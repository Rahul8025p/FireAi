"""
detectors/rule_based.py - Rule-Based Detector for NYC 311 data quality issues.

Uses pure pandas/Python logic (no ML, no LLM).
Returns: {problem_type: {detected: bool, count: int, rows: list[int], explanation: str}}
Designed to handle 1M rows in <30 seconds.
"""

import re
import pandas as pd
import numpy as np
from typing import Any

# ── known reference data ──────────────────────────────────────────────────────

BOROUGH_ZIP_PREFIXES: dict[str, list[str]] = {
    "MANHATTAN":     ["100"],
    "BROOKLYN":      ["112"],
    "QUEENS":        ["113", "114", "116"],
    "BRONX":         ["104"],
    "STATEN ISLAND": ["103"],
}

COMPLAINT_DESCRIPTOR_MAP: dict[str, set[str]] = {
    "Noise - Residential":    {"Loud Music/Party", "Loud Talking", "Banging/Pounding"},
    "HEAT/HOT WATER":         {"No Heat", "Inadequate Heat", "No Hot Water"},
    "Blocked Driveway":       {"Partial Blockage", "No Access"},
    "Illegal Parking":        {"No Parking", "Blocked Hydrant", "Overnight Commercial Storage"},
    "Rodent":                 {"Rat Sighting", "Mouse Sighting", "Signs of Rodents"},
    "Noise - Residential":    {"Loud Music/Party", "Loud Talking", "Banging/Pounding"},
    "Street Light Condition": {"Street Light Out", "Lamp Broken", "Light Flickering"},
    "Water System":           {"No Running Water", "Low Pressure", "Water Quality"},
    "Building/Use":           {"Illegal Conversion", "Zoning Violation"},
    "Plumbing":               {"Noisy Pipes", "Leaking Pipe", "Broken Faucet"},
    "Paint/Plaster":          {"Peeling", "Chipping", "Mold"},
}

OPEN_STATUS = {"Open", "Pending", "In Progress"}
CLOSED_STATUS = {"Closed"}

RESOLUTION_CLOSED_PATTERNS = [
    "corrected", "resolved", "no action", "not found", "jurisdiction",
    "closed", "forwarded",
]

PHONE_RE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

EXPECTED_COLUMNS = {
    "unique_key", "created_date", "closed_date", "agency", "agency_name",
    "complaint_type", "descriptor", "location_type", "incident_zip",
    "incident_address", "city", "borough", "latitude", "longitude",
    "status", "resolution_description",
}

# NYC bounding box
NYC_LAT_MIN, NYC_LAT_MAX = 40.49, 40.91
NYC_LON_MIN, NYC_LON_MAX = -74.26, -73.70


def _result(detected: bool, count: int, rows: list[int], explanation: str) -> dict:
    return {"detected": detected, "count": count, "rows": rows, "explanation": explanation}


class RuleBasedDetector:
    """
    Detects 12 data quality problem types using pure pandas/Python rules.

    Usage
    -----
    det = RuleBasedDetector()
    results = det.detect_all(df)
    """

    # ── individual detectors ──────────────────────────────────────────────────

    def detect_renamed_column(self, df: pd.DataFrame) -> dict:
        """a. Check for missing or unexpected column names."""
        actual = set(df.columns.str.lower())
        # strip _RENAMED suffix that the injector adds
        actual_clean = {c.replace("_renamed", "") for c in actual}
        missing = EXPECTED_COLUMNS - actual_clean
        renamed = {c for c in actual if c.endswith("_renamed")}
        issues = missing | renamed
        detected = len(issues) > 0
        return _result(
            detected, len(issues), [],
            f"Missing/renamed columns: {sorted(issues)}" if detected else "All expected columns present.",
        )

    def detect_type_change(self, df: pd.DataFrame) -> dict:
        """b. Detect numeric columns stored as non-numeric strings."""
        bad_rows: list[int] = []
        details: list[str] = []
        for col in ["latitude", "longitude", "unique_key", "incident_zip", "bbl"]:
            if col not in df.columns:
                continue
            # If column contains non-numeric strings or has alpha characters
            series_str = df[col].dropna().astype(str)
            numeric = pd.to_numeric(df[col], errors="coerce")
            bad_mask = df[col].notna() & numeric.isna()
            suffix_mask = series_str.str.contains(r"[A-Za-z_]", regex=True)
            combined = bad_mask | suffix_mask
            bad = df.index[combined].tolist()
            if bad:
                bad_rows.extend(bad)
                details.append(f"{col}: {len(bad)} bad values")
        bad_rows = list(dict.fromkeys(bad_rows))
        detected = len(bad_rows) > 0
        return _result(detected, len(bad_rows), bad_rows[:100],
                       "; ".join(details) if detected else "No type anomalies detected.")

    def detect_date_format_switch(self, df: pd.DataFrame) -> dict:
        """c. Find rows where dates deviate from the dominant format."""
        bad_rows: list[int] = []
        details: list[str] = []
        for col in ["created_date", "closed_date"]:
            if col not in df.columns:
                continue
            series = df[col].dropna().astype(str)
            if series.empty:
                continue
            # ISO format: starts with 4-digit year
            iso_mask = series.str.match(r"^\d{4}-\d{2}-\d{2}")
            # US format: MM/DD/YYYY
            us_mask = series.str.match(r"^\d{1,2}/\d{1,2}/\d{4}")
            iso_count = iso_mask.sum()
            us_count = us_mask.sum()
            # Whichever format is minority is "switched"
            if iso_count > us_count and us_count > 0:
                minority_idx = series[us_mask].index.tolist()
                bad_rows.extend(minority_idx)
                details.append(f"{col}: {us_count} rows in US format (minority)")
            elif us_count >= iso_count and iso_count > 0:
                minority_idx = series[iso_mask].index.tolist()
                bad_rows.extend(minority_idx)
                details.append(f"{col}: {iso_count} rows in ISO format (minority)")
        bad_rows = list(dict.fromkeys(bad_rows))
        detected = len(bad_rows) > 0
        return _result(detected, len(bad_rows), bad_rows[:100],
                       "; ".join(details) if detected else "No date format switches detected.")

    def detect_lat_lon_swap(self, df: pd.DataFrame) -> dict:
        """d. Detect swapped lat/lon: NYC lat ~40-41, lon ~-74 to -73."""
        if "latitude" not in df.columns or "longitude" not in df.columns:
            return _result(False, 0, [], "latitude or longitude column missing.")
        lat = pd.to_numeric(df["latitude"], errors="coerce")
        lon = pd.to_numeric(df["longitude"], errors="coerce")
        # A swap: lat looks like a longitude (negative ~-74) or lon looks like lat (~40)
        swap_mask = (
            (lat < -60) | (lat > 60) |   # lat is too extreme
            (lon > 0)  |                 # longitude should be negative for NYC
            (lon > 30)                   # lon looks like a latitude
        )
        both_valid = lat.notna() & lon.notna()
        swapped = df.index[swap_mask & both_valid].tolist()
        detected = len(swapped) > 0
        return _result(detected, len(swapped), swapped[:100],
                       f"{len(swapped)} rows with likely swapped lat/lon." if detected
                       else "No lat/lon swaps detected.")

    def detect_exact_duplicates(self, df: pd.DataFrame) -> dict:
        """e. Find exact duplicate rows."""
        dup_mask = df.duplicated(keep=False)
        dup_rows = df.index[dup_mask].tolist()
        detected = len(dup_rows) > 0
        return _result(detected, len(dup_rows), dup_rows[:100],
                       f"{len(dup_rows)} rows are exact duplicates." if detected
                       else "No exact duplicates found.")

    def detect_near_duplicates(self, df: pd.DataFrame) -> dict:
        """f. Detect near-duplicate rows (same unique_key, slightly different timestamp/text)."""
        if "unique_key" not in df.columns:
            return _result(False, 0, [], "unique_key column missing.")
        # Rows sharing a unique_key are near-duplicates
        uk_dup_mask = df.duplicated(subset=["unique_key"], keep=False)
        dup_rows = df.index[uk_dup_mask].tolist()
        # Also check for rows within 10-min of each other sharing agency+complaint
        near_rows: list[int] = []
        if "created_date" in df.columns and "agency" in df.columns and "complaint_type" in df.columns:
            tmp = df[["agency", "complaint_type", "created_date", "descriptor"]].copy()
            tmp["_cd"] = pd.to_datetime(tmp["created_date"], errors="coerce")
            tmp = tmp.sort_values("_cd")
            # Vectorised: group by agency+complaint, check time delta between consecutive rows
            tmp["_prev_cd"] = tmp.groupby(["agency", "complaint_type"])["_cd"].shift(1)
            tmp["_delta"] = (tmp["_cd"] - tmp["_prev_cd"]).abs()
            near_mask = tmp["_delta"] < pd.Timedelta(minutes=15)
            near_rows = tmp.index[near_mask].tolist()
        all_rows = list(dict.fromkeys(dup_rows + near_rows))
        detected = len(all_rows) > 0
        return _result(detected, len(all_rows), all_rows[:100],
                       f"{len(all_rows)} near-duplicate rows detected." if detected
                       else "No near-duplicates found.")

    def detect_null_spike(self, df: pd.DataFrame) -> dict:
        """g. Detect agencies/groups with abnormally high null rates."""
        if "agency" not in df.columns:
            return _result(False, 0, [], "agency column missing.")
        key_cols = [c for c in ["descriptor", "incident_zip", "borough"] if c in df.columns]
        if not key_cols:
            return _result(False, 0, [], "No key columns to check for null spikes.")
        agency_null_rate = (
            df.groupby("agency")[key_cols]
            .apply(lambda g: g.isnull().mean().mean())
        )
        overall_rate = df[key_cols].isnull().mean().mean()
        # Flag agencies with null rate > 3x overall
        threshold = max(0.1, overall_rate * 3)
        spiked = agency_null_rate[agency_null_rate > threshold]
        if spiked.empty:
            return _result(False, 0, [], "No null spikes detected.")
        spiked_agencies = spiked.index.tolist()
        rows = df[df["agency"].isin(spiked_agencies)].index.tolist()
        return _result(True, len(rows), rows[:100],
                       f"Null spike in agencies: {spiked_agencies} (rate {spiked.to_dict()})")

    def detect_closed_before_created(self, df: pd.DataFrame) -> dict:
        """h. Detect rows where closed_date < created_date."""
        if "created_date" not in df.columns or "closed_date" not in df.columns:
            return _result(False, 0, [], "created_date or closed_date missing.")
        cd = pd.to_datetime(df["created_date"], format="mixed", errors="coerce")
        cl = pd.to_datetime(df["closed_date"], format="mixed", errors="coerce")
        both = cd.notna() & cl.notna()
        bad_mask = both & (cl < cd)
        bad_rows = df.index[bad_mask].tolist()
        detected = len(bad_rows) > 0
        return _result(detected, len(bad_rows), bad_rows[:100],
                       f"{len(bad_rows)} rows have closed_date before created_date." if detected
                       else "No date inversions found.")

    def detect_zip_borough_mismatch(self, df: pd.DataFrame) -> dict:
        """i. Check if zip code prefix matches the stated borough."""
        if "borough" not in df.columns or "incident_zip" not in df.columns:
            return _result(False, 0, [], "borough or incident_zip column missing.")
        bad_rows: list[int] = []
        for idx, row in df[["borough", "incident_zip"]].iterrows():
            borough = str(row["borough"]).upper().strip() if pd.notna(row["borough"]) else None
            zipcode = str(row["incident_zip"]).strip() if pd.notna(row["incident_zip"]) else None
            if not borough or not zipcode or borough not in BOROUGH_ZIP_PREFIXES:
                continue
            valid_prefixes = BOROUGH_ZIP_PREFIXES[borough]
            if not any(zipcode.startswith(p) for p in valid_prefixes):
                bad_rows.append(idx)
        detected = len(bad_rows) > 0
        return _result(detected, len(bad_rows), bad_rows[:100],
                       f"{len(bad_rows)} rows have zip code not matching borough." if detected
                       else "No zip/borough mismatches found.")

    def detect_complaint_descriptor_mismatch(self, df: pd.DataFrame) -> dict:
        """j. Flag rows where descriptor doesn't belong to complaint_type."""
        if "complaint_type" not in df.columns or "descriptor" not in df.columns:
            return _result(False, 0, [], "complaint_type or descriptor column missing.")
        bad_rows: list[int] = []
        all_valid = {d for s in COMPLAINT_DESCRIPTOR_MAP.values() for d in s}
        for idx, row in df[["complaint_type", "descriptor"]].iterrows():
            ct = str(row["complaint_type"]).strip() if pd.notna(row["complaint_type"]) else None
            desc = str(row["descriptor"]).strip() if pd.notna(row["descriptor"]) else None
            if not ct or not desc or ct not in COMPLAINT_DESCRIPTOR_MAP:
                continue
            valid = COMPLAINT_DESCRIPTOR_MAP[ct]
            if desc in all_valid and desc not in valid:
                bad_rows.append(idx)
        detected = len(bad_rows) > 0
        return _result(detected, len(bad_rows), bad_rows[:100],
                       f"{len(bad_rows)} rows have descriptor/complaint_type mismatch." if detected
                       else "No complaint/descriptor mismatches found.")

    def detect_resolution_status_mismatch(self, df: pd.DataFrame) -> dict:
        """k. Open/Pending rows that have a resolution, or Closed rows with no resolution."""
        if "status" not in df.columns or "resolution_description" not in df.columns:
            return _result(False, 0, [], "status or resolution_description column missing.")
        status_upper = df["status"].astype(str).str.strip().str.title()
        has_resolution = df["resolution_description"].notna() & (df["resolution_description"].astype(str).str.strip() != "")
        # Open/Pending with resolution = suspicious
        open_with_res = df.index[status_upper.isin(["Open", "Pending", "In Progress"]) & has_resolution].tolist()
        # Closed without resolution
        closed_no_res = df.index[(status_upper == "Closed") & (~has_resolution)].tolist()
        all_bad = list(dict.fromkeys(open_with_res + closed_no_res))
        detected = len(all_bad) > 0
        return _result(detected, len(all_bad), all_bad[:100],
                       f"{len(open_with_res)} open+resolved, {len(closed_no_res)} closed+no-resolution." if detected
                       else "No resolution/status mismatches found.")

    def detect_pii_in_text(self, df: pd.DataFrame) -> dict:
        """l. Find phone numbers or email addresses in text fields."""
        text_cols = [c for c in ["descriptor", "resolution_description"] if c in df.columns]
        bad_rows: list[int] = []
        details: list[str] = []
        for col in text_cols:
            series = df[col].dropna().astype(str)
            phone_hits = series.str.contains(PHONE_RE, regex=True)
            email_hits = series.str.contains(EMAIL_RE, regex=True)
            combined = phone_hits | email_hits
            hits = series.index[combined].tolist()
            if hits:
                bad_rows.extend(hits)
                details.append(f"{col}: {len(hits)} rows with PII")
        bad_rows = list(dict.fromkeys(bad_rows))
        detected = len(bad_rows) > 0
        return _result(detected, len(bad_rows), bad_rows[:100],
                       "; ".join(details) if detected else "No PII detected in text fields.")

    # ── convenience ───────────────────────────────────────────────────────────

    DETECTOR_MAP = {
        "renamed_column":                "detect_renamed_column",
        "type_change":                   "detect_type_change",
        "date_format_switch":            "detect_date_format_switch",
        "lat_lon_swap":                  "detect_lat_lon_swap",
        "exact_duplicates":              "detect_exact_duplicates",
        "near_duplicates":               "detect_near_duplicates",
        "null_spike":                    "detect_null_spike",
        "closed_before_created":         "detect_closed_before_created",
        "zip_borough_mismatch":          "detect_zip_borough_mismatch",
        "complaint_descriptor_mismatch": "detect_complaint_descriptor_mismatch",
        "resolution_status_mismatch":    "detect_resolution_status_mismatch",
        "pii_in_text":                   "detect_pii_in_text",
    }

    def detect_all(self, df: pd.DataFrame) -> dict[str, dict]:
        """Run all 12 detectors and return combined results."""
        results: dict[str, dict] = {}
        for key, method_name in self.DETECTOR_MAP.items():
            try:
                results[key] = getattr(self, method_name)(df)
            except Exception as exc:
                results[key] = _result(False, 0, [], f"ERROR: {exc}")
        return results

    def detect_one(self, df: pd.DataFrame, problem_type: str) -> dict:
        """Run a single detector by name key."""
        if problem_type not in self.DETECTOR_MAP:
            raise ValueError(f"Unknown problem type: {problem_type!r}")
        return getattr(self, self.DETECTOR_MAP[problem_type])(df)
