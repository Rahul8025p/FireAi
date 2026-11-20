"""
LLM-at-query-time tax engine for FY 2024-25.
Passes the full rule text + user data to Gemini for each query.
Falls back to HandCodedTaxEngine if LLM fails.
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from implementations.hand_coded_rules import HandCodedTaxEngine, TaxInput, TaxResult, _result_to_dict

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


TAX_RULES_TEXT = """
INDIAN INCOME TAX RULES FY 2024-25 (AY 2025-26) — SALARIED INDIVIDUALS

=== OLD REGIME ===
Standard deduction: ₹50,000
HRA exemption (if rent paid): minimum of:
  (a) HRA actually received
  (b) Actual rent paid minus 10% of basic salary
  (c) 50% of basic (metro cities: Mumbai, Delhi, Chennai, Kolkata) or 40% of basic (non-metro)
Section 80C: up to ₹1,50,000 (PF, ELSS, life insurance, PPF, etc.)
Section 80CCD(1B): additional NPS up to ₹50,000
Section 80D: medical insurance premiums
  - Self/spouse/children: up to ₹25,000 (₹50,000 if self is senior citizen ≥60)
  - Parents: up to ₹25,000 (₹50,000 if parents are senior citizens ≥60)
Section 24b: Home loan interest on self-occupied house up to ₹2,00,000

Old regime income tax slabs:
  ₹0 – ₹2,50,000: Nil
  ₹2,50,001 – ₹5,00,000: 5%
  ₹5,00,001 – ₹10,00,000: 20%
  Above ₹10,00,000: 30%

Section 87A rebate (old): full tax rebate up to ₹12,500 if taxable income ≤ ₹5,00,000

=== NEW REGIME (DEFAULT from FY 2023-24) ===
Standard deduction: ₹75,000
No other deductions allowed (no HRA, 80C, 80D, home loan interest, etc.)

New regime income tax slabs:
  ₹0 – ₹3,00,000: Nil
  ₹3,00,001 – ₹7,00,000: 5%
  ₹7,00,001 – ₹10,00,000: 10%
  ₹10,00,001 – ₹12,00,000: 15%
  ₹12,00,001 – ₹15,00,000: 20%
  Above ₹15,00,000: 30%

Section 87A rebate (new): full tax rebate up to ₹25,000 if taxable income ≤ ₹7,00,000

=== SURCHARGE (both regimes) ===
  Income ₹50L–₹1Cr: 10% of income tax
  Income ₹1Cr–₹2Cr: 15% of income tax
  Income ₹2Cr–₹5Cr: 25% of income tax
  Income >₹5Cr: 37% of income tax (new regime capped at 25%)
Marginal relief applies when surcharge causes effective tax > (income - threshold) + tax at threshold.

=== CESS ===
4% Health and Education Cess on (income tax + surcharge - rebate)

=== COMPUTATION ORDER ===
1. Gross salary
2. Subtract deductions → taxable income
3. Compute slab-wise tax
4. Apply 87A rebate (if eligible)
5. Compute surcharge with marginal relief
6. Apply 4% cess on (tax after rebate + surcharge)
7. Final tax = tax after rebate + surcharge + cess

All intermediate values rounded down (floor) to nearest rupee.
"""


@dataclass
class LLMCallStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0
    used_fallback: bool = False
    model: str = ""


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

class LLMQueryTimeTaxEngine:
    """
    Tax engine that queries Gemini LLM at runtime with the full rule text.
    Falls back to HandCodedTaxEngine if the API call fails or returns bad data.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        self._fallback = HandCodedTaxEngine()
        self._client = None
        self.last_stats: Optional[LLMCallStats] = None
        self._setup_client()

    def _setup_client(self):
        _load_env_key()
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not _GENAI_AVAILABLE:
            return
        if api_key:
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(self.model_name)

    def _build_prompt(self, inp: TaxInput) -> str:
        return f"""{TAX_RULES_TEXT}

=== USER INPUT ===
Annual salary (gross): ₹{inp.annual_salary:,}
HRA received: ₹{inp.hra_received:,}
Actual rent paid: ₹{inp.actual_rent_paid:,}
Metro city: {"Yes" if inp.is_metro else "No"}
80C investments: ₹{inp.investment_80c:,}
80CCD(1B) NPS: ₹{inp.investment_80ccd1b:,}
80D self/spouse/children: ₹{inp.medical_80d_self:,}
80D parents: ₹{inp.medical_80d_parents:,}
Parents are senior citizens: {"Yes" if inp.parents_senior_citizen else "No"}
Home loan interest: ₹{inp.home_loan_interest:,}
Age: {inp.age}

=== TASK ===
Using ONLY the rules above (FY 2024-25), compute income tax under BOTH old and new regime.
Return a JSON object with EXACTLY this structure (all values as integers, rupees):

{{
  "old_regime": {{
    "standard_deduction": <int>,
    "hra_exemption": <int>,
    "deduction_80c": <int>,
    "deduction_80ccd1b": <int>,
    "deduction_80d_self": <int>,
    "deduction_80d_parents": <int>,
    "deduction_home_loan": <int>,
    "total_deductions": <int>,
    "taxable_income": <int>,
    "gross_tax": <int>,
    "rebate_87a": <int>,
    "surcharge": <int>,
    "marginal_relief": <int>,
    "cess": <int>,
    "final_tax": <int>
  }},
  "new_regime": {{
    "standard_deduction": <int>,
    "taxable_income": <int>,
    "gross_tax": <int>,
    "rebate_87a": <int>,
    "surcharge": <int>,
    "marginal_relief": <int>,
    "cess": <int>,
    "final_tax": <int>
  }},
  "recommended_regime": "<old|new>",
  "savings": <int>,
  "recommendation_reason": "<brief explanation>"
}}

Return ONLY the JSON, no markdown fences, no extra text.
"""

    def compute(self, inp: TaxInput) -> TaxResult:
        """Compute tax via LLM. Falls back to hand-coded on failure."""
        stats = LLMCallStats(model=self.model_name)
        t0 = time.time()

        result = None
        if self._client is not None:
            try:
                prompt = self._build_prompt(inp)
                response = self._client.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0,
                        max_output_tokens=2048,
                    ),
                )
                elapsed = time.time() - t0

                # Token usage
                try:
                    usage = response.usage_metadata
                    stats.prompt_tokens = usage.prompt_token_count or 0
                    stats.completion_tokens = usage.candidates_token_count or 0
                    stats.total_tokens = usage.total_token_count or 0
                except Exception:
                    pass
                stats.latency_seconds = elapsed

                # Parse JSON
                raw = response.text.strip()
                # Strip markdown fences if present
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                data = json.loads(raw)
                result = self._dict_to_result(inp, data)

            except Exception as e:
                print(f"[LLMQueryTimeTaxEngine] LLM call failed: {e}. Using fallback.")
                stats.used_fallback = True

        if result is None:
            stats.used_fallback = True
            result = self._fallback.compute(inp)

        stats.latency_seconds = time.time() - t0
        self.last_stats = stats
        return result

    def _dict_to_result(self, inp: TaxInput, data: dict) -> TaxResult:
        """Convert LLM JSON response to TaxResult, filling gaps from hand-coded."""
        from implementations.hand_coded_rules import RegimeTaxResult, TaxResult

        old_data = data.get("old_regime", {})
        new_data = data.get("new_regime", {})

        def make_regime(d: dict, regime: str) -> RegimeTaxResult:
            return RegimeTaxResult(
                regime=regime,
                gross_salary=inp.annual_salary,
                standard_deduction=d.get("standard_deduction", 0),
                hra_exemption=d.get("hra_exemption", 0),
                deduction_80c=d.get("deduction_80c", 0),
                deduction_80ccd1b=d.get("deduction_80ccd1b", 0),
                deduction_80d_self=d.get("deduction_80d_self", 0),
                deduction_80d_parents=d.get("deduction_80d_parents", 0),
                deduction_home_loan=d.get("deduction_home_loan", 0),
                total_deductions=d.get("total_deductions", 0),
                taxable_income=d.get("taxable_income", 0),
                slab_details=[],  # LLM doesn't return slab details
                gross_tax=d.get("gross_tax", 0),
                rebate_87a=d.get("rebate_87a", 0),
                tax_after_rebate=d.get("gross_tax", 0) - d.get("rebate_87a", 0),
                surcharge_rate=0.0,
                surcharge=d.get("surcharge", 0),
                marginal_relief=d.get("marginal_relief", 0),
                surcharge_after_relief=d.get("surcharge", 0),
                cess=d.get("cess", 0),
                final_tax=d.get("final_tax", 0),
                notes=["LLM-computed result"],
            )

        old_result = make_regime(old_data, "old")
        new_result = make_regime(new_data, "new")

        return TaxResult(
            old_regime=old_result,
            new_regime=new_result,
            recommended_regime=data.get("recommended_regime", "new"),
            savings=data.get("savings", 0),
            recommendation_reason=data.get("recommendation_reason", ""),
        )

    def compute_dict(self, **kwargs) -> dict:
        inp = TaxInput(**kwargs)
        result = self.compute(inp)
        return _result_to_dict(result)

    def estimate_cost_per_1000(self) -> dict:
        """Estimate cost per 1000 requests based on last call stats."""
        if self.last_stats is None:
            return {"error": "No stats available yet. Run compute() first."}

        # Gemini 2.0 Flash pricing (approximate as of 2024)
        # Input: $0.075 per 1M tokens, Output: $0.30 per 1M tokens
        input_cost_per_1m = 0.075
        output_cost_per_1m = 0.30

        cost_per_call = (
            (self.last_stats.prompt_tokens / 1_000_000) * input_cost_per_1m +
            (self.last_stats.completion_tokens / 1_000_000) * output_cost_per_1m
        )

        return {
            "model": self.model_name,
            "tokens_per_call": {
                "prompt": self.last_stats.prompt_tokens,
                "completion": self.last_stats.completion_tokens,
                "total": self.last_stats.total_tokens,
            },
            "cost_per_call_usd": round(cost_per_call, 6),
            "cost_per_1000_requests_usd": round(cost_per_call * 1000, 4),
            "latency_seconds": round(self.last_stats.latency_seconds, 2),
            "used_fallback": self.last_stats.used_fallback,
        }
