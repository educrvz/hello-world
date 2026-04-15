#!/usr/bin/env python3
"""
Geocode hospital addresses using Nominatim (OpenStreetMap).
3-tier fallback: full address → hospital name + city → city centroid.
Reads hospitals_raw.json and outputs hospitals.json with lat/lng.
"""

import json
import os
import sys
import time

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

SCRIPT_DIR = os.path.dirname(__file__)
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "..", "hospitals_raw.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "..", "hospitals.json")
DEFAULT_FAILED = os.path.join(SCRIPT_DIR, "..", "hospitals_failed_geocode.json")
CACHE_FILE = os.path.join(SCRIPT_DIR, "..", "geocode_cache.json")

# Brazil geographic bounds
BRAZIL_LAT = (-34.0, 6.0)
BRAZIL_LNG = (-74.0, -34.0)

RATE_LIMIT_SECONDS = 1.1


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def is_in_brazil(lat, lng):
    return BRAZIL_LAT[0] <= lat <= BRAZIL_LAT[1] and BRAZIL_LNG[0] <= lng <= BRAZIL_LNG[1]


def geocode_query(geolocator, query, cache):
    """Geocode a query string with caching and rate limiting."""
    if query in cache:
        cached = cache[query]
        if cached is None:
            return None
        return cached

    time.sleep(RATE_LIMIT_SECONDS)

    try:
        location = geolocator.geocode(query, timeout=10)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"    Geocoder error for '{query[:50]}': {e}")
        time.sleep(5)
        try:
            location = geolocator.geocode(query, timeout=15)
        except Exception:
            cache[query] = None
            return None

    if location and is_in_brazil(location.latitude, location.longitude):
        result = {"lat": location.latitude, "lng": location.longitude, "display": location.address}
        cache[query] = result
        return result

    cache[query] = None
    return None


def geocode_hospital(geolocator, hospital, cache):
    """
    Geocode a hospital using 3-tier fallback:
    1. Full address + city + state
    2. Hospital name + city + state
    3. City + state (centroid)
    """
    city = hospital.get("city", "")
    state = hospital.get("state_name", "")
    address = hospital.get("address", "")
    name = hospital.get("hospital_name", "")

    # Tier 1: Full address
    if address and city:
        query = f"{address}, {city}, {state}, Brasil"
        result = geocode_query(geolocator, query, cache)
        if result:
            return result, 1

    # Tier 2: Hospital name + city
    if name and city:
        query = f"{name}, {city}, {state}, Brasil"
        result = geocode_query(geolocator, query, cache)
        if result:
            return result, 2

    # Tier 3: City centroid
    if city:
        query = f"{city}, {state}, Brasil"
        result = geocode_query(geolocator, query, cache)
        if result:
            return result, 3

    return None, 0


def main():
    input_path = DEFAULT_INPUT
    output_path = DEFAULT_OUTPUT
    failed_path = DEFAULT_FAILED

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]

    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    with open(input_path, "r", encoding="utf-8") as f:
        hospitals = json.load(f)

    print(f"Loaded {len(hospitals)} hospitals from {input_path}")

    cache = load_cache()
    print(f"Cache has {len(cache)} entries")

    geolocator = Nominatim(user_agent="sos-antiveneno-geocoder/1.0")

    geocoded = []
    failed = []
    tier_counts = {1: 0, 2: 0, 3: 0, 0: 0}

    for i, h in enumerate(hospitals):
        result, tier = geocode_hospital(geolocator, h, cache)

        if result:
            h["lat"] = round(result["lat"], 6)
            h["lng"] = round(result["lng"], 6)
            h["geocode_tier"] = tier
            geocoded.append(h)
        else:
            h["lat"] = None
            h["lng"] = None
            h["geocode_tier"] = 0
            failed.append(h)

        tier_counts[tier] += 1

        if (i + 1) % 50 == 0:
            pct = (i + 1) / len(hospitals) * 100
            print(f"  Progress: {i + 1}/{len(hospitals)} ({pct:.0f}%) — "
                  f"T1:{tier_counts[1]} T2:{tier_counts[2]} T3:{tier_counts[3]} fail:{tier_counts[0]}")
            save_cache(cache)

    save_cache(cache)

    # Write all hospitals (geocoded + failed with null coords) to output
    all_hospitals = geocoded + failed
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_hospitals, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(all_hospitals)} hospitals to {output_path}")

    if failed:
        with open(failed_path, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(failed)} failed entries to {failed_path}")

    total = len(hospitals)
    print(f"\n=== Geocoding Results ===")
    print(f"  Total: {total}")
    print(f"  Tier 1 (address): {tier_counts[1]} ({tier_counts[1]/total*100:.1f}%)")
    print(f"  Tier 2 (name): {tier_counts[2]} ({tier_counts[2]/total*100:.1f}%)")
    print(f"  Tier 3 (city): {tier_counts[3]} ({tier_counts[3]/total*100:.1f}%)")
    print(f"  Failed: {tier_counts[0]} ({tier_counts[0]/total*100:.1f}%)")
    print(f"  Success rate: {(total-tier_counts[0])/total*100:.1f}%")


if __name__ == "__main__":
    main()
