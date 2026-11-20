"""
profiler.py - NYC 311 Data Quality Profiler
Profiles data quality issues and outputs a markdown report.
"""

import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional


# ── sample data generation ────────────────────────────────────────────────────

BOROUGHS = ["MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND"]
AGENCIES = ["NYPD", "HPD", "DOT", "DSNY", "DEP", "DOB", "DOHMH", "DPR"]
COMPLAINT_TYPES = [
    "Noise - Residential", "HEAT/HOT WATER", "Blocked Driveway",
    "Illegal Parking", "Street Light Condition", "Rodent",
    "Water System", "Building/Use", "Plumbing", "Paint/Plaster",
]
DESCRIPTORS = [
    "Loud Music/Party", "No Heat", "Partial Blockage", "No Parking",
    "Street Light Out", "Rat Sighting", "No Running Water",
    "Illegal Conversion", "Noisy Pipes", "Peeling",
]
BOROUGH_ZIPS = {
    "MANHATTAN": ["10001", "10002", "10003", "10004", "10005"],
    "BROOKLYN":  ["11201", "11202", "11203", "11204", "11205"],
    "QUEENS":    ["11354", "11355", "11356", "11357", "11358"],
    "BRONX":     ["10451", "10452", "10453", "10454", "10455"],
    "STATEN ISLAND": ["10301", "10302", "10303", "10304", "10305"],
}
STATUSES = ["Open", "Closed", "Pending", "In Progress"]
RESOLUTIONS = [
    "The condition was corrected.",
    "Upon inspection, the condition was not found.",
    "No action was necessary.",
    "The complaint was forwarded.",
    "This complaint does not fall under our jurisdiction.",
]


def generate_sample_data(n: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate a realistic-looking NYC 311 dataset."""
    rng = np.random.default_rng(seed)
    boroughs = rng.choice(BOROUGHS, n)
    complaint_indices = rng.integers(0, len(COMPLAINT_TYPES), n)
    statuses = rng.choice(STATUSES, n, p=[0.3, 0.5, 0.1, 0.1])

    created_dates = pd.date_range("2023-01-01", "2023-12-31", periods=n)
    days_to_close = rng.integers(0, 30, n)
    closed_dates = [
        (created_dates[i] + pd.Timedelta(days=int(days_to_close[i]))).isoformat()
        if statuses[i] == "Closed" else None
        for i in range(n)
    ]

    lats = rng.uniform(40.49, 40.91, n).astype(str)
    lons = rng.uniform(-74.26, -73.70, n).astype(str)

    zips = [
        rng.choice(BOROUGH_ZIPS[b]) for b in boroughs
    ]

    df = pd.DataFrame({
        "unique_key":           [str(10000000 + i) for i in range(n)],
        "created_date":         [d.isoformat() for d in created_dates],
        "closed_date":          closed_dates,
        "agency":               rng.choice(AGENCIES, n),
        "agency_name":          rng.choice(AGENCIES, n),
        "complaint_type":       [COMPLAINT_TYPES[i] for i in complaint_indices],
        "descriptor":           [DESCRIPTORS[i] for i in complaint_indices],
        "location_type":        rng.choice(["Street/Sidewalk", "Residential Building", "Commercial"], n),
        "incident_zip":         zips,
        "incident_address":     [f"{rng.integers(1,999)} MAIN ST" for _ in range(n)],
        "city":                 boroughs,
        "borough":              boroughs,
        "latitude":             lats,
        "longitude":            lons,
        "status":               statuses,
        "resolution_description": [
            rng.choice(RESOLUTIONS) if s == "Closed" else None
            for s in statuses
        ],
    })
    return df


# ── downloader ────────────────────────────────────────────────────────────────

def download_sample(limit: int = 50_000, save_path: str = "nyc311_sample.csv") -> pd.DataFrame:
    """
    Download up to `limit` rows of 2023 NYC 311 data from the Socrata API.
    Falls back to generated sample data if the download fails.
    """
    url = (
        "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
        f"?$where=date_extract_y(created_date)=2023"
        f"&$limit={limit}"
        f"&$order=created_date"
    )
    print(f"Downloading {limit} rows from NYC Open Data …")
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)
        df.to_csv(save_path, index=False)
        print(f"Saved {len(df)} rows to {save_path}")
        return df
    except Exception as exc:
        print(f"Download failed ({exc}). Generating synthetic sample …")
        df = generate_sample_data(5000)
        df.to_csv(save_path, index=False)
        print(f"Saved {len(df)} synthetic rows to {save_path}")
        return df


# ── profiler ──────────────────────────────────────────────────────────────────

def profile_dataframe(df: pd.DataFrame) -> dict:
    """Run all quality checks and return structured results."""
    # Ensure unhashable nested dict/list columns are serialized
    work_df = df.copy()
    for col in work_df.columns:
        if work_df[col].apply(lambda x: isinstance(x, (dict, list))).any():
            work_df[col] = work_df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)

    results: dict = {}
    n = len(work_df)

    # 1. Null analysis
    null_counts = work_df.isnull().sum()
    null_pct = (null_counts / n * 100).round(2)
    results["nulls"] = {
        col: {"count": int(null_counts[col]), "pct": float(null_pct[col])}
        for col in work_df.columns
        if null_counts[col] > 0
    }

    # 2. Duplicates
    dup_mask = work_df.duplicated()
    results["exact_duplicates"] = {
        "count": int(dup_mask.sum()),
        "pct": round(dup_mask.sum() / n * 100, 2),
    }
    if "unique_key" in work_df.columns:
        uk_dups = work_df["unique_key"].duplicated().sum()
        results["unique_key_duplicates"] = {
            "count": int(uk_dups),
            "pct": round(uk_dups / n * 100, 2),
        }

    # 3. Date issues
    date_issues = {}
    for col in ["created_date", "closed_date"]:
        if col in df.columns:
            series = df[col].dropna()
            parsed = pd.to_datetime(series, errors="coerce")
            unparseable = int(parsed.isna().sum())
            future = int((parsed > pd.Timestamp.now()).sum()) if not parsed.isna().all() else 0
            date_issues[col] = {
                "unparseable": unparseable,
                "future_dates": future,
            }
    if "created_date" in df.columns and "closed_date" in df.columns:
        cd = pd.to_datetime(df["created_date"], errors="coerce")
        cl = pd.to_datetime(df["closed_date"], errors="coerce")
        both_valid = cd.notna() & cl.notna()
        inverted = int((cl[both_valid] < cd[both_valid]).sum())
        date_issues["closed_before_created"] = {"count": inverted}
    results["date_issues"] = date_issues

    # 4. Coordinate issues
    coord_issues: dict = {}
    for col in ["latitude", "longitude"]:
        if col in df.columns:
            numeric = pd.to_numeric(df[col], errors="coerce")
            non_numeric = int(numeric.isna().sum() - df[col].isna().sum())
            if col == "latitude":
                out_of_range = int(((numeric < 40.49) | (numeric > 40.91)).sum())
            else:
                out_of_range = int(((numeric < -74.26) | (numeric > -73.70)).sum())
            coord_issues[col] = {
                "non_numeric": max(0, non_numeric),
                "out_of_range": out_of_range,
            }
    # lat/lon swap heuristic
    if "latitude" in df.columns and "longitude" in df.columns:
        lat_num = pd.to_numeric(df["latitude"], errors="coerce")
        lon_num = pd.to_numeric(df["longitude"], errors="coerce")
        # NY lats ~40-41, lons ~-74 to -73 → if lat looks like lon, swapped
        swapped = int(((lat_num < -73) | (lon_num > 40)).sum())
        coord_issues["likely_swapped"] = {"count": swapped}
    results["coordinate_issues"] = coord_issues

    # 5. Text length anomalies
    text_cols = ["descriptor", "resolution_description", "incident_address"]
    text_issues = {}
    for col in text_cols:
        if col in df.columns:
            lengths = df[col].dropna().str.len()
            if len(lengths) > 10:
                q1, q3 = lengths.quantile(0.25), lengths.quantile(0.75)
                iqr = q3 - q1
                upper = q3 + 3 * iqr
                lower = max(0, q1 - 3 * iqr)
                outliers = int(((lengths > upper) | (lengths < lower)).sum())
                text_issues[col] = {
                    "mean_len": round(float(lengths.mean()), 1),
                    "max_len": int(lengths.max()),
                    "min_len": int(lengths.min()),
                    "outlier_count": outliers,
                }
    results["text_length_anomalies"] = text_issues

    # 6. Type issues (numeric stored as string)
    type_issues = {}
    for col in ["latitude", "longitude", "unique_key"]:
        if col in df.columns and df[col].dtype == object:
            numeric = pd.to_numeric(df[col], errors="coerce")
            non_numeric = int(numeric.isna().sum() - df[col].isna().sum())
            type_issues[col] = {
                "dtype": str(df[col].dtype),
                "non_numeric_strings": max(0, non_numeric),
            }
    results["type_issues"] = type_issues

    # 7. Cardinality / value distribution
    cat_cols = ["borough", "agency", "complaint_type", "status"]
    cardinality = {}
    for col in cat_cols:
        if col in df.columns:
            vc = df[col].value_counts(dropna=False)
            cardinality[col] = {
                "unique_values": int(df[col].nunique(dropna=True)),
                "top5": vc.head(5).to_dict(),
                "nulls": int(df[col].isna().sum()),
            }
    results["cardinality"] = cardinality

    # 8. PII heuristic
    if "descriptor" in df.columns:
        import re
        phone_re = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
        email_re = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
        desc = df["descriptor"].dropna()
        phone_hits = int(desc.str.contains(phone_re).sum())
        email_hits = int(desc.str.contains(email_re).sum())
        results["pii_heuristic"] = {
            "phone_numbers_in_descriptor": phone_hits,
            "emails_in_descriptor": email_hits,
        }

    return results


# ── report writer ─────────────────────────────────────────────────────────────

def generate_report(df: pd.DataFrame, profile: dict, output_path: str = "data_quality_report.md") -> str:
    """Generate a markdown report from profiling results."""
    n = len(df)
    lines = [
        "# NYC 311 Data Quality Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Rows analysed:** {n:,}  ",
        f"**Columns:** {len(df.columns)}  \n",
        "---\n",
        "## 1. Null Values\n",
        "| Column | Null Count | Null % |",
        "|--------|-----------|--------|",
    ]
    for col, info in profile["nulls"].items():
        lines.append(f"| {col} | {info['count']:,} | {info['pct']}% |")
    if not profile["nulls"]:
        lines.append("| — | 0 | 0% |")

    lines += [
        "\n## 2. Duplicates\n",
        f"- **Exact duplicate rows:** {profile['exact_duplicates']['count']:,} ({profile['exact_duplicates']['pct']}%)",
    ]
    if "unique_key_duplicates" in profile:
        lines.append(f"- **Duplicate unique_key values:** {profile['unique_key_duplicates']['count']:,}")

    lines += ["\n## 3. Date Issues\n"]
    di = profile["date_issues"]
    for col, info in di.items():
        if col == "closed_before_created":
            lines.append(f"- **closed_before_created:** {info['count']:,} rows")
        else:
            lines.append(f"- **{col}** — unparseable: {info['unparseable']:,}, future: {info['future_dates']:,}")

    lines += ["\n## 4. Coordinate Issues\n"]
    for col, info in profile["coordinate_issues"].items():
        if col == "likely_swapped":
            lines.append(f"- **Likely lat/lon swapped:** {info['count']:,} rows")
        else:
            lines.append(f"- **{col}** — non-numeric: {info.get('non_numeric', 0):,}, out-of-range: {info.get('out_of_range', 0):,}")

    lines += ["\n## 5. Text Length Anomalies\n",
              "| Column | Mean Len | Min | Max | Outliers |",
              "|--------|----------|-----|-----|---------|"]
    for col, info in profile["text_length_anomalies"].items():
        lines.append(f"| {col} | {info['mean_len']} | {info['min_len']} | {info['max_len']} | {info['outlier_count']:,} |")

    lines += ["\n## 6. Type Issues\n"]
    if profile["type_issues"]:
        for col, info in profile["type_issues"].items():
            lines.append(f"- **{col}:** dtype=`{info['dtype']}`, non-numeric strings: {info['non_numeric_strings']:,}")
    else:
        lines.append("No type issues detected.")

    lines += ["\n## 7. Cardinality / Value Distribution\n"]
    for col, info in profile["cardinality"].items():
        lines.append(f"\n### {col} ({info['unique_values']} unique values, {info['nulls']:,} nulls)\n")
        lines.append("| Value | Count |")
        lines.append("|-------|-------|")
        for val, cnt in list(info["top5"].items())[:5]:
            lines.append(f"| {val} | {cnt:,} |")

    lines += ["\n## 8. PII Heuristic\n"]
    if "pii_heuristic" in profile:
        p = profile["pii_heuristic"]
        lines.append(f"- Phone numbers found in `descriptor`: **{p['phone_numbers_in_descriptor']:,}**")
        lines.append(f"- Email addresses found in `descriptor`: **{p['emails_in_descriptor']:,}**")

    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {output_path}")
    return report


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _dir = os.path.dirname(os.path.abspath(__file__))
    real_csv = os.path.join(_dir, "data", "nyc_311_2023_clean.csv")
    if os.path.exists(real_csv):
        print(f"Loading REAL 2023 NYC 311 data from {real_csv} …")
        df = pd.read_csv(real_csv, low_memory=False)
    else:
        sample_path = "nyc311_sample.csv"
        if os.path.exists(sample_path):
            print(f"Loading existing sample from {sample_path} …")
            df = pd.read_csv(sample_path, low_memory=False)
        else:
            df = download_sample(limit=50_000, save_path=sample_path)

    profile = profile_dataframe(df)
    report = generate_report(df, profile, output_path=os.path.join(_dir, "real_data_quality_report.md"))
    print("\n" + "=" * 60)
    print("PROFILING COMPLETED ON REAL 2023 NYC 311 DATA")
    print(report[:2000])
    print("=" * 60)
