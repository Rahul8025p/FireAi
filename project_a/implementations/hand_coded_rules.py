"""
Hand-coded Indian Income Tax Engine for FY 2024-25 (AY 2025-26).
Covers old and new regime for salaried individuals.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class TaxInput:
    """Structured input for tax computation."""
    annual_salary: int           # Gross annual salary (CTC or gross)
    hra_received: int = 0        # HRA component received from employer
    actual_rent_paid: int = 0    # Actual rent paid per year
    is_metro: bool = False       # Metro city? (Mumbai, Delhi, Chennai, Kolkata)
    investment_80c: int = 0      # 80C investments (max 1,50,000)
    investment_80ccd1b: int = 0  # 80CCD(1B) NPS (max 50,000)
    medical_80d_self: int = 0    # 80D premium for self/spouse/children
    medical_80d_parents: int = 0 # 80D premium for parents
    parents_senior_citizen: bool = False  # Are parents senior citizens (60+)?
    home_loan_interest: int = 0  # Interest on home loan (self-occupied, max 2,00,000)
    age: int = 30                # Taxpayer's age


@dataclass
class SlabDetail:
    """Detail of tax computed for one slab."""
    slab_start: int
    slab_end: Optional[int]   # None means unlimited
    rate: float
    income_in_slab: int
    tax_in_slab: int


@dataclass
class RegimeTaxResult:
    """Full tax computation result for one regime."""
    regime: str                     # 'old' or 'new'
    gross_salary: int
    standard_deduction: int
    hra_exemption: int              # only old regime
    deduction_80c: int
    deduction_80ccd1b: int
    deduction_80d_self: int
    deduction_80d_parents: int
    deduction_home_loan: int
    total_deductions: int
    taxable_income: int
    slab_details: list[SlabDetail]
    gross_tax: int                  # tax before rebate/surcharge/cess
    rebate_87a: int
    tax_after_rebate: int
    surcharge_rate: float
    surcharge: int
    marginal_relief: int
    surcharge_after_relief: int
    cess: int
    final_tax: int
    notes: list[str] = field(default_factory=list)


@dataclass
class TaxResult:
    """Combined result with both regimes and recommendation."""
    old_regime: RegimeTaxResult
    new_regime: RegimeTaxResult
    recommended_regime: str
    savings: int
    recommendation_reason: str


# ─── constants ────────────────────────────────────────────────────────────────

OLD_STANDARD_DEDUCTION = 50_000
NEW_STANDARD_DEDUCTION = 75_000

OLD_SLABS = [
    (0,         250_000, 0.00),
    (250_000,   500_000, 0.05),
    (500_000, 1_000_000, 0.20),
    (1_000_000, None,   0.30),
]

NEW_SLABS = [
    (0,          300_000, 0.00),
    (300_000,    700_000, 0.05),
    (700_000,  1_000_000, 0.10),
    (1_000_000, 1_200_000, 0.15),
    (1_200_000, 1_500_000, 0.20),
    (1_500_000,  None,    0.30),
]

# 80C limit
LIMIT_80C = 150_000
# 80CCD(1B) limit
LIMIT_80CCD1B = 50_000
# 80D self limits
LIMIT_80D_SELF_NORMAL = 25_000
LIMIT_80D_SELF_SENIOR = 50_000   # if taxpayer is 60+
# 80D parents limits
LIMIT_80D_PARENTS_NORMAL = 25_000
LIMIT_80D_PARENTS_SENIOR = 50_000
# Home loan interest (self-occupied)
LIMIT_HOME_LOAN = 200_000

# 87A rebate
OLD_REBATE_INCOME_LIMIT = 500_000
OLD_REBATE_MAX = 12_500
NEW_REBATE_INCOME_LIMIT = 700_000
NEW_REBATE_MAX = 25_000

# Surcharge thresholds
SURCHARGE_THRESHOLDS = [
    (5_000_000,   10_000_000, 0.10),
    (10_000_000,  20_000_000, 0.15),
    (20_000_000,  50_000_000, 0.25),
    (50_000_000,  None,       0.37),
]
NEW_REGIME_SURCHARGE_CAP = 0.25  # 37% capped at 25% for new regime


# ─── helper functions ─────────────────────────────────────────────────────────

def _compute_slab_tax(income: int, slabs: list[tuple]) -> tuple[int, list[SlabDetail]]:
    """Compute tax and slab details for given income."""
    total_tax = 0
    details: list[SlabDetail] = []
    for start, end, rate in slabs:
        if income <= start:
            break
        slab_top = end if end is not None else income
        slab_income = min(income, slab_top) - start
        if slab_income <= 0:
            continue
        slab_tax = int(slab_income * rate)
        total_tax += slab_tax
        details.append(SlabDetail(
            slab_start=start,
            slab_end=end,
            rate=rate,
            income_in_slab=slab_income,
            tax_in_slab=slab_tax,
        ))
    return total_tax, details


def _compute_surcharge(gross_income: int, gross_tax: int, is_new_regime: bool) -> tuple[float, int, int]:
    """
    Returns (surcharge_rate, surcharge_amount, marginal_relief).
    Marginal relief ensures the surcharge doesn't make the taxpayer worse off
    than if they had income just at the threshold.
    """
    if gross_income <= 5_000_000:
        return 0.0, 0, 0

    # Determine applicable surcharge rate
    applicable_rate = 0.0
    threshold = 5_000_000
    for lo, hi, rate in SURCHARGE_THRESHOLDS:
        if gross_income > lo:
            applicable_rate = rate
            threshold = lo
        else:
            break

    if is_new_regime:
        applicable_rate = min(applicable_rate, NEW_REGIME_SURCHARGE_CAP)

    surcharge = int(gross_tax * applicable_rate)

    # Marginal relief: tax+surcharge at current income should not exceed
    # tax+surcharge at threshold + (income - threshold)
    # Compute tax at threshold (no surcharge at threshold)
    slabs = NEW_SLABS if is_new_regime else OLD_SLABS
    tax_at_threshold, _ = _compute_slab_tax(threshold, slabs)

    # For the threshold itself, surcharge might apply at previous bracket
    threshold_surcharge_rate = 0.0
    for lo, hi, rate in SURCHARGE_THRESHOLDS:
        if threshold > lo:
            if is_new_regime:
                threshold_surcharge_rate = min(rate, NEW_REGIME_SURCHARGE_CAP)
            else:
                threshold_surcharge_rate = rate
        else:
            break

    tax_at_threshold_with_surcharge = int(tax_at_threshold * (1 + threshold_surcharge_rate))
    max_allowed_total_tax = tax_at_threshold_with_surcharge + (gross_income - threshold)
    actual_total_tax = gross_tax + surcharge

    marginal_relief = 0
    if actual_total_tax > max_allowed_total_tax:
        marginal_relief = actual_total_tax - max_allowed_total_tax
        surcharge = max(0, surcharge - marginal_relief)

    return applicable_rate, surcharge, marginal_relief


def _hra_exemption(annual_salary: int, hra_received: int, actual_rent_paid: int, is_metro: bool) -> int:
    """
    HRA exemption = min of:
    1. HRA received
    2. Actual rent paid - 10% of basic salary
    3. 50% of basic (metro) or 40% of basic (non-metro)
    Basic salary approximated as annual_salary * 0.5 (common practice);
    or the caller can pass basic directly by using this as a utility.
    Per IT rules, 'salary' for HRA = basic + DA. We approximate basic = 50% of gross.
    """
    if actual_rent_paid == 0 or hra_received == 0:
        return 0
    basic = int(annual_salary * 0.50)
    ten_percent_basic = int(basic * 0.10)
    metro_pct = 0.50 if is_metro else 0.40
    limit_1 = hra_received
    limit_2 = max(0, actual_rent_paid - ten_percent_basic)
    limit_3 = int(basic * metro_pct)
    return min(limit_1, limit_2, limit_3)


# ─── main engine ─────────────────────────────────────────────────────────────

class HandCodedTaxEngine:
    """
    Indian Income Tax engine for FY 2024-25 (AY 2025-26).
    Covers salaried individuals under old and new tax regimes.
    """

    def compute(self, inp: TaxInput) -> TaxResult:
        old = self._compute_old_regime(inp)
        new = self._compute_new_regime(inp)

        if old.final_tax <= new.final_tax:
            recommended = 'old'
            savings = new.final_tax - old.final_tax
            reason = (
                f"Old regime saves ₹{savings:,} due to deductions "
                f"(80C: ₹{old.deduction_80c:,}, HRA: ₹{old.hra_exemption:,}, "
                f"80D: ₹{old.deduction_80d_self + old.deduction_80d_parents:,}, etc.)"
            )
        else:
            recommended = 'new'
            savings = old.final_tax - new.final_tax
            reason = (
                f"New regime saves ₹{savings:,}; deductions under old regime "
                f"(₹{old.total_deductions:,}) do not outweigh the lower slab rates."
            )

        return TaxResult(
            old_regime=old,
            new_regime=new,
            recommended_regime=recommended,
            savings=savings,
            recommendation_reason=reason,
        )

    # ── old regime ────────────────────────────────────────────────────────────

    def _compute_old_regime(self, inp: TaxInput) -> RegimeTaxResult:
        notes: list[str] = []

        # Standard deduction
        std_ded = OLD_STANDARD_DEDUCTION

        # HRA exemption (old regime only)
        hra_exempt = _hra_exemption(
            inp.annual_salary, inp.hra_received, inp.actual_rent_paid, inp.is_metro
        )

        # 80C (capped at 1,50,000)
        ded_80c = min(inp.investment_80c, LIMIT_80C)

        # 80CCD(1B) (capped at 50,000)
        ded_80ccd1b = min(inp.investment_80ccd1b, LIMIT_80CCD1B)

        # 80D self
        self_80d_limit = LIMIT_80D_SELF_SENIOR if inp.age >= 60 else LIMIT_80D_SELF_NORMAL
        ded_80d_self = min(inp.medical_80d_self, self_80d_limit)

        # 80D parents
        parents_80d_limit = LIMIT_80D_PARENTS_SENIOR if inp.parents_senior_citizen else LIMIT_80D_PARENTS_NORMAL
        ded_80d_parents = min(inp.medical_80d_parents, parents_80d_limit)

        # Home loan interest (Section 24b, capped at 2L for self-occupied)
        ded_home_loan = min(inp.home_loan_interest, LIMIT_HOME_LOAN)

        total_deductions = (
            std_ded + hra_exempt + ded_80c + ded_80ccd1b +
            ded_80d_self + ded_80d_parents + ded_home_loan
        )

        taxable_income = max(0, inp.annual_salary - total_deductions)

        # Slab tax
        gross_tax, slab_details = _compute_slab_tax(taxable_income, OLD_SLABS)

        # 87A rebate
        rebate = 0
        if taxable_income <= OLD_REBATE_INCOME_LIMIT:
            rebate = min(gross_tax, OLD_REBATE_MAX)
            notes.append(f"87A rebate applied: ₹{rebate:,} (taxable income ≤ ₹5L)")

        tax_after_rebate = gross_tax - rebate

        # Surcharge (on gross income = taxable income for salaried)
        surcharge_rate, surcharge, marginal_relief = _compute_surcharge(
            taxable_income, tax_after_rebate, is_new_regime=False
        )

        surcharge_after_relief = surcharge

        # Cess: 4% on (tax_after_rebate + surcharge)
        cess = int((tax_after_rebate + surcharge_after_relief) * 0.04)

        final_tax = tax_after_rebate + surcharge_after_relief + cess

        return RegimeTaxResult(
            regime='old',
            gross_salary=inp.annual_salary,
            standard_deduction=std_ded,
            hra_exemption=hra_exempt,
            deduction_80c=ded_80c,
            deduction_80ccd1b=ded_80ccd1b,
            deduction_80d_self=ded_80d_self,
            deduction_80d_parents=ded_80d_parents,
            deduction_home_loan=ded_home_loan,
            total_deductions=total_deductions,
            taxable_income=taxable_income,
            slab_details=slab_details,
            gross_tax=gross_tax,
            rebate_87a=rebate,
            tax_after_rebate=tax_after_rebate,
            surcharge_rate=surcharge_rate,
            surcharge=surcharge,
            marginal_relief=marginal_relief,
            surcharge_after_relief=surcharge_after_relief,
            cess=cess,
            final_tax=final_tax,
            notes=notes,
        )

    # ── new regime ────────────────────────────────────────────────────────────

    def _compute_new_regime(self, inp: TaxInput) -> RegimeTaxResult:
        notes: list[str] = []

        # Only standard deduction in new regime
        std_ded = NEW_STANDARD_DEDUCTION
        notes.append("New regime: only standard deduction of ₹75,000 allowed")

        taxable_income = max(0, inp.annual_salary - std_ded)

        # Slab tax
        gross_tax, slab_details = _compute_slab_tax(taxable_income, NEW_SLABS)

        # 87A rebate (with marginal relief under Section 87A proviso)
        rebate = 0
        if taxable_income <= NEW_REBATE_INCOME_LIMIT:
            rebate = min(gross_tax, NEW_REBATE_MAX)
            notes.append(f"87A rebate applied: ₹{rebate:,} (taxable income ≤ ₹7L)")
        elif taxable_income > 700_000 and gross_tax > (taxable_income - 700_000):
            rebate = gross_tax - (taxable_income - 700_000)
            notes.append(f"87A marginal relief rebate applied: ₹{rebate:,} (tax capped to excess over ₹7L)")

        tax_after_rebate = gross_tax - rebate

        # Surcharge
        surcharge_rate, surcharge, marginal_relief = _compute_surcharge(
            taxable_income, tax_after_rebate, is_new_regime=True
        )

        surcharge_after_relief = surcharge

        # Cess: 4% on (tax_after_rebate + surcharge)
        cess = int((tax_after_rebate + surcharge_after_relief) * 0.04)

        final_tax = tax_after_rebate + surcharge_after_relief + cess

        return RegimeTaxResult(
            regime='new',
            gross_salary=inp.annual_salary,
            standard_deduction=std_ded,
            hra_exemption=0,
            deduction_80c=0,
            deduction_80ccd1b=0,
            deduction_80d_self=0,
            deduction_80d_parents=0,
            deduction_home_loan=0,
            total_deductions=std_ded,
            taxable_income=taxable_income,
            slab_details=slab_details,
            gross_tax=gross_tax,
            rebate_87a=rebate,
            tax_after_rebate=tax_after_rebate,
            surcharge_rate=surcharge_rate,
            surcharge=surcharge,
            marginal_relief=marginal_relief,
            surcharge_after_relief=surcharge_after_relief,
            cess=cess,
            final_tax=final_tax,
            notes=notes,
        )

    def compute_dict(self, **kwargs) -> dict:
        """
        Convenience method: accepts keyword arguments matching TaxInput fields,
        returns result as a plain dict.
        """
        inp = TaxInput(**kwargs)
        result = self.compute(inp)
        return _result_to_dict(result)


def _result_to_dict(result: TaxResult) -> dict:
    """Convert TaxResult to plain dict for JSON serialisation."""
    def regime_to_dict(r: RegimeTaxResult) -> dict:
        return {
            'regime': r.regime,
            'gross_salary': r.gross_salary,
            'standard_deduction': r.standard_deduction,
            'hra_exemption': r.hra_exemption,
            'deduction_80c': r.deduction_80c,
            'deduction_80ccd1b': r.deduction_80ccd1b,
            'deduction_80d_self': r.deduction_80d_self,
            'deduction_80d_parents': r.deduction_80d_parents,
            'deduction_home_loan': r.deduction_home_loan,
            'total_deductions': r.total_deductions,
            'taxable_income': r.taxable_income,
            'slab_details': [
                {
                    'slab_start': s.slab_start,
                    'slab_end': s.slab_end,
                    'rate': s.rate,
                    'income_in_slab': s.income_in_slab,
                    'tax_in_slab': s.tax_in_slab,
                }
                for s in r.slab_details
            ],
            'gross_tax': r.gross_tax,
            'rebate_87a': r.rebate_87a,
            'tax_after_rebate': r.tax_after_rebate,
            'surcharge_rate': r.surcharge_rate,
            'surcharge': r.surcharge,
            'marginal_relief': r.marginal_relief,
            'surcharge_after_relief': r.surcharge_after_relief,
            'cess': r.cess,
            'final_tax': r.final_tax,
            'notes': r.notes,
        }

    return {
        'old_regime': regime_to_dict(result.old_regime),
        'new_regime': regime_to_dict(result.new_regime),
        'recommended_regime': result.recommended_regime,
        'savings': result.savings,
        'recommendation_reason': result.recommendation_reason,
    }


if __name__ == '__main__':
    engine = HandCodedTaxEngine()
    # Sample: 12 LPA, no deductions
    result = engine.compute(TaxInput(annual_salary=1_200_000))
    import json, dataclasses
    print(json.dumps(_result_to_dict(result), indent=2))
