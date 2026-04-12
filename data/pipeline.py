#!/usr/bin/env python3
"""
PESA Data Pipeline Orchestrator

Runs the full pipeline: scrape PDFs → geocode → output final JSON.

Usage:
    python3 pipeline.py                    # Parse local PDFs + geocode
    python3 pipeline.py --download         # Download PDFs first
    python3 pipeline.py --skip-geocode     # Only parse, skip geocoding
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# Add script directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from scraper import scrape_all
from geocoder import HospitalGeocoder


def main():
    parser = argparse.ArgumentParser(description="PESA Data Pipeline")
    parser.add_argument("--download", action="store_true",
                        help="Download PDFs from gov.br before parsing")
    parser.add_argument("--skip-geocode", action="store_true",
                        help="Skip geocoding step (parse PDFs only)")
    parser.add_argument("--pdf-dir", default=None,
                        help="PDF directory (default: data/pdfs)")
    args = parser.parse_args()

    pdf_dir = args.pdf_dir or str(script_dir / "pdfs")
    raw_path = script_dir / "hospitals_raw.json"
    final_path = script_dir / "hospitals.json"
    fail_path = script_dir / "hospitals_failed.json"
    app_path = script_dir.parent / "app" / "hospitals.json"

    # ── Step 1: Scrape PDFs ──────────────────────────────────────────────
    print("=" * 60)
    print("STEP 1: SCRAPING PDFs")
    print("=" * 60)
    print()

    hospitals, scrape_failures = scrape_all(pdf_dir, download=args.download)

    # Write raw data
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(hospitals, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(hospitals)} hospitals to {raw_path}")

    if not hospitals:
        print("\nERROR: No hospitals extracted. Check PDFs in {pdf_dir}")
        sys.exit(1)

    # ── Step 2: Geocode ──────────────────────────────────────────────────
    if args.skip_geocode:
        print("\nSkipping geocoding (--skip-geocode)")
        # Write without coordinates
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(hospitals, f, ensure_ascii=False, indent=2)
    else:
        print()
        print("=" * 60)
        print("STEP 2: GEOCODING")
        print("=" * 60)
        print()

        geocoder = HospitalGeocoder()
        geocoded, geo_failures = geocoder.geocode_batch(hospitals)

        # Merge all hospitals (geocoded + failed but keep all)
        all_hospitals = geocoded + geo_failures
        all_hospitals.sort(key=lambda h: (h.get("state", ""), h.get("city", "")))

        # Write final data
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(all_hospitals, f, ensure_ascii=False, indent=2)
        print(f"\nWrote {len(all_hospitals)} hospitals to {final_path}")

        # Write failures
        all_failures = scrape_failures + [
            {**h, "error": "Geocoding failed"} for h in geo_failures
        ]
        if all_failures:
            with open(fail_path, "w", encoding="utf-8") as f:
                json.dump(all_failures, f, ensure_ascii=False, indent=2)
            print(f"Wrote {len(all_failures)} failures to {fail_path}")

    # ── Step 3: Copy to app ──────────────────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 3: DEPLOYING TO APP")
    print("=" * 60)

    app_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final_path, app_path)
    print(f"Copied {final_path} → {app_path}")

    # ── Summary ──────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    with open(final_path, "r", encoding="utf-8") as f:
        final_data = json.load(f)
    print(f"  Total hospitals: {len(final_data)}")

    # Count by state
    by_state = {}
    for h in final_data:
        s = h.get("state", "??")
        by_state[s] = by_state.get(s, 0) + 1
    print(f"  States covered: {len(by_state)}")
    for s in sorted(by_state.keys()):
        print(f"    {s}: {by_state[s]}")

    if not args.skip_geocode:
        with_coords = sum(1 for h in final_data if h.get("lat") is not None)
        print(f"  With coordinates: {with_coords}/{len(final_data)}")


if __name__ == "__main__":
    main()
