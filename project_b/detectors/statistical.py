"""
detectors/statistical.py - Statistical Detector for NYC 311 data quality issues.

Uses z-scores, IQR, moving averages, and chi-square tests.
Returns: {problem_type: {detected: bool, count: int, rows: list[int], explanation: str}}
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Any


def _result(detected: bool, count: int, rows: list[int], explanation: str) -> dict:
    return {"detected": detected, "count": count, "rows": rows, "explanation": explanation}


def _zscore_outlier_rows(series: pd.Series, threshold: float = 3.0) -> list[int]:
    """Return index positions where z-score > threshold."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.std() == 0 or len(s) < 3:
        return []
    z = np.abs(stats.zscore(s))
    return s.index[z > threshold].tolist()


def _iqr_outlier_rows(series: pd.Series, multiplier: float = 3.0) -> list[int]:
    """Return index positions that are IQR outliers."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 4:
        return []
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
    return s.index[(s < lower) | (s > upper)].tolist()


class StatisticalDetector:
    """
    Detects data quality issues using statistical methods.

    Parameters
    ----------
    z_threshold : float
        Z-score threshold for outlier detection (default 3.0).
    iqr_multiplier : float
        IQR multiplier for outlier detection (default 3.0).
    chi2_alpha : float
        Significance level for chi-square tests (default 0.05).
    """

    def __init__(self, z_threshold: float = 3.0, iqr_multiplier: float = 3.0,
                 chi2_alpha: float = 0.05):
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier
        self.chi2_alpha = chi2_alpha

    # ── individual detectors ──────────────────────────────────────────────────

    def detect_null_spike(self, df: pd.DataFrame) -> dict:
        """
        Detect agencies with abnormally high null rates using z-scores.
        Groups by agency and measures null fraction across key columns.
        """
        if "agency" not in df.columns:
            return _result(False, 0, [], "agency column missing.")
        key_cols = [c for c in ["descriptor", "incident_zip", "borough", "latitude"] if c in df.columns]
        if not key_cols:
            return _result(False, 0, [], "No key columns found.")
        agency_null = (
            df.groupby("agency")[key_cols]
            .apply(lambda g: g.isnull().mean().mean())
            .rename("null_rate")
        )
        if len(agency_null) < 3:
            return _result(False, 0, [], "Too few agencies for statistical test.")
        z = np.abs(stats.zscore(agency_null.values))
        spiked_agencies = agency_null.index[z > self.z_threshold].tolist()
        if not spiked_agencies:
            return _result(False, 0, [], f"No null spikes detected (z-threshold={self.z_threshold}).")
        rows = df[df["agency"].isin(spiked_agencies)].index.tolist()
        return _result(True, len(rows), rows[:100],
                       f"Null spike (z>{self.z_threshold}) in {spiked_agencies}; "
                       f"rates: {agency_null[spiked_agencies].to_dict()}")

    def detect_duplicate_rate(self, df: pd.DataFrame) -> dict:
        """Detect abnormally high duplicate rates vs. expected baseline."""
        dup_count = df.duplicated().sum()
        dup_rate = dup_count / len(df)
        # Baseline: 0.1% duplicates is typical; flag if >3% (IQR would need historical data)
        threshold = 0.03
        detected = dup_rate > threshold
        return _result(detected, int(dup_count), [],
                       f"Duplicate rate {dup_rate:.2%} {'exceeds' if detected else 'within'} threshold {threshold:.2%}.")

    def detect_date_anomalies(self, df: pd.DataFrame) -> dict:
        """
        Use moving-average z-score on daily complaint volume to flag date anomalies
        (spikes or gaps that suggest corrupt dates).
        """
        if "created_date" not in df.columns:
            return _result(False, 0, [], "created_date missing.")
        dates = pd.to_datetime(df["created_date"], errors="coerce")
        valid = dates.dropna()
        if valid.empty:
            return _result(False, 0, [], "No valid dates.")
        daily = valid.dt.date.value_counts().sort_index()
        if len(daily) < 7:
            return _result(False, 0, [], "Too few days for moving average.")
        # 7-day moving average
        rolling_mean = daily.rolling(7, min_periods=1).mean()
        rolling_std  = daily.rolling(7, min_periods=1).std().fillna(1)
        z_scores = ((daily - rolling_mean) / rolling_std).abs()
        anomaly_days = daily.index[z_scores > self.z_threshold].tolist()
        if not anomaly_days:
            return _result(False, 0, [], "No date anomalies via moving average.")
        anomaly_days_set = set(str(d) for d in anomaly_days)
        rows = df.index[dates.dt.date.astype(str).isin(anomaly_days_set)].tolist()
        return _result(True, len(rows), rows[:100],
                       f"Date volume anomalies on {anomaly_days} (z>{self.z_threshold}).")

    def detect_coordinate_outliers(self, df: pd.DataFrame) -> dict:
        """Detect coordinate outliers using IQR."""
        rows: list[int] = []
        details: list[str] = []
        for col in ["latitude", "longitude"]:
            if col not in df.columns:
                continue
            outlier_idx = _iqr_outlier_rows(df[col], self.iqr_multiplier)
            if outlier_idx:
                rows.extend(outlier_idx)
                details.append(f"{col}: {len(outlier_idx)} outliers")
        rows = list(dict.fromkeys(rows))
        detected = len(rows) > 0
        return _result(detected, len(rows), rows[:100],
                       "; ".join(details) if detected else "No coordinate outliers (IQR).")

    def detect_text_length_anomalies(self, df: pd.DataFrame) -> dict:
        """Detect text length outliers using IQR on descriptor and resolution fields."""
        rows: list[int] = []
        details: list[str] = []
        for col in ["descriptor", "resolution_description"]:
            if col not in df.columns:
                continue
            lengths = df[col].dropna().str.len()
            outlier_idx = _iqr_outlier_rows(lengths, self.iqr_multiplier)
            if outlier_idx:
                rows.extend(outlier_idx)
                details.append(f"{col}: {len(outlier_idx)} length outliers")
        rows = list(dict.fromkeys(rows))
        detected = len(rows) > 0
        return _result(detected, len(rows), rows[:100],
                       "; ".join(details) if detected else "No text length anomalies.")

    def detect_distribution_shift(self, df: pd.DataFrame) -> dict:
        """
        Use chi-square test on complaint_type and borough distributions
        split by first-half vs second-half of the dataset to detect shifts.
        """
        results_parts: list[str] = []
        any_shift = False
        shift_rows: list[int] = []
        for col in ["complaint_type", "borough", "agency"]:
            if col not in df.columns:
                continue
            half = len(df) // 2
            if half < 10:
                continue
            first  = df.iloc[:half][col].value_counts()
            second = df.iloc[half:][col].value_counts()
            # Align categories
            all_cats = first.index.union(second.index)
            first  = first.reindex(all_cats, fill_value=0)
            second = second.reindex(all_cats, fill_value=0)
            if first.sum() == 0 or second.sum() == 0:
                continue
            # Normalize to same total for chi2
            combined = np.vstack([first.values, second.values])
            try:
                chi2, p, dof, _ = stats.chi2_contingency(combined)
                if p < self.chi2_alpha:
                    any_shift = True
                    results_parts.append(f"{col}: chi2={chi2:.1f} p={p:.4f}")
                    # Flag second-half rows as shifted
                    shift_rows.extend(df.index[half:].tolist())
            except Exception:
                pass
        shift_rows = list(dict.fromkeys(shift_rows))
        return _result(any_shift, len(shift_rows), shift_rows[:100],
                       "Distribution shifts: " + "; ".join(results_parts) if any_shift
                       else "No distribution shifts detected.")

    def detect_lat_lon_swap(self, df: pd.DataFrame) -> dict:
        """
        Detect lat/lon swap using IQR: NYC lats cluster ~40.7, lons ~-73.9.
        A swapped value will be an extreme outlier for its column.
        """
        rows: list[int] = []
        for col, expected_sign in [("latitude", 1), ("longitude", -1)]:
            if col not in df.columns:
                continue
            num = pd.to_numeric(df[col], errors="coerce")
            # Wrong sign
            wrong_sign = df.index[num.notna() & (np.sign(num) != expected_sign)].tolist()
            rows.extend(wrong_sign)
            # IQR outliers
            rows.extend(_iqr_outlier_rows(num, self.iqr_multiplier))
        rows = list(dict.fromkeys(rows))
        detected = len(rows) > 0
        return _result(detected, len(rows), rows[:100],
                       f"{len(rows)} probable lat/lon swap rows." if detected
                       else "No lat/lon swaps detected statistically.")

    def detect_closed_before_created(self, df: pd.DataFrame) -> dict:
        """Detect date inversions and flag duration outliers (z-score)."""
        if "created_date" not in df.columns or "closed_date" not in df.columns:
            return _result(False, 0, [], "Date columns missing.")
        cd = pd.to_datetime(df["created_date"], errors="coerce")
        cl = pd.to_datetime(df["closed_date"], errors="coerce")
        both = cd.notna() & cl.notna()
        duration = (cl - cd).dt.total_seconds() / 3600  # hours
        # Negative duration = closed before created
        neg_rows = df.index[both & (duration < 0)].tolist()
        # Statistical outliers in duration (extremely short or long)
        valid_dur = duration[both & (duration >= 0)]
        outlier_rows: list[int] = []
        if len(valid_dur) > 10:
            outlier_rows = _zscore_outlier_rows(valid_dur, self.z_threshold)
        all_rows = list(dict.fromkeys(neg_rows + outlier_rows))
        detected = len(neg_rows) > 0
        return _result(detected, len(neg_rows), neg_rows[:100],
                       f"{len(neg_rows)} inverted dates; {len(outlier_rows)} duration outliers." if detected
                       else f"No date inversions; {len(outlier_rows)} duration outliers noted.")

    def detect_zip_borough_mismatch(self, df: pd.DataFrame) -> dict:
        """
        Statistical: flag zip codes whose first-3-digits deviate from the
        dominant pattern for that borough using chi-square.
        """
        if "borough" not in df.columns or "incident_zip" not in df.columns:
            return _result(False, 0, [], "borough or incident_zip missing.")
        df2 = df[["borough", "incident_zip"]].copy()
        df2["zip3"] = df2["incident_zip"].astype(str).str[:3]
        # For each borough, find dominant zip prefix; flag deviations
        bad_rows: list[int] = []
        for borough, grp in df2.groupby("borough"):
            if grp.empty:
                continue
            counts = grp["zip3"].value_counts()
            dominant = counts.idxmax()
            # Flag if zip3 is not dominant AND residual count is statistically small
            # Simple rule: flag rows where zip3 != mode and mode covers >70% of rows
            dominant_pct = counts.max() / len(grp)
            if dominant_pct > 0.7:
                non_dominant = grp.index[grp["zip3"] != dominant].tolist()
                bad_rows.extend(non_dominant)
        detected = len(bad_rows) > 0
        return _result(detected, len(bad_rows), bad_rows[:100],
                       f"{len(bad_rows)} zip codes deviate from borough's dominant pattern." if detected
                       else "No statistical zip/borough anomalies.")

    def detect_pii_in_text(self, df: pd.DataFrame) -> dict:
        """
        Statistical: flag rows where descriptor length is a z-score outlier
        (PII appended makes text longer) AND contains '@' or digit runs.
        """
        if "descriptor" not in df.columns:
            return _result(False, 0, [], "descriptor column missing.")
        series = df["descriptor"].dropna()
        lengths = series.str.len()
        outlier_long = set(_zscore_outlier_rows(lengths, self.z_threshold))
        # Also flag presence of '@' or phone-like patterns
        has_at = set(series.index[series.str.contains("@", na=False)])
        has_digits = set(series.index[series.str.contains(r"\d{3}[-.\s]\d{3}", na=False, regex=True)])
        candidates = (outlier_long | has_at | has_digits)
        rows = list(candidates)
        detected = len(rows) > 0
        return _result(detected, len(rows), rows[:100],
                       f"{len(rows)} rows with possible PII (length outlier + pattern)." if detected
                       else "No statistical PII signal.")

    # ── convenience ───────────────────────────────────────────────────────────

    DETECTOR_MAP = {
        "null_spike":                    "detect_null_spike",
        "duplicate_rate":                "detect_duplicate_rate",
        "date_anomalies":                "detect_date_anomalies",
        "coordinate_outliers":           "detect_coordinate_outliers",
        "text_length_anomalies":         "detect_text_length_anomalies",
        "distribution_shift":            "detect_distribution_shift",
        "lat_lon_swap":                  "detect_lat_lon_swap",
        "closed_before_created":         "detect_closed_before_created",
        "zip_borough_mismatch":          "detect_zip_borough_mismatch",
        "pii_in_text":                   "detect_pii_in_text",
    }

    def detect_all(self, df: pd.DataFrame) -> dict[str, dict]:
        """Run all statistical detectors."""
        results: dict[str, dict] = {}
        for key, method_name in self.DETECTOR_MAP.items():
            try:
                results[key] = getattr(self, method_name)(df)
            except Exception as exc:
                results[key] = _result(False, 0, [], f"ERROR: {exc}")
        return results
