"""
main.py - CLI Interface for Project A (Indian Income Tax Engine).

Commands:
  python main.py --text "I earn 12 lakhs and pay 25000 rent in Delhi..."
  python main.py --benchmark
  python main.py --test
"""

import sys
import os
import argparse
import json

# Ensure project_a and root are in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
for p in [_current_dir, _parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from implementations.hand_coded_rules import HandCodedTaxEngine, TaxInput
from parser import NLPParser
from benchmark import run_benchmark
from tests.test_cases import TEST_CASES


def run_tests():
    print(f"\n==================================================")
    print(f"RUNNING PROJECT A TEST SUITE ({len(TEST_CASES)} CASES)")
    print(f"==================================================")
    engine = HandCodedTaxEngine()
    passed = 0
    failures = []
    for i, tc in enumerate(TEST_CASES):
        inp = TaxInput(**tc["input"])
        res = engine.compute(inp)
        old_match = (res.old_regime.final_tax == tc["expected_old_regime_tax"])
        new_match = (res.new_regime.final_tax == tc["expected_new_regime_tax"])
        if old_match and new_match:
            passed += 1
        else:
            failures.append((i, tc["description"], res, tc))

    print(f"\nTotal Cases: {len(TEST_CASES)}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {len(failures)}")
    print(f"Accuracy:    {(passed / len(TEST_CASES)) * 100:.2f}%\n")
    if failures:
        print("First 3 failures:")
        for idx, desc, res, tc in failures[:3]:
            print(f"  #{idx}: {desc}")
            print(f"    Old regime - computed: {res.old_regime.final_tax}, expected: {tc['expected_old_regime_tax']}")
            print(f"    New regime - computed: {res.new_regime.final_tax}, expected: {tc['expected_new_regime_tax']}")
    else:
        print("ALL TEST CASES PASSED WITH 100% RUPEE-EXACT PRECISION!")
    print(f"==================================================\n")
    return 0 if len(failures) == 0 else 1


def handle_text(text: str):
    print("\n" + "=" * 70)
    print("USER INPUT:")
    print(f'"{text}"')
    print("=" * 70)

    parser = NLPParser()
    parse_result = parser.parse(text)

    if parse_result.clarification_needed and parse_result.clarification_question:
        print("\n[CLARIFYING QUESTION REQUIRED]")
        print(f"  {parse_result.clarification_question}")
        print("\n(The engine avoids guessing missing or ambiguous data.)")
        print("=" * 70)
        return

    p = parse_result.parsed
    if not p.salary:
        print("\nCould not determine annual salary. Please provide your annual salary/CTC.")
        return

    tax_input = TaxInput(
        annual_salary=p.salary or 0,
        hra_received=p.hra or 0,
        actual_rent_paid=p.rent or 0,
        is_metro=p.is_metro or False,
        investment_80c=p.investment_80c or 0,
        investment_80ccd1b=p.investment_80ccd1b or 0,
        medical_80d_self=p.medical_80d_self or 0,
        medical_80d_parents=p.medical_80d_parents or 0,
        parents_senior_citizen=p.parents_senior_citizen or False,
        home_loan_interest=p.home_loan_interest or 0,
        age=p.age or 30,
    )

    engine = HandCodedTaxEngine()
    res = engine.compute(tax_input)

    print("\nTAX COMPUTATION BREAKDOWN (FY 2024-25 / AY 2025-26):")
    print("-" * 70)
    print(f"{'Item':<35} | {'Old Regime':<15} | {'New Regime':<15}")
    print("-" * 70)
    print(f"{'Gross Salary':<35} | ₹{res.old_regime.gross_salary:>13,} | ₹{res.new_regime.gross_salary:>13,}")
    print(f"{'Standard Deduction':<35} | ₹{res.old_regime.standard_deduction:>13,} | ₹{res.new_regime.standard_deduction:>13,}")
    if res.old_regime.hra_exemption:
        print(f"{'HRA Exemption (Sec 10(13A))':<35} | ₹{res.old_regime.hra_exemption:>13,} | {'N/A':>14}")
    if res.old_regime.deduction_80c:
        print(f"{'Section 80C Deductions':<35} | ₹{res.old_regime.deduction_80c:>13,} | {'N/A':>14}")
    if res.old_regime.deduction_80d_self or res.old_regime.deduction_80d_parents:
        print(f"{'Section 80D Health Insurance':<35} | ₹{(res.old_regime.deduction_80d_self + res.old_regime.deduction_80d_parents):>13,} | {'N/A':>14}")
    print(f"{'Total Taxable Income':<35} | ₹{res.old_regime.taxable_income:>13,} | ₹{res.new_regime.taxable_income:>13,}")
    print(f"{'Slab Tax (Gross)':<35} | ₹{res.old_regime.gross_tax:>13,} | ₹{res.new_regime.gross_tax:>13,}")
    if res.old_regime.rebate_87a or res.new_regime.rebate_87a:
        print(f"{'Section 87A Rebate':<35} | ₹{res.old_regime.rebate_87a:>13,} | ₹{res.new_regime.rebate_87a:>13,}")
    if res.old_regime.surcharge or res.new_regime.surcharge:
        print(f"{'Surcharge (net of marginal relief)':<35} | ₹{res.old_regime.surcharge_after_relief:>13,} | ₹{res.new_regime.surcharge_after_relief:>13,}")
    print(f"{'4% Health & Education Cess':<35} | ₹{res.old_regime.cess:>13,} | ₹{res.new_regime.cess:>13,}")
    print("-" * 70)
    print(f"{'FINAL TAX LIABILITY':<35} | ₹{res.old_regime.final_tax:>13,} | ₹{res.new_regime.final_tax:>13,}")
    print("=" * 70)
    print(f"RECOMMENDATION: Choose {res.recommended_regime.upper()} REGIME")
    print(f"Net Savings:    ₹{res.savings:,}")
    print(f"Reason:         {res.recommendation_reason}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Indian Income Tax Engine CLI (FY 2024-25 & FY 2025-26)")
    parser.add_argument("--text", type=str, help="Plain-language salary and deduction description")
    parser.add_argument("--test", action="store_true", help="Run full 220+ test suite")
    parser.add_argument("--benchmark", action="store_true", help="Run comparative benchmark of 3 implementations")

    args = parser.parse_args()

    if args.test:
        sys.exit(run_tests())
    elif args.benchmark:
        run_benchmark()
    elif args.text:
        handle_text(args.text)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
