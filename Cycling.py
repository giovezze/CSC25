
"""
Cycling Event Route Planner (Enhanced Planning Prototype)

OVERVIEW
--------
This script is a PLANNING tool for cycling event organizers.
It helps answer high-level planning questions such as:

• What candidate routes could we offer?
• How difficult are those routes likely to be?
• How many staff and volunteers might we need?
• How do route count, distance, and riders affect operations?

IMPORTANT
---------
• This is NOT a production routing engine.
• Route geometry is approximate and for planning only.
• All outputs are ESTIMATES, not commitments.
• The model intentionally biases toward safety and over-support.

TARGET AUDIENCE
---------------
• Ride Directors
• Operations Leads
• Technical planners
• Developers extending this prototype
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, List, Optional, Tuple

import googlemaps


# ------------------------------------------------------------------
# SECURITY & API SAFETY CONTROLS
# ------------------------------------------------------------------
# These controls protect against:
# • Accidental Google Maps quota exhaustion
# • Crashes due to API errors
# • Running the tool without credentials
# • Unsafe testing scenarios

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# If set to true, all Google Maps calls are skipped.
# Useful for testing logic without spending API quota.
DRY_RUN = os.getenv("CYCLING_PLANNER_DRY_RUN", "false").lower() == "true"

# Hard limit on how many Google Maps API calls may occur per run.
# This prevents accidental cost explosions.
MAX_API_CALLS_PER_RUN = 25
_api_call_count = 0


def _check_api_budget() -> bool:
    """
    Track and enforce per-run Google Maps API call limits.

    Returns:
        True  -> API call is allowed
        False -> API call budget exhausted
    """
    global _api_call_count
    if _api_call_count >= MAX_API_CALLS_PER_RUN:
        print("⚠️ API call limit reached; continuing without enrichment.")
        return False
    _api_call_count += 1
    return True


# Initialize Google Maps client unless running in DRY_RUN mode.
if not DRY_RUN:
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY environment variable is not set.")
    google_maps_client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
else:
    google_maps_client = None
    print("ℹ️ DRY_RUN enabled — no Google Maps API calls will be made.")


# ------------------------------------------------------------------
# PLANNING HEURISTICS & CONSTRAINTS
# ------------------------------------------------------------------
# These values represent conservative, industry-style planning
# assumptions. They are NOT precise measurements.

ELEVATION_GAIN_PER_MILE_FT = 120.0  # heuristic placeholder

BASE_SAFETY_SCORE = 90.0
SAFETY_SCORE_DISTANCE_PENALTY = 0.2
SAFETY_SCORE_VARIANT_BONUS = 2.0

MIN_DISTANCE_MILES = 1.0
MAX_DISTANCE_MILES = 200.0
DEFAULT_TARGET_DISTANCES = [10.0, 25.0, 50.0]

MIN_EXPECTED_RIDERS = 1
MAX_EXPECTED_RIDERS = 2000
MAX_ADDRESS_LENGTH = 200


# ------------------------------------------------------------------
# DOMAIN MODELS
# ------------------------------------------------------------------
# These dataclasses define the vocabulary of the planning domain.
# They are immutable (frozen=True) to avoid accidental mutation.

@dataclass(frozen=True)
class Location:
    """
    Represents a real-world location.

    Coordinates may be resolved later via geocoding.
    """
    label: str
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None


class RouteDifficulty(Enum):
    """
    Human-friendly difficulty classification.
    """
    EASY = "Easy"
    MODERATE = "Moderate"
    CHALLENGING = "Challenging"


@dataclass(frozen=True)
class RoutePreferences:
    """
    Inputs that influence route generation.
    """
    central_location: Location
    target_distances_miles: List[float]
    loop_preference: bool


@dataclass(frozen=True)
class RouteCandidate:
    """
    Planning-level description of a route.

    This is NOT a navigable route; it is a planning artifact.
    """
    name: str
    distance_miles: float
    actual_distance_miles: float
    elevation_gain_ft: float
    turn_count: int
    safety_score: float
    difficulty: RouteDifficulty
    geometry_wkt: str
    destination: Optional[Location] = None


@dataclass(frozen=True)
class StaffingRatios:
    """
    Configurable planning ratios for staffing estimates.

    These should be reviewed and tuned using historical event data.
    """
    riders_per_sag: int = 175
    riders_per_mechanic: int = 250
    sag_per_long_route: int = 1
    long_route_threshold_miles: int = 50
    turns_per_signage_team: int = 30
    registration_seconds_per_rider: int = 90
    registration_peak_window_minutes: int = 60
    registration_lead_minutes: int = 120
    route_start_spacing_minutes: int = 20
    rest_stop_spacing_miles: int = 12
    rest_stop_volunteers_per_stop: int = 5
    rest_stop_leads_per_stop: int = 1


@dataclass(frozen=True)
class StaffingEstimate:
    """
    Aggregated staffing results (planning estimates).
    """
    sag_vehicles: int
    mechanics_hub: int
    mechanics_roving: int
    total_mechanics: int
    signage_teams: int
    rest_stop_leads: int
    rest_stop_volunteers: int
    registration_volunteers: int


# ------------------------------------------------------------------
# INPUT SANITIZATION & PARSING
# ------------------------------------------------------------------

def sanitize_address(text: str) -> str:
    """
    Remove control characters and enforce max length.
    Protects terminal output and downstream APIs.
    """
    cleaned = "".join(ch for ch in text if ch.isprintable())
    return cleaned[:MAX_ADDRESS_LENGTH]


def parse_target_distances(text: str) -> List[float]:
    """
    Parse comma-separated distance input.
    Accepts values like '10, 25, 50 miles'.
    """
    distances: List[float] = []

    for token in text.split(","):
        cleaned = token.strip().lower().replace("miles", "").replace("mile", "")
        if not cleaned:
            continue

        value = float(cleaned)

        if not (MIN_DISTANCE_MILES <= value <= MAX_DISTANCE_MILES):
            raise ValueError("Distance out of range.")

        distances.append(value)

    if not distances:
        raise ValueError("At least one distance is required.")

    return distances


def parse_expected_riders(text: str) -> int:
    """
    Parse expected rider count with sensible defaults.
    """
    if not text:
        return 250

    riders = int(text)

    if not (MIN_EXPECTED_RIDERS <= riders <= MAX_EXPECTED_RIDERS):
        raise ValueError("Expected riders out of range.")

    return riders


# ------------------------------------------------------------------
# SAFE GOOGLE MAPS API WRAPPERS
# ------------------------------------------------------------------

def safe_geocode(address: str) -> Optional[Tuple[float, float]]:
    """
    Geocode an address safely.
    Returns (lat, lon) or None on failure.
    """
    if DRY_RUN or not _check_api_budget():
        return None

    try:
        results = google_maps_client.geocode(address)
        if not results:
            return None
        loc = results[0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    except Exception:
        return None


def safe_directions(origin: str, destination: str) -> Optional[float]:
    """
    Retrieve approximate route distance in miles.
    Returns None if API fails or is disabled.
    """
    if DRY_RUN or not _check_api_budget():
        return None

    try:
        results = google_maps_client.directions(
            origin, destination, mode="bicycling"
        )
        if not results:
            return None

        meters = sum(
            leg["distance"]["value"]
            for leg in results[0].get("legs", [])
        )
        return meters / 1609.34
    except Exception:
        return None


# ------------------------------------------------------------------
# ROUTE GENERATION (PLANNING-FIRST)
# ------------------------------------------------------------------

def estimate_elevation_gain(distance_miles: float) -> float:
    """
    Estimate elevation gain using a simple heuristic.
    """
    return distance_miles * ELEVATION_GAIN_PER_MILE_FT


def classify_route_difficulty(
    distance_miles: float,
    elevation_gain_ft: float,
) -> RouteDifficulty:
    """
    Assign a planner-friendly difficulty category.
    """
    if distance_miles <= 15 and elevation_gain_ft <= 1500:
        return RouteDifficulty.EASY
    if distance_miles <= 40 and elevation_gain_ft <= 3500:
        return RouteDifficulty.MODERATE
    return RouteDifficulty.CHALLENGING


def generate_route_candidates(preferences: RoutePreferences) -> List[RouteCandidate]:
    """
    Generate planning-level route candidates.

    Uses limited Directions API calls for enrichment.
    """
    origin = preferences.central_location
    candidates: List[RouteCandidate] = []

    # Cardinal bearings to explore rough directions
    bearings = [0, 90, 180, 270]

    for distance in preferences.target_distances_miles:
        elevation = estimate_elevation_gain(distance)
        difficulty = classify_route_difficulty(distance, elevation)

        for idx, bearing in enumerate(bearings, start=1):
            delta_lat = (distance / 2) * math.cos(math.radians(bearing)) / 69.0
            lat = (origin.lat or 0.0) + delta_lat
            lon = origin.lon or 0.0

            actual_distance = (
                safe_directions(
                    f"{origin.lat},{origin.lon}",
                    f"{lat},{lon}",
                )
                or distance
            )

            candidates.append(
                RouteCandidate(
                    name=f"{int(distance)}mi Variant {idx}",
                    distance_miles=distance,
                    actual_distance_miles=actual_distance,
                    elevation_gain_ft=elevation,
                    turn_count=max(3, int(distance / 3)),
                    safety_score=max(
                        50.0,
                        BASE_SAFETY_SCORE
                        - distance * SAFETY_SCORE_DISTANCE_PENALTY
                        + idx * SAFETY_SCORE_VARIANT_BONUS,
                    ),
                    difficulty=difficulty,
                    geometry_wkt="LINESTRING (0 0, 1 1)",
                )
            )

    return candidates


# ------------------------------------------------------------------
# STAFFING LOGIC (CONSERVATIVE PLANNING)
# ------------------------------------------------------------------

def select_representative_routes(routes: List[RouteCandidate]) -> List[RouteCandidate]:
    """
    Select the most demanding route per distance.
    """
    by_distance: dict[float, RouteCandidate] = {}
    for r in routes:
        if (
            r.distance_miles not in by_distance
            or r.turn_count > by_distance[r.distance_miles].turn_count
        ):
            by_distance[r.distance_miles] = r
    return list(by_distance.values())


def estimate_staffing(
    expected_riders: int,
    routes: List[RouteCandidate],
    ratios: StaffingRatios,
) -> StaffingEstimate:
    """
    Estimate staffing needs conservatively.
    """
    selected = select_representative_routes(routes)
    distances = [r.distance_miles for r in selected]

    longest = max(distances)
    rest_stops = max(1, math.ceil(longest / ratios.rest_stop_spacing_miles))

    sag = max(1, math.ceil(expected_riders / ratios.riders_per_sag))
    hub_mech = max(1, math.ceil(expected_riders / ratios.riders_per_mechanic))
    roving_mech = math.ceil(sag / 2)

    signage = max(
        1,
        math.ceil(
            max(r.turn_count for r in selected) / ratios.turns_per_signage_team
        ),
    )

    reg_vols = max(
        1,
        math.ceil(
            expected_riders
            * ratios.registration_seconds_per_rider
            / (ratios.registration_peak_window_minutes * 60)
        ),
    )

    return StaffingEstimate(
        sag_vehicles=sag,
        mechanics_hub=hub_mech,
        mechanics_roving=roving_mech,
        total_mechanics=hub_mech + roving_mech,
        signage_teams=signage,
        rest_stop_leads=rest_stops,
        rest_stop_volunteers=rest_stops * ratios.rest_stop_volunteers_per_stop,
        registration_volunteers=reg_vols,
    )


# ------------------------------------------------------------------
# CLI ENTRY POINT
# ------------------------------------------------------------------

def main():
    """
    Interactive entry point for planning use.
    """
    address = sanitize_address(input("Enter central event address: ").strip())
    latlon = safe_geocode(address) or (0.0, 0.0)

    distances = parse_target_distances(
        input("Target distances (default 10,25,50): ").strip() or "10,25,50"
    )
    riders = parse_expected_riders(
        input("Expected riders (default 250): ").strip()
    )

    prefs = RoutePreferences(
        central_location=Location("Central Hub", address, latlon[0], latlon[1]),
        target_distances_miles=distances,
        loop_preference=True,
    )

    routes = generate_route_candidates(prefs)
    staffing = estimate_staffing(riders, routes, StaffingRatios())

    print("\n=== STAFFING ESTIMATE (PLANNING) ===")
    print(staffing)


if __name__ == "__main__":
    main()
