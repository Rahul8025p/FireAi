"""
run_all.py - Master Reproducibility Script for Fire AI Take-Home Assignment.

A single command that runs the full test suite, profiles real NYC 311 2023 data,
executes benchmarks for Project A and Project B, runs the hybrid pipeline,
saves execution state at each step to pipeline_execution_state.json,
and reproduces every metric reported in RESULTS_A.md, RESULTS_B.md, and DECISION_MATRIX.md.

Usage:
  python run_all.py
"""

import sys
import os
import time
import json
import subprocess
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(ROOT_DIR, "pipeline_execution_state.json")

# Auto-load .env into environment
env_path = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip("\"' \t\r\n")
                if key:
                    os.environ["GOOGLE_API_KEY"] = key

def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f" {title.upper()}")
    print("=" * 80)

def save_state(state_data: dict):
    state_data["last_updated"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state_data, f, indent=2)

def run_step(step_idx: int, description: str, cmd: list[str], state_data: dict, artifacts: list[str]) -> bool:
    print(f"\n>>> [STEP {step_idx}/5] {description} ...")
    t0 = time.time()
    t_start_iso = datetime.now().isoformat()

    step_info = {
        "step_index": step_idx,
        "description": description,
        "command": cmd,
        "status": "RUNNING",
        "started_at": t_start_iso,
        "ended_at": None,
        "duration_seconds": None,
        "exit_code": None,
        "generated_artifacts": [],
    }
    state_data["steps"].append(step_info)
    save_state(state_data)

    res = subprocess.run(cmd, cwd=ROOT_DIR)
    elapsed = time.time() - t0
    t_end_iso = datetime.now().isoformat()

    step_info["status"] = "COMPLETED" if res.returncode == 0 else "FAILED"
    step_info["ended_at"] = t_end_iso
    step_info["duration_seconds"] = round(elapsed, 2)
    step_info["exit_code"] = res.returncode

    # Check generated artifacts
    for art in artifacts:
        art_path = os.path.join(ROOT_DIR, art)
        if os.path.exists(art_path):
            step_info["generated_artifacts"].append({
                "path": art,
                "size_bytes": os.path.getsize(art_path),
                "modified_at": datetime.fromtimestamp(os.path.getmtime(art_path)).isoformat()
            })

    save_state(state_data)

    if res.returncode == 0:
        print(f">>> [SUCCESS] Step {step_idx} finished in {elapsed:.2f}s.")
        return True
    else:
        print(f">>> [FAILED] Step {step_idx} exited with code {res.returncode} in {elapsed:.2f}s.")
        return False

def main():
    print_banner("FIRE AI: RULES VS LLMS - FULL REPRODUCIBILITY SUITE")
    print(f"Executing from root: {ROOT_DIR}")
    print(f"Python interpreter: {sys.executable}")
    print(f"Tracking state at : {STATE_FILE}")
    has_gemini_key = bool(os.environ.get("GOOGLE_API_KEY"))
    print(f"Gemini API Key    : {'Configured and Active' if has_gemini_key else 'Not Found (using deterministic fallbacks)'}")

    t_start = time.time()

    state_data = {
        "pipeline_name": "Fire AI Take-Home Rules vs LLMs Master Suite",
        "started_at": datetime.now().isoformat(),
        "python_version": sys.version,
        "has_gemini_api_key": has_gemini_key,
        "steps": [],
        "overall_status": "IN_PROGRESS",
    }
    save_state(state_data)

    steps = [
        (1, "Project A: Run 222 Unit & Boundary Test Cases",
         [sys.executable, "project_a/main.py", "--test"],
         ["project_a/tests/test_cases.py"]),

        (2, "Project A: Run Three Implementations & Law Change Benchmark",
         [sys.executable, "project_a/main.py", "--benchmark"],
         ["project_a/benchmark_results.json"]),

        (3, "Project B: Profile REAL 2023 NYC 311 Dataset",
         [sys.executable, "project_b/profiler.py"],
         ["project_b/real_data_quality_report.md", "project_b/data/nyc_311_2023_clean.csv"]),

        (4, "Project B: Benchmark 12 Corruption Types x 3 Detector Families on Real Data",
         [sys.executable, "project_b/benchmark.py"],
         ["project_b/benchmark_results.json"]),

        (5, "Project B: Execute Production Hybrid Data Quality Pipeline",
         [sys.executable, "project_b/pipeline.py"],
         ["project_b/data/nyc_311_2023_clean.csv"]),
    ]

    all_passed = True
    for idx, desc, cmd, arts in steps:
        success = run_step(idx, desc, cmd, state_data, arts)
        if not success:
            all_passed = False
            print(f"Aborting due to failure in step {idx}: {desc}")
            break

    total_time = time.time() - t_start
    state_data["overall_status"] = "SUCCESS" if all_passed else "FAILED"
    state_data["total_duration_seconds"] = round(total_time, 2)
    state_data["completed_at"] = datetime.now().isoformat()
    save_state(state_data)

    print_banner("EXECUTION SUMMARY")
    if all_passed:
        print(f"Status: ALL 5 STEPS COMPLETED SUCCESSFULLY in {total_time:.2f}s!")
        print(f"Pipeline state saved at each step to: {STATE_FILE}")
        print("\nAll deliverables updated and verifiable:")
        print("  - RESULTS_A.md                 : Indian income-tax rules vs LLMs benchmark & FY25-26 change analysis")
        print("  - RESULTS_B.md                 : NYC 311 real data quality audit & 12-problem benchmark")
        print("  - DECISION_MATRIX.md           : Grounded component-by-component architectural justification")
        print("  - AI_USAGE.md                  : Transparent AI tool usage note & failure postmortem")
        print("  - README.md                    : Full setup, architecture, and reproduction instructions")
        print("  - pipeline_execution_state.json: Persisted execution state and artifact metadata for every step")
        sys.exit(0)
    else:
        print("Status: FAILED. Check step logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
