"""
FY 2025-26 (AY 2026-27) tax engine — new regime changes only.
Extends HandCodedTaxEngine with updated slabs, standard deduction, and 87A rebate.
"""
from __future__ import annotations
from implementations.hand_coded_rules import (
    HandCodedTaxEngine, TaxInput, TaxResult, RegimeTaxResult, SlabDetail,
    _result_to_dict, _hra_exemption, _compute_surcharge,
    LIMIT_80C, LIMIT_80CCD1B, LIMIT_80D_SELF_NORMAL, LIMIT_80D_SELF_SENIOR,
    LIMIT_80D_PARENTS_NORMAL, LIMIT_80D_PARENTS_SENIOR, LIMIT_HOME_LOAN,
    OLD_STANDARD_DEDUCTION, OLD_REBATE_INCOME_LIMIT, OLD_REBATE_MAX,
)

# ─── FY 2025-26 new regime constants ─────────────────────────────────────────

FY2526_NEW_STANDARD_DEDUCTION = 75_000  # unchanged

FY2526_NEW_SLABS = [
    (0,          400_000, 0.00),
    (400_000,    800_000, 0.05),
    (800_000,  1_200_000, 0.10),
    (1_200_000, 1_600_000, 0.15),
    (1_600_000, 2_000_000, 0.20),
    (2_000_000, 2_400_000, 0.25),
    (2_400_000,  None,    0.30),
]

FY2526_NEW_REBATE_INCOME_LIMIT = 1_200_000  # ₹12L
FY2526_NEW_REBATE_MAX = 60_000              # up to ₹60,000


def _compute_fy2526_slab_tax(income: int, slabs: list[tuple]) -> tuple[int, list[SlabDetail]]:
    """Compute slab-wise tax using FY 2025-26 slabs."""
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


class HandCodedTaxEngineFY2526(HandCodedTaxEngine):
    """
    FY 2025-26 (AY 2026-27) tax engine.
    New regime slabs updated, old regime stays the same.
    New regime 87A rebate: up to ₹60,000 if taxable income ≤ ₹12L.
    """

    def compute(self, inp: TaxInput) -> TaxResult:
        old = self._compute_old_regime(inp)   # inherited — old regime unchanged
        new = self._compute_fy2526_new_regime(inp)

        if old.final_tax <= new.final_tax:
            recommended = 'old'
            savings = new.final_tax - old.final_tax
            reason = (
                f"Old regime saves ₹{savings:,} due to deductions "
                f"(80C: ₹{old.deduction_80c:,}, HRA: ₹{old.hra_exemption:,}, etc.) [FY 2025-26]"
            )
        else:
            recommended = 'new'
            savings = old.final_tax - new.final_tax
            reason = (
                f"New regime saves ₹{savings:,}; deductions under old regime "
                f"(₹{old.total_deductions:,}) do not outweigh the lower slab rates. [FY 2025-26]"
            )

        return TaxResult(
            old_regime=old,
            new_regime=new,
            recommended_regime=recommended,
            savings=savings,
            recommendation_reason=reason,
        )

    def _compute_fy2526_new_regime(self, inp: TaxInput) -> RegimeTaxResult:
        notes: list[str] = ["FY 2025-26 new regime", "Only standard deduction of ₹75,000 allowed"]

        std_ded = FY2526_NEW_STANDARD_DEDUCTION
        taxable_income = max(0, inp.annual_salary - std_ded)

        gross_tax, slab_details = _compute_fy2526_slab_tax(taxable_income, FY2526_NEW_SLABS)

        # 87A rebate: up to ₹60,000 if taxable income ≤ ₹12L
        rebate = 0
        if taxable_income <= FY2526_NEW_REBATE_INCOME_LIMIT:
            rebate = min(gross_tax, FY2526_NEW_REBATE_MAX)
            notes.append(f"87A rebate: ₹{rebate:,} (taxable ≤ ₹12L under FY 2025-26 rules)")

        tax_after_rebate = gross_tax - rebate

        # Surcharge (same thresholds as FY 2024-25)
        surcharge_rate, surcharge, marginal_relief = _compute_surcharge(
            taxable_income, tax_after_rebate, is_new_regime=True
        )

        surcharge_after_relief = surcharge
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


if __name__ == '__main__':
    import json
    engine = HandCodedTaxEngineFY2526()

    # Test: 12L salary → new regime taxable=1125000 → 0+20000+30000+3750=53750 → no rebate (>12L)?
    # Actually taxable=1200000-75000=1125000 ≤ 1200000 → rebate applies
    # slab: 0-4L=0, 4-8L: 400k*5%=20000, 8-12L: 400k*10%=40000, 12L-1125k? 1125000<1200000
    # slab: 0-400000=0, 400000-800000: 400000*5%=20000, 800000-1125000: 325000*10%=32500
    # gross=52500, taxable=1125000≤1200000 → rebate=min(52500,60000)=52500 → 0
    # cess=0, final=0

    result = engine.compute(TaxInput(annual_salary=1_275_000))
    print(f"FY 2025-26 | Salary ₹12.75L")
    print(f"  New regime taxable: {result.new_regime.taxable_income:,}")
    print(f"  New regime gross tax: {result.new_regime.gross_tax:,}")
    print(f"  New regime rebate: {result.new_regime.rebate_87a:,}")
    print(f"  New regime final: {result.new_regime.final_tax:,}")
    print(f"  Old regime final: {result.old_regime.final_tax:,}")
    print(f"  Recommendation: {result.recommended_regime}")
    print()

    # Comparison table
    print(f"{'Salary':>12} | {'FY24-25 New':>12} | {'FY25-26 New':>12} | {'FY24-25 Old':>12}")
    print("-" * 55)
    base_engine = HandCodedTaxEngine()
    for sal in [600_000, 800_000, 1_000_000, 1_200_000, 1_275_000, 1_500_000, 2_000_000, 3_000_000]:
        r24 = base_engine.compute(TaxInput(annual_salary=sal))
        r25 = engine.compute(TaxInput(annual_salary=sal))
        print(f"{sal:>12,} | {r24.new_regime.final_tax:>12,} | {r25.new_regime.final_tax:>12,} | {r24.old_regime.final_tax:>12,}")
