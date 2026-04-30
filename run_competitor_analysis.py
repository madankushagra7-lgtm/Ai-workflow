"""
Main orchestrator for the competitor analysis workflow.
Run: python run_competitor_analysis.py

Steps:
  1. Validate business_profile.json
  2. Discover competitors (tools/discover_competitors.py)
  3. Scrape each competitor (tools/scrape_competitor.py)
  4. Analyze with Claude (tools/analyze_competitors.py)
  5. Generate branded PDF (tools/generate_pdf_report.py)
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def print_step(num, label):
    print(f"\n{'='*55}")
    print(f"  Step {num}: {label}")
    print(f"{'='*55}")


def run_tool(cmd, label):
    result = subprocess.run(cmd, cwd=ROOT, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"\n[FAIL] {label} exited with code {result.returncode}.")
        return False
    return True


def validate_profile():
    path = os.path.join(ROOT, "business_profile.json")
    if not os.path.isfile(path):
        print("[ERROR] business_profile.json not found. It should be in the project root.")
        return False
    with open(path, "r", encoding="utf-8") as f:
        try:
            profile = json.load(f)
        except json.JSONDecodeError:
            print("[ERROR] business_profile.json is not valid JSON.")
            return False

    if not profile.get("business_name", "").strip():
        print(
            "[ERROR] business_profile.json is missing 'business_name'.\n"
            "Please fill in your business details before running the workflow.\n"
            f"  → Open: {path}"
        )
        return False
    return True


def check_env_warnings():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))

    warnings = []
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        warnings.append(
            "ANTHROPIC_API_KEY is not set — the analysis step will fail.\n"
            "  → Add it to .env: ANTHROPIC_API_KEY=your_key_here"
        )
    if not os.getenv("SERPAPI_API_KEY", "").strip() and not os.getenv("TAVILY_API_KEY", "").strip():
        warnings.append(
            "No search API key found (SERPAPI_API_KEY or TAVILY_API_KEY).\n"
            "  → Will fall back to known_competitors in business_profile.json.\n"
            "  → For auto-discovery, add a key to .env."
        )
    for w in warnings:
        print(f"[WARN] {w}")
    return len([w for w in warnings if "ANTHROPIC" in w]) == 0


def run_scraping_step():
    tmp_path = os.path.join(ROOT, ".tmp", "competitors.json")
    if not os.path.isfile(tmp_path):
        print("[ERROR] .tmp/competitors.json not found. Discovery step may have failed.")
        return False

    with open(tmp_path, "r", encoding="utf-8") as f:
        competitors = json.load(f)

    if not competitors:
        print("[ERROR] No competitors found in .tmp/competitors.json. Cannot proceed.")
        return False

    print(f"\n[INFO] Scraping {len(competitors)} competitor websites...")
    success_count = 0
    for i, comp in enumerate(competitors, 1):
        url = comp.get("url", "")
        name = comp.get("name", url)
        if not url:
            print(f"  [{i}/{len(competitors)}] Skipping '{name}' — no URL.")
            continue
        print(f"  [{i}/{len(competitors)}] {url}")
        result = subprocess.run(
            [sys.executable, "tools/scrape_competitor.py", url],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip()
        for line in output.splitlines():
            if line.strip():
                print(f"    {line}")
        if result.returncode == 0:
            success_count += 1

    if success_count == 0:
        print("[ERROR] All scraping attempts failed. Cannot proceed to analysis.")
        return False

    print(f"\n[OK] Scraped {success_count}/{len(competitors)} competitors successfully.")
    return True


def main():
    print("\n" + "=" * 55)
    print("     COMPETITOR ANALYSIS WORKFLOW")
    print("=" * 55)

    print_step("PRE", "Validating setup")
    if not validate_profile():
        sys.exit(1)

    has_anthropic = check_env_warnings()
    if not has_anthropic:
        print("\n[ERROR] Cannot run analysis without ANTHROPIC_API_KEY. Aborting.")
        sys.exit(1)

    os.makedirs(os.path.join(ROOT, ".tmp"), exist_ok=True)

    print_step(1, "Discovering competitors")
    if not run_tool([sys.executable, "tools/discover_competitors.py"], "Competitor discovery"):
        sys.exit(1)

    print_step(2, "Scraping competitor websites")
    if not run_scraping_step():
        sys.exit(1)

    print_step(3, "Analyzing with Claude AI")
    if not run_tool([sys.executable, "tools/analyze_competitors.py"], "Claude analysis"):
        sys.exit(1)

    print_step(4, "Generating branded PDF report")
    if not run_tool([sys.executable, "tools/generate_pdf_report.py"], "PDF generation"):
        sys.exit(1)

    print("\n" + "=" * 55)
    print("  WORKFLOW COMPLETE")
    report_dir = os.path.join(ROOT, "reports")
    reports = sorted(
        [f for f in os.listdir(report_dir) if f.endswith(".pdf")],
        reverse=True,
    )
    if reports:
        print(f"  Report: {os.path.join(report_dir, reports[0])}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
