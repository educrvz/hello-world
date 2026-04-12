#!/usr/bin/env python3
"""
Hospital Geocoder

Geocodes hospital addresses using Nominatim (OpenStreetMap).
Three-tier fallback: full address → hospital name + city → city centroid.

Usage:
    python3 geocoder.py                          # Geocode hospitals_raw.json
    python3 geocoder.py --input custom.json      # Use custom input
    python3 geocoder.py --output result.json     # Custom output path
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
except ImportError:
    print("ERROR: geopy not installed. Run: pip3 install geopy")
    sys.exit(1)

# Brazil coordinate bounds for validation
BRAZIL_LAT_MIN, BRAZIL_LAT_MAX = -34.0, 6.0
BRAZIL_LNG_MIN, BRAZIL_LNG_MAX = -74.0, -34.0


class HospitalGeocoder:
    def __init__(self, cache_file: str = None):
        self.geolocator = Nominatim(
            user_agent="sos-antiveneno-brazil/1.0 (emergency-hospital-finder)",
            timeout=10,
        )
        self.geocode_fn = RateLimiter(
            self.geolocator.geocode,
            min_delay_seconds=1.1,
            max_retries=2,
            error_wait_seconds=5.0,
            return_value_on_exception=None,
        )
        self.cache_file = cache_file or str(
            Path(__file__).parent / "geocode_cache.json"
        )
        self.cache = self._load_cache()
        self._cache_hits = 0
        self._api_calls = 0

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _is_valid_brazil_coords(self, lat: float, lng: float) -> bool:
        return (
            BRAZIL_LAT_MIN <= lat <= BRAZIL_LAT_MAX
            and BRAZIL_LNG_MIN <= lng <= BRAZIL_LNG_MAX
        )

    def _try_geocode(self, query: str) -> tuple:
        """
        Try to geocode a query string.
        Returns (lat, lng) or (None, None).
        """
        # Check cache
        if query in self.cache:
            cached = self.cache[query]
            self._cache_hits += 1
            if cached.get("lat") is not None:
                return cached["lat"], cached["lng"]
            return None, None

        # API call
        self._api_calls += 1
        try:
            location = self.geocode_fn(
                query,
                country_codes="br",
                exactly_one=True,
            )
        except Exception as e:
            print(f"    Geocode error for '{query}': {e}")
            location = None

        if location and self._is_valid_brazil_coords(
            location.latitude, location.longitude
        ):
            lat, lng = location.latitude, location.longitude
            self.cache[query] = {
                "lat": lat,
                "lng": lng,
                "display_name": location.address,
            }
            return lat, lng
        else:
            self.cache[query] = {"lat": None, "lng": None, "display_name": None}
            return None, None

    def geocode_hospital(self, hospital: dict) -> dict:
        """
        Geocode a single hospital using three-tier fallback.
        Modifies the hospital dict in-place and returns it.
        """
        city = hospital.get("city", "")
        state_name = hospital.get("state_name", "")
        address = hospital.get("address", "")
        name = hospital.get("hospital_name", "")

        # Tier 1: Full address + city + state
        if address and city:
            query = f"{address}, {city}, {state_name}, Brasil"
            lat, lng = self._try_geocode(query)
            if lat is not None:
                hospital["lat"] = lat
                hospital["lng"] = lng
                hospital["geocode_quality"] = "address"
                return hospital

        # Tier 2: Hospital name + city + state
        if name and city:
            query = f"{name}, {city}, {state_name}, Brasil"
            lat, lng = self._try_geocode(query)
            if lat is not None:
                hospital["lat"] = lat
                hospital["lng"] = lng
                hospital["geocode_quality"] = "hospital_name"
                return hospital

        # Tier 3: City + state centroid
        if city:
            query = f"{city}, {state_name}, Brasil"
            lat, lng = self._try_geocode(query)
            if lat is not None:
                hospital["lat"] = lat
                hospital["lng"] = lng
                hospital["geocode_quality"] = "city_centroid"
                return hospital

        # All tiers failed
        hospital["lat"] = None
        hospital["lng"] = None
        hospital["geocode_quality"] = "failed"
        return hospital

    def geocode_batch(self, hospitals: list) -> tuple:
        """
        Geocode a list of hospitals.
        Returns (geocoded, failed).
        """
        geocoded = []
        failed = []
        total = len(hospitals)

        for i, hospital in enumerate(hospitals):
            city = hospital.get("city", "")
            state = hospital.get("state", "")
            name = hospital.get("hospital_name", "")
            print(
                f"  [{i + 1}/{total}] {name}, {city}-{state}...",
                end="",
                flush=True,
            )

            result = self.geocode_hospital(hospital)
            quality = result.get("geocode_quality", "failed")

            if quality == "failed":
                print(f" FAILED")
                failed.append(result)
            else:
                print(f" OK ({quality}: {result['lat']:.4f}, {result['lng']:.4f})")
                geocoded.append(result)

            # Save cache periodically
            if (i + 1) % 10 == 0:
                self._save_cache()

        # Final cache save
        self._save_cache()

        # Print stats
        print(f"\n{'=' * 60}")
        print("GEOCODING SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Total hospitals: {total}")
        print(f"  Successfully geocoded: {len(geocoded)}")
        print(f"  Failed: {len(failed)}")
        print(f"  Cache hits: {self._cache_hits}")
        print(f"  API calls: {self._api_calls}")

        # Quality breakdown
        qualities = {}
        for h in geocoded:
            q = h.get("geocode_quality", "unknown")
            qualities[q] = qualities.get(q, 0) + 1
        for q, count in sorted(qualities.items()):
            print(f"  Quality '{q}': {count}")

        return geocoded, failed


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Hospital Geocoder")
    parser.add_argument(
        "--input",
        default=None,
        help="Input JSON file (default: data/hospitals_raw.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file (default: data/hospitals.json)",
    )
    parser.add_argument(
        "--cache",
        default=None,
        help="Cache file (default: data/geocode_cache.json)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    input_path = args.input or str(script_dir / "hospitals_raw.json")
    output_path = args.output or str(script_dir / "hospitals.json")

    # Load hospitals
    print(f"Loading hospitals from {input_path}...")
    with open(input_path, "r", encoding="utf-8") as f:
        hospitals = json.load(f)
    print(f"Loaded {len(hospitals)} hospitals")
    print()

    # Geocode
    geocoder = HospitalGeocoder(cache_file=args.cache)
    geocoded, failed = geocoder.geocode_batch(hospitals)

    # Sort by state, then city
    geocoded.sort(key=lambda h: (h.get("state", ""), h.get("city", "")))

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geocoded, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(geocoded)} geocoded hospitals to {output_path}")

    # Write failures
    if failed:
        fail_path = str(Path(output_path).parent / "hospitals_failed.json")
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(failed)} failures to {fail_path}")

    # Copy to app directory
    app_path = script_dir.parent / "app" / "hospitals.json"
    if app_path.parent.exists():
        all_hospitals = geocoded + [h for h in failed if h.get("lat") is not None]
        all_hospitals.sort(key=lambda h: (h.get("state", ""), h.get("city", "")))
        with open(app_path, "w", encoding="utf-8") as f:
            json.dump(all_hospitals, f, ensure_ascii=False, indent=2)
        print(f"Copied {len(all_hospitals)} hospitals to {app_path}")


if __name__ == "__main__":
    main()
