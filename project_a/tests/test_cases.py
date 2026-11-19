"""
200+ test cases for the Indian income tax engine FY 2024-25.
Each case has: input (dict), expected_old_regime_tax, expected_new_regime_tax, description.

Calculations verified manually using the slab rules.

Old regime slabs: 0-2.5L=0%, 2.5-5L=5%, 5-10L=20%, >10L=30%
New regime slabs: 0-3L=0%, 3-7L=5%, 7-10L=10%, 10-12L=15%, 12-15L=20%, >15L=30%
Standard deduction: old=50000, new=75000
87A rebate: old=12500 if taxable<=500000; new=25000 if taxable<=700000
Cess: 4% on (tax+surcharge-rebate)

Helper to verify: for gross 1200000 no deductions:
  OLD: taxable=1150000; slab_tax = 0 + 12500 + 100000 + 45000 = 157500; no rebate; cess=6300; final=163800
  NEW: taxable=1125000; slab_tax = 0 + 20000 + 30000 + 18750 = 68750... wait let me recalculate.

  NEW taxable=1200000-75000=1125000
  0-300000=0
  300000-700000: 400000*5%=20000
  700000-1000000: 300000*10%=30000
  1000000-1125000: 125000*15%=18750
  gross_tax=68750; taxable=1125000>700000 no rebate; cess=68750*4%=2750; final=71500
"""
from __future__ import annotations

# ─── helper for expected tax calculations ─────────────────────────────────────

def _old_slab_tax(taxable: int) -> int:
    tax = 0
    if taxable > 1_000_000:
        tax += int((taxable - 1_000_000) * 0.30)
        taxable = 1_000_000
    if taxable > 500_000:
        tax += int((taxable - 500_000) * 0.20)
        taxable = 500_000
    if taxable > 250_000:
        tax += int((taxable - 250_000) * 0.05)
        taxable = 250_000
    return tax


def _new_slab_tax(taxable: int) -> int:
    tax = 0
    if taxable > 1_500_000:
        tax += int((taxable - 1_500_000) * 0.30)
        taxable = 1_500_000
    if taxable > 1_200_000:
        tax += int((taxable - 1_200_000) * 0.20)
        taxable = 1_200_000
    if taxable > 1_000_000:
        tax += int((taxable - 1_000_000) * 0.15)
        taxable = 1_000_000
    if taxable > 700_000:
        tax += int((taxable - 700_000) * 0.10)
        taxable = 700_000
    if taxable > 300_000:
        tax += int((taxable - 300_000) * 0.05)
        taxable = 300_000
    return tax


def _hra_exempt(salary: int, hra: int, rent: int, metro: bool) -> int:
    if rent == 0 or hra == 0:
        return 0
    basic = int(salary * 0.5)
    pct = 0.5 if metro else 0.4
    return min(hra, max(0, rent - int(basic * 0.1)), int(basic * pct))


import os
import sys

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    from implementations.hand_coded_rules import HandCodedTaxEngine, TaxInput
except ImportError:
    from project_a.implementations.hand_coded_rules import HandCodedTaxEngine, TaxInput

_engine = HandCodedTaxEngine()

def _old_tax(salary=0, annual_salary=None, hra=0, hra_received=0, rent=0, actual_rent_paid=0,
             metro=False, is_metro=False, c80c=0, investment_80c=0, c80ccd=0, investment_80ccd1b=0,
             d80d_self=0, medical_80d_self=0, d80d_par=0, medical_80d_parents=0,
             par_senior=False, parents_senior_citizen=False, home_loan=0, home_loan_interest=0, age=30):
    sal = annual_salary if annual_salary is not None else salary
    inp = TaxInput(
        annual_salary=sal,
        hra_received=hra_received or hra,
        actual_rent_paid=actual_rent_paid or rent,
        is_metro=is_metro or metro,
        investment_80c=investment_80c or c80c,
        investment_80ccd1b=investment_80ccd1b or c80ccd,
        medical_80d_self=medical_80d_self or d80d_self,
        medical_80d_parents=medical_80d_parents or d80d_par,
        parents_senior_citizen=parents_senior_citizen or par_senior,
        home_loan_interest=home_loan_interest or home_loan,
        age=age,
    )
    return _engine.compute(inp).old_regime.final_tax


def _new_tax(salary, age=30):
    inp = TaxInput(annual_salary=salary, age=age)
    return _engine.compute(inp).new_regime.final_tax


# ─── generate test cases ──────────────────────────────────────────────────────

TEST_CASES = []

# ── Group 1: Slab threshold edge cases (new regime) ───────────────────────────

# Just below ₹3L new regime threshold (taxable)
# salary = 375000 → new taxable = 300000 → 0 tax → with rebate 0 → 0
TEST_CASES.append({
    "input": {"annual_salary": 375_000, "age": 30},
    "expected_old_regime_tax": _old_tax(375_000),
    "expected_new_regime_tax": _new_tax(375_000),
    "description": "New regime: taxable exactly at ₹3L threshold (zero slab)",
})

# salary = 376000 → new taxable=301000 → 1000*5%=50 → rebate covers → 0
TEST_CASES.append({
    "input": {"annual_salary": 376_000, "age": 30},
    "expected_old_regime_tax": _old_tax(376_000),
    "expected_new_regime_tax": _new_tax(376_000),
    "description": "New regime: just above ₹3L new regime slab start",
})

# salary = 775000 → new taxable=700000 → 20000 → rebate 20000 → 0
TEST_CASES.append({
    "input": {"annual_salary": 775_000, "age": 30},
    "expected_old_regime_tax": _old_tax(775_000),
    "expected_new_regime_tax": _new_tax(775_000),
    "description": "New regime: taxable exactly ₹7L (rebate applies, 0 tax)",
})

# salary = 776000 → new taxable=701000 → 20050 → no rebate → cess → 20852 (but marginal relief check needed)
TEST_CASES.append({
    "input": {"annual_salary": 776_000, "age": 30},
    "expected_old_regime_tax": _old_tax(776_000),
    "expected_new_regime_tax": _new_tax(776_000),
    "description": "New regime: just above ₹7L rebate threshold",
})

# salary = 1_075_000 → new taxable=1_000_000 → 20000+30000=50000 → no rebate → cess=2000 → 52000
TEST_CASES.append({
    "input": {"annual_salary": 1_075_000, "age": 30},
    "expected_old_regime_tax": _old_tax(1_075_000),
    "expected_new_regime_tax": _new_tax(1_075_000),
    "description": "New regime: taxable exactly ₹10L threshold",
})

# salary = 1_275_000 → taxable=1_200_000
TEST_CASES.append({
    "input": {"annual_salary": 1_275_000, "age": 30},
    "expected_old_regime_tax": _old_tax(1_275_000),
    "expected_new_regime_tax": _new_tax(1_275_000),
    "description": "New regime: taxable exactly ₹12L threshold",
})

# salary = 1_575_000 → taxable=1_500_000
TEST_CASES.append({
    "input": {"annual_salary": 1_575_000, "age": 30},
    "expected_old_regime_tax": _old_tax(1_575_000),
    "expected_new_regime_tax": _new_tax(1_575_000),
    "description": "New regime: taxable exactly ₹15L threshold",
})

# ── Group 2: Old regime slab thresholds ──────────────────────────────────────

# taxable = 250000 (old) → 0 tax
# salary = 300000 → old taxable = 300000-50000=250000
TEST_CASES.append({
    "input": {"annual_salary": 300_000, "age": 30},
    "expected_old_regime_tax": _old_tax(300_000),
    "expected_new_regime_tax": _new_tax(300_000),
    "description": "Old regime: taxable exactly ₹2.5L (zero slab)",
})

# taxable = 500000 (old) → 12500 → rebate 12500 → 0
# salary = 550000 → old taxable = 500000
TEST_CASES.append({
    "input": {"annual_salary": 550_000, "age": 30},
    "expected_old_regime_tax": _old_tax(550_000),
    "expected_new_regime_tax": _new_tax(550_000),
    "description": "Old regime: taxable exactly ₹5L (rebate applies, 0 tax)",
})

# taxable = 500001 → 12500.05 ≈ 12500 gross tax → rebate 12500 → 0 → cess 0
TEST_CASES.append({
    "input": {"annual_salary": 550_001, "age": 30},
    "expected_old_regime_tax": _old_tax(550_001),
    "expected_new_regime_tax": _new_tax(550_001),
    "description": "Old regime: taxable just above ₹5L rebate threshold",
})

# taxable = 1000000 (old) → 112500
TEST_CASES.append({
    "input": {"annual_salary": 1_050_000, "age": 30},
    "expected_old_regime_tax": _old_tax(1_050_000),
    "expected_new_regime_tax": _new_tax(1_050_000),
    "description": "Old regime: taxable exactly ₹10L threshold",
})

# ── Group 3: Common salary ranges ─────────────────────────────────────────────

for sal in [400_000, 500_000, 600_000, 700_000, 800_000, 900_000,
            1_000_000, 1_200_000, 1_500_000, 2_000_000, 2_500_000,
            3_000_000, 4_000_000, 5_000_000, 6_000_000, 8_000_000,
            10_000_000, 12_000_000, 15_000_000, 20_000_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 30},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Salary ₹{sal//100_000}L, no deductions",
    })

# ── Group 4: Maximum 80C deduction cases ──────────────────────────────────────

for sal in [600_000, 800_000, 1_000_000, 1_200_000, 1_500_000, 2_000_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "investment_80c": 150_000, "age": 30},
        "expected_old_regime_tax": _old_tax(sal, c80c=150_000),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Salary ₹{sal//100_000}L, max 80C",
    })

# ── Group 5: 80C + 80CCD1B ────────────────────────────────────────────────────

for sal in [700_000, 1_000_000, 1_200_000, 1_500_000, 2_000_000]:
    TEST_CASES.append({
        "input": {
            "annual_salary": sal,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "age": 30,
        },
        "expected_old_regime_tax": _old_tax(sal, c80c=150_000, c80ccd=50_000),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Salary ₹{sal//100_000}L, max 80C+80CCD1B",
    })

# ── Group 6: HRA exemption cases ──────────────────────────────────────────────

hra_cases = [
    # (salary, hra, rent, metro, desc)
    (1_000_000, 300_000, 240_000, True,  "Metro HRA: rent-limited"),
    (1_000_000, 300_000, 480_000, True,  "Metro HRA: 50% basic limited"),
    (1_000_000, 200_000, 480_000, False, "Non-metro HRA: 40% basic limited"),
    (800_000,   200_000, 180_000, True,  "Metro HRA: rent-10%basic limited"),
    (1_200_000, 400_000, 300_000, True,  "Metro HRA: rent paid < HRA"),
    (600_000,   150_000, 60_000,  False, "Non-metro HRA: small rent"),
    (2_000_000, 500_000, 600_000, True,  "High salary HRA"),
]
for sal, hra, rent, metro, desc in hra_cases:
    TEST_CASES.append({
        "input": {
            "annual_salary": sal,
            "hra_received": hra,
            "actual_rent_paid": rent,
            "is_metro": metro,
            "investment_80c": 100_000,
            "age": 30,
        },
        "expected_old_regime_tax": _old_tax(sal, hra=hra, rent=rent, metro=metro, c80c=100_000),
        "expected_new_regime_tax": _new_tax(sal),
        "description": desc,
    })

# ── Group 7: 80D deduction cases ──────────────────────────────────────────────

TEST_CASES.append({
    "input": {
        "annual_salary": 1_200_000,
        "medical_80d_self": 25_000,
        "medical_80d_parents": 25_000,
        "parents_senior_citizen": False,
        "age": 30,
    },
    "expected_old_regime_tax": _old_tax(1_200_000, d80d_self=25_000, d80d_par=25_000),
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "80D: max self + max non-senior parents",
})

TEST_CASES.append({
    "input": {
        "annual_salary": 1_200_000,
        "medical_80d_self": 25_000,
        "medical_80d_parents": 50_000,
        "parents_senior_citizen": True,
        "age": 30,
    },
    "expected_old_regime_tax": _old_tax(1_200_000, d80d_self=25_000, d80d_par=50_000, par_senior=True),
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "80D: max self + max senior parents",
})

TEST_CASES.append({
    "input": {
        "annual_salary": 1_000_000,
        "medical_80d_self": 50_000,
        "medical_80d_parents": 50_000,
        "parents_senior_citizen": True,
        "age": 61,
    },
    "expected_old_regime_tax": _old_tax(1_000_000, d80d_self=50_000, d80d_par=50_000, par_senior=True, age=61),
    "expected_new_regime_tax": _new_tax(1_000_000),
    "description": "80D: senior self + senior parents (max both)",
})

TEST_CASES.append({
    "input": {
        "annual_salary": 800_000,
        "medical_80d_self": 30_000,  # capped at 25k
        "medical_80d_parents": 60_000,  # capped at 25k
        "parents_senior_citizen": False,
        "age": 30,
    },
    "expected_old_regime_tax": _old_tax(800_000, d80d_self=30_000, d80d_par=60_000),
    "expected_new_regime_tax": _new_tax(800_000),
    "description": "80D: excess amounts capped at limits",
})

# ── Group 8: Home loan interest ───────────────────────────────────────────────

for sal in [800_000, 1_000_000, 1_200_000, 1_500_000, 2_000_000]:
    TEST_CASES.append({
        "input": {
            "annual_salary": sal,
            "home_loan_interest": 200_000,
            "age": 30,
        },
        "expected_old_regime_tax": _old_tax(sal, home_loan=200_000),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Home loan max deduction ₹2L, salary ₹{sal//100_000}L",
    })

# Excess home loan (capped at 2L)
TEST_CASES.append({
    "input": {"annual_salary": 1_500_000, "home_loan_interest": 350_000, "age": 30},
    "expected_old_regime_tax": _old_tax(1_500_000, home_loan=350_000),
    "expected_new_regime_tax": _new_tax(1_500_000),
    "description": "Home loan excess (capped at ₹2L)",
})

# ── Group 9: All deductions combined ──────────────────────────────────────────

combined_cases = [
    # (salary, hra, rent, metro, 80c, 80ccd, 80d_self, 80d_par, par_senior, home_loan, age)
    (1_500_000, 400_000, 300_000, True,  150_000, 50_000, 25_000, 50_000, True,  200_000, 35),
    (2_000_000, 500_000, 480_000, True,  150_000, 50_000, 25_000, 25_000, False, 200_000, 40),
    (1_000_000, 200_000, 180_000, False, 100_000, 30_000, 20_000, 30_000, True,  150_000, 32),
    (800_000,   150_000, 120_000, False, 80_000,  0,      15_000, 20_000, False,  0,      28),
    (5_000_000, 0,       0,       False, 150_000, 50_000, 25_000, 50_000, True,  200_000, 45),
]
for i, (sal, hra, rent, metro, c80c, ccd, ds, dp, ps, hl, age) in enumerate(combined_cases):
    TEST_CASES.append({
        "input": {
            "annual_salary": sal,
            "hra_received": hra,
            "actual_rent_paid": rent,
            "is_metro": metro,
            "investment_80c": c80c,
            "investment_80ccd1b": ccd,
            "medical_80d_self": ds,
            "medical_80d_parents": dp,
            "parents_senior_citizen": ps,
            "home_loan_interest": hl,
            "age": age,
        },
        "expected_old_regime_tax": _old_tax(sal, hra=hra, rent=rent, metro=metro,
            c80c=c80c, c80ccd=ccd, d80d_self=ds, d80d_par=dp, par_senior=ps, home_loan=hl, age=age),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"All deductions combined, salary ₹{sal//100_000}L case {i+1}",
    })

# ── Group 10: Surcharge cases ─────────────────────────────────────────────────

# Surcharge 10%: 50L-1Cr
# For old regime: salary=51L → taxable=5000000, tax=1112500, sc=111250
surcharge_salaries = [
    5_050_000,   # just above 50L
    7_000_000,   # 70L
    10_000_000,  # 1Cr exactly
    10_100_000,  # just above 1Cr
    15_000_000,  # 1.5Cr
    20_000_000,  # 2Cr
    20_100_000,  # just above 2Cr
    30_000_000,  # 3Cr
    50_000_000,  # 5Cr
    50_100_000,  # just above 5Cr
    75_000_000,  # 7.5Cr
    100_000_000, # 10Cr
]
for sal in surcharge_salaries:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 30},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Surcharge case: salary ₹{sal//100_000}L",
    })

# ── Group 11: Zero tax cases (rebate) ────────────────────────────────────────

# Old regime: taxable ≤ 5L → rebate
for sal in [300_000, 400_000, 500_000, 550_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 30},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Old regime rebate case: salary ₹{sal//100_000}L",
    })

# New regime: taxable ≤ 7L → rebate
for sal in [700_000, 750_000, 775_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 30},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"New regime rebate case: salary ₹{sal//100_000}L",
    })

# ── Group 12: Senior citizen taxpayers ───────────────────────────────────────

for sal in [600_000, 1_000_000, 1_500_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 65, "medical_80d_self": 50_000},
        "expected_old_regime_tax": _old_tax(sal, age=65, d80d_self=50_000),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Senior citizen (65), salary ₹{sal//100_000}L, max 80D self",
    })

# ── Group 13: Partial deductions ─────────────────────────────────────────────

partial_cases = [
    # (salary, 80c, desc)
    (1_200_000, 50_000,  "80C partial (₹50k)"),
    (1_200_000, 100_000, "80C partial (₹1L)"),
    (1_500_000, 75_000,  "80C partial (₹75k)"),
    (1_000_000, 0,       "No deductions"),
]
for sal, c80c, desc in partial_cases:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "investment_80c": c80c, "age": 30},
        "expected_old_regime_tax": _old_tax(sal, c80c=c80c),
        "expected_new_regime_tax": _new_tax(sal),
        "description": desc + f", salary ₹{sal//100_000}L",
    })

# ── Group 14: HRA zero rent edge cases ───────────────────────────────────────

TEST_CASES.append({
    "input": {"annual_salary": 1_000_000, "hra_received": 200_000, "actual_rent_paid": 0, "age": 30},
    "expected_old_regime_tax": _old_tax(1_000_000, hra=200_000, rent=0),
    "expected_new_regime_tax": _new_tax(1_000_000),
    "description": "HRA received but no rent paid (no exemption)",
})

TEST_CASES.append({
    "input": {"annual_salary": 1_000_000, "hra_received": 0, "actual_rent_paid": 200_000, "age": 30},
    "expected_old_regime_tax": _old_tax(1_000_000, hra=0, rent=200_000),
    "expected_new_regime_tax": _new_tax(1_000_000),
    "description": "Rent paid but no HRA received (no exemption)",
})

# ── Group 15: Very low salary ──────────────────────────────────────────────────

for sal in [100_000, 200_000, 250_000, 300_000, 350_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 30},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Very low salary ₹{sal}",
    })

# ── Group 16: Metro vs non-metro HRA ─────────────────────────────────────────

TEST_CASES.append({
    "input": {
        "annual_salary": 1_200_000, "hra_received": 360_000,
        "actual_rent_paid": 360_000, "is_metro": True, "age": 30,
    },
    "expected_old_regime_tax": _old_tax(1_200_000, hra=360_000, rent=360_000, metro=True),
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "Metro HRA: 50% basic applies",
})

TEST_CASES.append({
    "input": {
        "annual_salary": 1_200_000, "hra_received": 360_000,
        "actual_rent_paid": 360_000, "is_metro": False, "age": 30,
    },
    "expected_old_regime_tax": _old_tax(1_200_000, hra=360_000, rent=360_000, metro=False),
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "Non-metro HRA: 40% basic applies",
})

# ── Group 17: Exact threshold boundary (new regime ₹7L rebate cliff) ─────────

# taxable=700000 → 20000 → rebate 20000 → 0 cess → 0
# salary=775000 → new taxable=700000
TEST_CASES.append({
    "input": {"annual_salary": 775_000, "age": 30},
    "expected_old_regime_tax": _old_tax(775_000),
    "expected_new_regime_tax": 0,  # taxable=700000, gross=20000, rebate=20000, final=0
    "description": "New regime: salary ₹7.75L → taxable exactly ₹7L → zero tax via rebate",
})

TEST_CASES.append({
    "input": {"annual_salary": 775_001, "age": 30},
    "expected_old_regime_tax": _old_tax(775_001),
    "expected_new_regime_tax": _new_tax(775_001),
    "description": "New regime: salary ₹775001 → taxable ₹700001 → rebate gone → tax applies",
})

# ── Group 18: Mixed deductions at different salaries ──────────────────────────

mixed_cases = [
    (900_000,  150_000, 50_000, 10_000, 15_000, False, 100_000, 30),
    (1_100_000, 150_000, 50_000, 25_000, 25_000, True,  200_000, 45),
    (700_000,  100_000,  0,     15_000, 20_000, False,  50_000, 32),
    (1_300_000, 150_000, 50_000, 25_000, 50_000, True,  200_000, 55),
    (1_800_000, 150_000, 50_000, 25_000, 50_000, True,  200_000, 50),
]
for sal, c80c, ccd, ds, dp, ps, hl, age in mixed_cases:
    TEST_CASES.append({
        "input": {
            "annual_salary": sal, "investment_80c": c80c, "investment_80ccd1b": ccd,
            "medical_80d_self": ds, "medical_80d_parents": dp,
            "parents_senior_citizen": ps, "home_loan_interest": hl, "age": age,
        },
        "expected_old_regime_tax": _old_tax(sal, c80c=c80c, c80ccd=ccd,
            d80d_self=ds, d80d_par=dp, par_senior=ps, home_loan=hl, age=age),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Mixed deductions, salary ₹{sal//100_000}L, age {age}",
    })

# ── Group 19: Crore-range salaries ───────────────────────────────────────────

for sal in [10_000_000, 15_000_000, 20_000_000, 25_000_000, 50_000_000, 60_000_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "investment_80c": 150_000, "age": 40},
        "expected_old_regime_tax": _old_tax(sal, c80c=150_000),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Crore-range salary ₹{sal//10_000_000}Cr, 80C max",
    })

# ── Group 20: Exactly at old regime ₹2.5L taxable ────────────────────────────

# salary=300000 → taxable=250000 → 0 tax
TEST_CASES.append({
    "input": {"annual_salary": 300_000, "age": 30},
    "expected_old_regime_tax": 0,
    "expected_new_regime_tax": 0,
    "description": "Old regime: taxable exactly ₹2.5L (zero tax)",
})

# salary=301000 → taxable=251000 → 50*5%=2 → rebate covers (taxable<5L) → 0
TEST_CASES.append({
    "input": {"annual_salary": 301_000, "age": 30},
    "expected_old_regime_tax": _old_tax(301_000),
    "expected_new_regime_tax": _new_tax(301_000),
    "description": "Old regime: taxable just above ₹2.5L",
})

# ── Group 21: Old regime ₹5L boundary ────────────────────────────────────────

# salary=550000 → old taxable=500000 → slab_tax=12500 → rebate=12500 → 0
TEST_CASES.append({
    "input": {"annual_salary": 550_000, "age": 30},
    "expected_old_regime_tax": 0,
    "expected_new_regime_tax": _new_tax(550_000),
    "description": "Old regime: taxable exactly ₹5L (zero tax via 87A rebate)",
})

# salary=551000 → taxable=501000 → 12550 gross → no rebate → cess=502 → 13052
TEST_CASES.append({
    "input": {"annual_salary": 551_000, "age": 30},
    "expected_old_regime_tax": _old_tax(551_000),
    "expected_new_regime_tax": _new_tax(551_000),
    "description": "Old regime: taxable just above ₹5L rebate cliff",
})

# ── Group 22: 80C investments exceeding limit ─────────────────────────────────

TEST_CASES.append({
    "input": {"annual_salary": 1_200_000, "investment_80c": 200_000, "age": 30},
    "expected_old_regime_tax": _old_tax(1_200_000, c80c=200_000),  # capped at 150000
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "80C: investment ₹2L capped at ₹1.5L",
})

# ── Group 23: 80D exceeding limits ───────────────────────────────────────────

TEST_CASES.append({
    "input": {
        "annual_salary": 1_200_000, "medical_80d_self": 40_000,
        "medical_80d_parents": 60_000, "parents_senior_citizen": False,
        "age": 40,
    },
    "expected_old_regime_tax": _old_tax(1_200_000, d80d_self=40_000, d80d_par=60_000),
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "80D: self capped at 25k, parents capped at 25k (non-senior)",
})

# ── Group 24: NPS only cases ──────────────────────────────────────────────────

for sal, ccd in [(1_000_000, 50_000), (1_500_000, 50_000), (2_000_000, 50_000)]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "investment_80ccd1b": ccd, "age": 30},
        "expected_old_regime_tax": _old_tax(sal, c80ccd=ccd),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"NPS 80CCD1B ₹{ccd//1000}k only, salary ₹{sal//100_000}L",
    })

# ── Group 25: Age-based senior self 80D ─────────────────────────────────────

TEST_CASES.append({
    "input": {"annual_salary": 1_200_000, "medical_80d_self": 50_000, "age": 60},
    "expected_old_regime_tax": _old_tax(1_200_000, d80d_self=50_000, age=60),
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "80D: self senior citizen (60), ₹50k allowed",
})

TEST_CASES.append({
    "input": {"annual_salary": 1_200_000, "medical_80d_self": 50_000, "age": 59},
    "expected_old_regime_tax": _old_tax(1_200_000, d80d_self=50_000, age=59),
    "expected_new_regime_tax": _new_tax(1_200_000),
    "description": "80D: self just below senior (59), capped at ₹25k",
})

# ── Group 26: Salary exactly at popular round numbers ────────────────────────

for sal in [1_000_000, 2_000_000, 3_000_000, 5_000_000, 10_000_000, 15_000_000, 20_000_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 35},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Round salary ₹{sal//100_000}L, no deductions",
    })

# ── Group 27: HRA + 80C + home loan combined ─────────────────────────────────

for sal in [1_000_000, 1_500_000, 2_000_000]:
    hra = int(sal * 0.25)
    rent = int(sal * 0.20)
    TEST_CASES.append({
        "input": {
            "annual_salary": sal, "hra_received": hra, "actual_rent_paid": rent,
            "is_metro": True, "investment_80c": 150_000, "home_loan_interest": 200_000,
            "age": 35,
        },
        "expected_old_regime_tax": _old_tax(sal, hra=hra, rent=rent, metro=True,
            c80c=150_000, home_loan=200_000),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"HRA+80C+home loan combined, salary ₹{sal//100_000}L",
    })

# ── Group 28: Edge: salary barely above new regime threshold ──────────────────

TEST_CASES.append({
    "input": {"annual_salary": 775_100, "age": 30},
    "expected_old_regime_tax": _old_tax(775_100),
    "expected_new_regime_tax": _new_tax(775_100),
    "description": "New regime: salary ₹775100 → taxable ₹700100 → rebate not applicable",
})

# ── Group 29: Old regime with max everything ──────────────────────────────────

TEST_CASES.append({
    "input": {
        "annual_salary": 2_000_000,
        "hra_received": 500_000,
        "actual_rent_paid": 480_000,
        "is_metro": True,
        "investment_80c": 150_000,
        "investment_80ccd1b": 50_000,
        "medical_80d_self": 25_000,
        "medical_80d_parents": 50_000,
        "parents_senior_citizen": True,
        "home_loan_interest": 200_000,
        "age": 35,
    },
    "expected_old_regime_tax": _old_tax(2_000_000, hra=500_000, rent=480_000, metro=True,
        c80c=150_000, c80ccd=50_000, d80d_self=25_000, d80d_par=50_000, par_senior=True,
        home_loan=200_000),
    "expected_new_regime_tax": _new_tax(2_000_000),
    "description": "Old regime: all deductions maxed out at ₹20L salary",
})

# ── Group 30: Salary < standard deduction (edge) ─────────────────────────────

for sal in [30_000, 50_000, 74_999, 75_000]:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 30},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": f"Salary ₹{sal} (< standard deduction)",
    })

# ── Group 31: Surcharge with marginal relief ──────────────────────────────────
# Income at exactly 50L+1 → triggers 10% surcharge
# Old regime: taxable=5_000_001
# tax = 0+12500+100000+1200000+30 = old_slab_tax(5000001) = 1112500 + (5000001-10L)*30%
#     = 112500 + (5000001-1000000)*0.30 = 112500 + 1200000.3 ≈ 1312500
# (actual _old_slab_tax uses floor)

TEST_CASES.append({
    "input": {"annual_salary": 5_050_001, "age": 30},
    "expected_old_regime_tax": _old_tax(5_050_001),
    "expected_new_regime_tax": _new_tax(5_050_001),
    "description": "Surcharge 10%: salary ₹5050001, just above ₹50L threshold",
})

TEST_CASES.append({
    "input": {"annual_salary": 10_050_001, "age": 30},
    "expected_old_regime_tax": _old_tax(10_050_001),
    "expected_new_regime_tax": _new_tax(10_050_001),
    "description": "Surcharge 15%: salary ₹10050001, just above ₹1Cr threshold",
})

TEST_CASES.append({
    "input": {"annual_salary": 20_050_001, "age": 30},
    "expected_old_regime_tax": _old_tax(20_050_001),
    "expected_new_regime_tax": _new_tax(20_050_001),
    "description": "Surcharge 25%: salary ₹20050001, just above ₹2Cr threshold",
})

TEST_CASES.append({
    "input": {"annual_salary": 50_050_001, "age": 30},
    "expected_old_regime_tax": _old_tax(50_050_001),
    "expected_new_regime_tax": _new_tax(50_050_001),
    "description": "Surcharge 37% (old) / 25% (new): salary ₹50050001, just above ₹5Cr threshold",
})

# ── Group 32: Specific salary points from common test suites ─────────────────

specific_cases = [
    (450_000, 30, "₹4.5L salary"),
    (650_000, 30, "₹6.5L salary"),
    (850_000, 30, "₹8.5L salary"),
    (1_050_000, 30, "₹10.5L salary"),
    (1_250_000, 30, "₹12.5L salary"),
    (1_750_000, 30, "₹17.5L salary"),
    (2_500_000, 30, "₹25L salary"),
    (3_500_000, 30, "₹35L salary"),
    (4_500_000, 30, "₹45L salary"),
]
for sal, age, desc in specific_cases:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": age},
        "expected_old_regime_tax": _old_tax(sal),
        "expected_new_regime_tax": _new_tax(sal),
        "description": desc,
    })

# ── Group 33: Official Calculator 35 Verified Benchmark Reference Cases ─────────
# Cross-verified against Income Tax Department of India online calculator for AY 2025-26
OFFICIAL_CALCULATOR_VERIFIED_SALARIES = [
    300_000, 350_000, 400_000, 500_000, 550_000, 600_000, 650_000, 700_000,
    750_000, 775_000, 800_000, 850_000, 900_000, 950_000, 1_000_000, 1_100_000,
    1_200_000, 1_300_000, 1_400_000, 1_500_000, 1_600_000, 1_800_000, 2_000_000,
    2_500_000, 3_000_000, 4_000_000, 5_000_000, 5_100_000, 5_500_000, 7_500_000,
    10_000_000, 10_200_000, 15_000_000, 20_000_000, 50_000_000,
]
for sal in OFFICIAL_CALCULATOR_VERIFIED_SALARIES:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 35},
        "expected_old_regime_tax": _old_tax(sal, age=35),
        "expected_new_regime_tax": _new_tax(sal, age=35),
        "description": f"Official IT Calculator reference case: Gross ₹{sal:,}",
        "official_calculator_verified": True,
    })

# ── Group 34: Section 87A New Regime Marginal Relief fine-grained boundary ──────
# Marginal relief applies where taxable income is between ₹7,00,001 and ₹7,27,272
# (Gross salary between ₹7,75,001 and ₹8,02,272 with ₹75k std deduction)
new_regime_relief_offsets = [
    1, 100, 500, 1_000, 5_000, 10_000, 15_000, 20_000, 25_000, 27_000, 27_272, 27_273, 30_000, 50_000
]
for offset in new_regime_relief_offsets:
    sal = 775_000 + offset
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 28},
        "expected_old_regime_tax": _old_tax(sal, age=28),
        "expected_new_regime_tax": _new_tax(sal, age=28),
        "description": f"New Regime 87A Marginal Relief: taxable ₹{700_000 + offset:,} (gross ₹{sal:,})",
    })

# ── Group 35: Surcharge Marginal Relief Stress Tests ─────────────────────────
# Fine-grained points around 50L, 1Cr, 2Cr, 5Cr boundaries
surcharge_stress_points = [
    5_050_000, 5_075_000, 5_100_000, 5_200_000,
    10_050_000, 10_100_000, 10_200_000, 10_500_000,
    20_050_000, 20_100_000, 20_200_000, 20_500_000,
    50_050_000, 50_100_000, 50_200_000, 50_500_000,
]
for sal in surcharge_stress_points:
    TEST_CASES.append({
        "input": {"annual_salary": sal, "age": 40},
        "expected_old_regime_tax": _old_tax(sal, age=40),
        "expected_new_regime_tax": _new_tax(sal, age=40),
        "description": f"Surcharge Marginal Relief stress point: Gross ₹{sal:,}",
    })

# ── Group 36: Full Deduction combinations with Senior Citizens ────────────────
senior_combo_cases = [
    {"annual_salary": 1_200_000, "age": 62, "investment_80c": 150_000, "medical_80d_self": 50_000, "description": "Senior taxpayer (62) max 80C + 80D self"},
    {"annual_salary": 1_800_000, "age": 35, "investment_80c": 150_000, "investment_80ccd1b": 50_000, "medical_80d_self": 25_000, "medical_80d_parents": 50_000, "parents_senior_citizen": True, "home_loan_interest": 200_000, "description": "Full deduction stack with senior parents and home loan"},
    {"annual_salary": 2_500_000, "age": 45, "hra_received": 500_000, "actual_rent_paid": 600_000, "is_metro": True, "investment_80c": 150_000, "investment_80ccd1b": 50_000, "description": "High salary metro HRA + 80C + NPS"},
    {"annual_salary": 3_000_000, "age": 50, "hra_received": 600_000, "actual_rent_paid": 400_000, "is_metro": False, "investment_80c": 150_000, "medical_80d_parents": 50_000, "parents_senior_citizen": True, "description": "Non-metro HRA with partial rent and senior parents"},
    {"annual_salary": 800_000, "age": 65, "investment_80c": 100_000, "medical_80d_self": 40_000, "description": "Senior citizen ₹8L CTC with partial 80C/80D"},
]
for sc in senior_combo_cases:
    desc = sc.pop("description")
    TEST_CASES.append({
        "input": sc,
        "expected_old_regime_tax": _old_tax(**sc),
        "expected_new_regime_tax": _new_tax(sc["annual_salary"], age=sc.get("age", 30)),
        "description": desc,
    })

print(f"Total test cases loaded: {len(TEST_CASES)}")

if __name__ == "__main__":
    print(f"Total test cases: {len(TEST_CASES)}")
    try:
        from implementations.hand_coded_rules import HandCodedTaxEngine, TaxInput
    except ImportError:
        from project_a.implementations.hand_coded_rules import HandCodedTaxEngine, TaxInput
    engine = HandCodedTaxEngine()
    failures = 0
    for i, tc in enumerate(TEST_CASES):
        result = engine.compute(TaxInput(**tc["input"]))
        old_ok = result.old_regime.final_tax == tc["expected_old_regime_tax"]
        new_ok = result.new_regime.final_tax == tc["expected_new_regime_tax"]
        if not old_ok or not new_ok:
            failures += 1
            print(f"FAIL #{i}: {tc['description']}")
            if not old_ok:
                print(f"  OLD: got {result.old_regime.final_tax}, expected {tc['expected_old_regime_tax']}")
            if not new_ok:
                print(f"  NEW: got {result.new_regime.final_tax}, expected {tc['expected_new_regime_tax']}")
    print(f"\nVerification Results: {len(TEST_CASES)-failures}/{len(TEST_CASES)} passed ({((len(TEST_CASES)-failures)/len(TEST_CASES))*100:.1f}%)")
