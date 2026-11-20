"""
injector.py - CorruptionInjector for NYC 311 data
Injects 12 types of data corruption at a configurable rate.
"""

import re
import random
import string
import numpy as np
import pandas as pd
from copy import deepcopy
from typing import Optional


# Known "correct" mappings used for mismatch injection
BOROUGH_ZIPS = {
    "MANHATTAN":    ["10001", "10002", "10003", "10004", "10005", "10006", "10007"],
    "BROOKLYN":     ["11201", "11202", "11203", "11204", "11205", "11206", "11207"],
    "QUEENS":       ["11354", "11355", "11356", "11357", "11358", "11359", "11360"],
    "BRONX":        ["10451", "10452", "10453", "10454", "10455", "10456", "10457"],
    "STATEN ISLAND":["10301", "10302", "10303", "10304", "10305"],
}

COMPLAINT_DESCRIPTOR_MAP: dict[str, list[str]] = {
    "Noise - Residential":    ["Loud Music/Party", "Loud Talking", "Banging/Pounding"],
    "HEAT/HOT WATER":         ["No Heat", "Inadequate Heat", "No Hot Water"],
    "Blocked Driveway":       ["Partial Blockage", "No Access"],
    "Illegal Parking":        ["No Parking", "Blocked Hydrant", "Overnight Commercial Storage"],
    "Rodent":                 ["Rat Sighting", "Mouse Sighting", "Signs of Rodents"],
}
ALL_DESCRIPTORS = [d for ds in COMPLAINT_DESCRIPTOR_MAP.values() for d in ds]

OPEN_RESOLUTION_PHRASES = [
    "The condition was corrected.",
    "Upon inspection, the condition was not found.",
    "No action was necessary.",
]
PENDING_RESOLUTION_PHRASES = [
    "Your Service Request was closed.",
    "This complaint was resolved.",
]


def _random_phone() -> str:
    area = random.randint(200, 999)
    mid  = random.randint(200, 999)
    end  = random.randint(1000, 9999)
    sep = random.choice(["-", ".", " "])
    return f"{area}{sep}{mid}{sep}{end}"


def _random_email() -> str:
    name = "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 10)))
    domain = random.choice(["gmail.com", "yahoo.com", "hotmail.com", "example.com"])
    return f"{name}@{domain}"


class CorruptionInjector:
    """
    Injects synthetic data quality problems into a pandas DataFrame.

    Parameters
    ----------
    rate : float
        Fraction of rows to corrupt per injection type (default 0.05 = 5%).
    seed : int
        Random seed for reproducibility.
    """

    def __init__(self, rate: float = 0.05, seed: int = 42):
        self.rate = rate
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _n_rows(self, df: pd.DataFrame) -> int:
        return max(1, int(len(df) * self.rate))

    def _sample_idx(self, df: pd.DataFrame, n: Optional[int] = None) -> np.ndarray:
        n = n or self._n_rows(df)
        return np.random.choice(df.index, size=min(n, len(df)), replace=False)

    # ── 12 injection methods ──────────────────────────────────────────────────

    def inject_renamed_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """a. Rename or drop a random non-key column."""
        df = df.copy()
        cols = [c for c in df.columns if c not in ("unique_key",)]
        if not cols:
            return df
        col = random.choice(cols)
        action = random.choice(["rename", "drop"])
        if action == "rename":
            df = df.rename(columns={col: col + "_RENAMED"})
        else:
            df = df.drop(columns=[col])
        return df

    def inject_type_change(self, df: pd.DataFrame) -> pd.DataFrame:
        """b. Convert a numeric column to string to break downstream parsing."""
        df = df.copy()
        numeric_cols = [c for c in ["latitude", "longitude", "unique_key"] if c in df.columns]
        if not numeric_cols:
            # fall back to any numeric column
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return df
        col = random.choice(numeric_cols)
        df[col] = df[col].astype(str) + "_str"
        return df

    def inject_date_format_switch(self, df: pd.DataFrame) -> pd.DataFrame:
        """c. Reformat a portion of dates from ISO to MM/DD/YYYY."""
        df = df.copy()
        for col in ["created_date", "closed_date"]:
            if col not in df.columns:
                continue
            df[col] = df[col].astype(object)
            idx = self._sample_idx(df)
            for i in idx:
                val = df.at[i, col]
                if pd.isna(val):
                    continue
                try:
                    dt = pd.to_datetime(val)
                    df.at[i, col] = dt.strftime("%m/%d/%Y %I:%M:%S %p")
                except Exception:
                    pass
        return df

    def inject_lat_lon_swap(self, df: pd.DataFrame) -> pd.DataFrame:
        """d. Swap latitude and longitude values in selected rows."""
        df = df.copy()
        if "latitude" not in df.columns or "longitude" not in df.columns:
            return df
        idx = self._sample_idx(df)
        df.loc[idx, ["latitude", "longitude"]] = df.loc[idx, ["longitude", "latitude"]].values
        return df

    def inject_exact_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """e. Duplicate rows and append them to the DataFrame."""
        idx = self._sample_idx(df)
        dupes = df.loc[idx].copy()
        df = pd.concat([df, dupes], ignore_index=True)
        return df

    def inject_near_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """f. Add near-duplicates with slightly altered timestamp/text."""
        df = df.copy()
        idx = self._sample_idx(df)
        new_rows = []
        for i in idx:
            row = df.loc[i].copy()
            # Shift created_date by a few minutes
            if "created_date" in df.columns and pd.notna(row.get("created_date")):
                try:
                    dt = pd.to_datetime(row["created_date"])
                    shift = random.randint(1, 10)
                    row["created_date"] = (dt + pd.Timedelta(minutes=shift)).isoformat()
                except Exception:
                    pass
            # Append junk character to descriptor
            if "descriptor" in df.columns and pd.notna(row.get("descriptor")):
                row["descriptor"] = str(row["descriptor"]) + " " + random.choice(["(dup)", "- copy", "  "])
            new_rows.append(row)
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        return df

    def inject_null_spike(self, df: pd.DataFrame) -> pd.DataFrame:
        """g. Set key fields to null for one agency's records."""
        df = df.copy()
        if "agency" not in df.columns:
            return df
        agencies = df["agency"].dropna().unique()
        if len(agencies) == 0:
            return df
        target_agency = random.choice(agencies)
        agency_mask = df["agency"] == target_agency
        agency_idx = df[agency_mask].index
        n = max(1, int(len(agency_idx) * self.rate * 5))  # spike = 5× base rate
        chosen = np.random.choice(agency_idx, size=min(n, len(agency_idx)), replace=False)
        null_cols = [c for c in ["descriptor", "incident_zip", "borough"] if c in df.columns]
        if null_cols:
            df.loc[chosen, null_cols] = np.nan
        return df

    def inject_closed_before_created(self, df: pd.DataFrame) -> pd.DataFrame:
        """h. Set closed_date earlier than created_date."""
        df = df.copy()
        if "created_date" not in df.columns or "closed_date" not in df.columns:
            return df
        closed_mask = df["closed_date"].notna()
        eligible = df[closed_mask].index
        idx = np.random.choice(eligible, size=min(self._n_rows(df), len(eligible)), replace=False)
        for i in idx:
            try:
                cd = pd.to_datetime(df.at[i, "created_date"])
                shift = random.randint(1, 30)
                df.at[i, "closed_date"] = (cd - pd.Timedelta(days=shift)).isoformat()
            except Exception:
                pass
        return df

    def inject_zip_borough_mismatch(self, df: pd.DataFrame) -> pd.DataFrame:
        """i. Assign zip codes from a different borough."""
        df = df.copy()
        if "borough" not in df.columns or "incident_zip" not in df.columns:
            return df
        df["incident_zip"] = df["incident_zip"].astype(object)
        idx = self._sample_idx(df)
        for i in idx:
            borough = df.at[i, "borough"]
            if pd.isna(borough) or borough not in BOROUGH_ZIPS:
                continue
            wrong_boroughs = [b for b in BOROUGH_ZIPS if b != borough]
            if not wrong_boroughs:
                continue
            wrong_b = random.choice(wrong_boroughs)
            df.at[i, "incident_zip"] = str(random.choice(BOROUGH_ZIPS[wrong_b]))
        return df

    def inject_complaint_descriptor_mismatch(self, df: pd.DataFrame) -> pd.DataFrame:
        """j. Use descriptor that belongs to a different complaint type."""
        df = df.copy()
        if "complaint_type" not in df.columns or "descriptor" not in df.columns:
            return df
        idx = self._sample_idx(df)
        for i in idx:
            complaint = df.at[i, "complaint_type"]
            if complaint not in COMPLAINT_DESCRIPTOR_MAP:
                continue
            correct_descriptors = set(COMPLAINT_DESCRIPTOR_MAP[complaint])
            wrong_descriptors = [d for d in ALL_DESCRIPTORS if d not in correct_descriptors]
            if wrong_descriptors:
                df.at[i, "descriptor"] = random.choice(wrong_descriptors)
        return df

    def inject_resolution_status_mismatch(self, df: pd.DataFrame) -> pd.DataFrame:
        """k. Set resolution_description that contradicts status (Open but resolved)."""
        df = df.copy()
        if "status" not in df.columns or "resolution_description" not in df.columns:
            return df
        idx = self._sample_idx(df)
        for i in idx:
            status = df.at[i, "status"]
            if status in ("Open", "Pending", "In Progress"):
                df.at[i, "resolution_description"] = random.choice(OPEN_RESOLUTION_PHRASES)
            elif status == "Closed":
                df.at[i, "resolution_description"] = None  # closed but no resolution
        return df

    def inject_pii_in_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """l. Inject fake phone numbers or emails into descriptor fields."""
        df = df.copy()
        if "descriptor" not in df.columns:
            return df
        idx = self._sample_idx(df)
        for i in idx:
            pii_type = random.choice(["phone", "email"])
            pii = _random_phone() if pii_type == "phone" else _random_email()
            existing = str(df.at[i, "descriptor"]) if pd.notna(df.at[i, "descriptor"]) else ""
            df.at[i, "descriptor"] = f"{existing} Contact: {pii}"
        return df

    # ── convenience ───────────────────────────────────────────────────────────

    INJECTION_METHODS = [
        "inject_renamed_column",
        "inject_type_change",
        "inject_date_format_switch",
        "inject_lat_lon_swap",
        "inject_exact_duplicates",
        "inject_near_duplicates",
        "inject_null_spike",
        "inject_closed_before_created",
        "inject_zip_borough_mismatch",
        "inject_complaint_descriptor_mismatch",
        "inject_resolution_status_mismatch",
        "inject_pii_in_text",
    ]

    def inject_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Inject ALL 12 problem types sequentially."""
        for method_name in self.INJECTION_METHODS:
            method = getattr(self, method_name)
            df = method(df)
        return df

    def inject_one(self, df: pd.DataFrame, problem_type: str) -> pd.DataFrame:
        """Inject a single problem type by name key (e.g. 'null_spike')."""
        mapping = {
            "renamed_column":               self.inject_renamed_column,
            "type_change":                  self.inject_type_change,
            "date_format_switch":           self.inject_date_format_switch,
            "lat_lon_swap":                 self.inject_lat_lon_swap,
            "exact_duplicates":             self.inject_exact_duplicates,
            "near_duplicates":              self.inject_near_duplicates,
            "null_spike":                   self.inject_null_spike,
            "closed_before_created":        self.inject_closed_before_created,
            "zip_borough_mismatch":         self.inject_zip_borough_mismatch,
            "complaint_descriptor_mismatch":self.inject_complaint_descriptor_mismatch,
            "resolution_status_mismatch":   self.inject_resolution_status_mismatch,
            "pii_in_text":                  self.inject_pii_in_text,
        }
        if problem_type not in mapping:
            raise ValueError(f"Unknown problem type: {problem_type!r}. Choose from: {list(mapping)}")
        return mapping[problem_type](df)
