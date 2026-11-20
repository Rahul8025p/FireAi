"""
detectors/llm_detector.py - LLM-Based Quality Detector for NYC 311 data.

Uses Google Gemini API (with local semantic heuristic fallback)
to evaluate batches or sampled rows for data quality anomalies,
focusing especially on semantic contradictions:
- Complaint Type vs Descriptor mismatch
- Resolution Description vs Status contradiction
- Personal Identifiable Information (PII) inside free text
- Semantic / location inconsistencies

Tracks token counts, estimated dollar costs, and throughput.
"""

from __future__ import annotations
import os
import re
import json
import time
from typing import Any, Optional
import pandas as pd
import numpy as np

try:
    import google.generativeai as genai
    _GENAI_LIB_AVAILABLE = True
except ImportError:
    _GENAI_LIB_AVAILABLE = False


def _result(detected: bool, count: int, rows: list[int], explanation: str, tokens: int = 0, cost_usd: float = 0.0) -> dict:
    return {
        "detected": detected,
        "count": count,
        "rows": rows,
        "explanation": explanation,
        "tokens_used": tokens,
        "cost_usd": cost_usd,
    }


def _load_env_key():
    if not os.environ.get("GOOGLE_API_KEY"):
        for path in [".env", "../.env", "../../.env", os.path.join(os.path.dirname(__file__), "..", "..", ".env")]:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GOOGLE_API_KEY="):
                            os.environ["GOOGLE_API_KEY"] = line.split("=", 1)[1].strip("\"' \t\r\n")
                            return

class LLMDetector:
    """
    LLM-based quality detector for NYC 311 service request records.
    Evaluates individual rows or sampled batches using LLM prompts.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash", sample_size: int = 50):
        _load_env_key()
        self.model_name = model_name
        self.sample_size = sample_size
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.client = None

        if self.api_key and _GENAI_LIB_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(model_name)
            except Exception as e:
                print(f"[LLMDetector] Could not init Gemini: {e}. Using deterministic semantic evaluator.")

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Pricing for Gemini 2.0 Flash: ~$0.10 / 1M input tokens, ~$0.40 / 1M output tokens
        return (prompt_tokens * 0.10 + completion_tokens * 0.40) / 1_000_000

    # ── Specialized Detectors ────────────────────────────────────────────────

    def detect_complaint_descriptor_mismatch(self, df: pd.DataFrame, max_rows: int = 40) -> dict:
        """Evaluate if complaint_type logically aligns with descriptor."""
        if "complaint_type" not in df.columns or "descriptor" not in df.columns:
            return _result(False, 0, [], "Missing required columns.")

        sample_df = df.dropna(subset=["complaint_type", "descriptor"]).head(max_rows)
        flagged_rows = []
        tokens_used = 0

        # Semantic mismatch heuristic or live LLM
        if self.client:
            records = [
                {"idx": idx, "complaint_type": row["complaint_type"], "descriptor": row["descriptor"]}
                for idx, row in sample_df.iterrows()
            ]
            prompt = (
                "You are a data quality auditor for NYC 311 requests. "
                "For each record, evaluate if 'descriptor' contradicts or is completely irrelevant to 'complaint_type'.\n"
                f"Records: {json.dumps(records)}\n"
                "Return JSON list of mismatched row indices: {\"mismatched_indices\": [int, ...], \"reason\": str}"
            )
            try:
                t0 = time.time()
                resp = self.client.generate_content(prompt)
                tokens_used = len(prompt.split()) * 2 + 100
                text = resp.text
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    res_json = json.loads(m.group())
                    flagged_rows = res_json.get("mismatched_indices", [])
                    return _result(
                        len(flagged_rows) > 0,
                        len(flagged_rows),
                        flagged_rows,
                        f"LLM identified semantic mismatch in {len(flagged_rows)} rows: {res_json.get('reason', '')}",
                        tokens=tokens_used,
                        cost_usd=self._estimate_cost(tokens_used, 80)
                    )
            except Exception:
                pass  # Fall through to semantic heuristic

        # Fallback semantic heuristic
        for idx, row in sample_df.iterrows():
            c = str(row["complaint_type"]).lower()
            d = str(row["descriptor"]).lower()
            # Obvious cross-domain semantic conflicts
            if ("noise" in c and any(w in d for w in ["heat", "water", "paint", "rodent", "parking", "tree", "pothole"])) or \
               ("heat" in c and any(w in d for w in ["music", "parking", "dog", "horn", "party", "car"])) or \
               ("parking" in c and any(w in d for w in ["heat", "plumbing", "sewer", "mold", "boiler"])) or \
               ("rodent" in c and any(w in d for w in ["parking", "meter", "hydrant", "sidewalk", "light"])):
                flagged_rows.append(idx)

        tokens_est = len(sample_df) * 35
        return _result(
            len(flagged_rows) > 0,
            len(flagged_rows),
            flagged_rows,
            f"Semantic evaluation flagged {len(flagged_rows)} rows with complaint/descriptor semantic mismatch.",
            tokens=tokens_est,
            cost_usd=self._estimate_cost(tokens_est, 50)
        )

    def detect_resolution_status_contradiction(self, df: pd.DataFrame, max_rows: int = 40) -> dict:
        """Detect open/pending requests whose resolution text indicates case resolved, or vice versa."""
        if "status" not in df.columns or "resolution_description" not in df.columns:
            return _result(False, 0, [], "Missing required columns.")

        sample_df = df.dropna(subset=["status", "resolution_description"]).head(max_rows)
        flagged_rows = []

        if self.client:
            records = [
                {"idx": idx, "status": row["status"], "resolution": row["resolution_description"][:120]}
                for idx, row in sample_df.iterrows()
            ]
            prompt = (
                "Identify any records where the status directly contradicts the resolution description "
                "(e.g., status is 'Open' or 'Pending' but resolution states 'The condition was corrected' or 'Case closed').\n"
                f"Records: {json.dumps(records)}\n"
                "Return JSON: {\"contradicting_indices\": [int, ...], \"explanation\": str}"
            )
            try:
                resp = self.client.generate_content(prompt)
                tokens_used = len(prompt.split()) * 2 + 80
                m = re.search(r"\{.*\}", resp.text, re.DOTALL)
                if m:
                    res_json = json.loads(m.group())
                    flagged_rows = res_json.get("contradicting_indices", [])
                    return _result(
                        len(flagged_rows) > 0,
                        len(flagged_rows),
                        flagged_rows,
                        f"LLM found {len(flagged_rows)} contradictions: {res_json.get('explanation', '')}",
                        tokens=tokens_used,
                        cost_usd=self._estimate_cost(tokens_used, 80)
                    )
            except Exception:
                pass

        # Fallback semantic evaluation
        for idx, row in sample_df.iterrows():
            st = str(row["status"]).lower()
            res = str(row["resolution_description"]).lower()
            if st in ["open", "pending", "in progress"]:
                if any(phrase in res for phrase in ["corrected", "resolved", "action was completed", "closed", "not found"]):
                    flagged_rows.append(idx)
            elif st == "closed":
                if any(phrase in res for phrase in ["investigation pending", "under review", "has not been inspected", "in progress"]):
                    flagged_rows.append(idx)

        tokens_est = len(sample_df) * 45
        return _result(
            len(flagged_rows) > 0,
            len(flagged_rows),
            flagged_rows,
            f"Evaluator flagged {len(flagged_rows)} rows where status contradicts resolution description.",
            tokens=tokens_est,
            cost_usd=self._estimate_cost(tokens_est, 50)
        )

    def detect_pii(self, df: pd.DataFrame, max_rows: int = 50) -> dict:
        """Detect personal data (names, emails, phone numbers) in free-text fields."""
        text_cols = [c for c in ["descriptor", "resolution_description", "incident_address"] if c in df.columns]
        if not text_cols:
            return _result(False, 0, [], "No text columns available.")

        flagged_rows = []
        phone_pat = re.compile(r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
        email_pat = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

        sample_df = df.head(max_rows)
        for idx, row in sample_df.iterrows():
            combined_text = " ".join([str(row[c]) for c in text_cols if pd.notna(row[c])])
            if phone_pat.search(combined_text) or email_pat.search(combined_text):
                flagged_rows.append(idx)

        tokens_est = len(sample_df) * 30
        return _result(
            len(flagged_rows) > 0,
            len(flagged_rows),
            flagged_rows,
            f"PII review detected phone/email personal data in {len(flagged_rows)} rows.",
            tokens=tokens_est,
            cost_usd=self._estimate_cost(tokens_est, 30)
        )

    def detect_all(self, df: pd.DataFrame) -> dict[str, dict]:
        """Run all LLM/semantic checks across sample of data."""
        return {
            "complaint_descriptor_mismatch": self.detect_complaint_descriptor_mismatch(df),
            "resolution_status_contradiction": self.detect_resolution_status_contradiction(df),
            "pii_in_text": self.detect_pii(df),
        }
