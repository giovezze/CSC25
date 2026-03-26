"""Cycling Event Route Planner (prototype)

This module provides a minimal, interactive prototype for the first
functional requirement: generating candidate loop routes from a central
hub and estimating staffing needs based on those routes.

The code is intentionally simple and self-contained, but includes clear
extension points (route generation, route metadata, staffing ratios)
so other teams can hook into it as the system evolves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


# ------------------------------------------------------------------
# 1. DATA MODELS ()
# ------------------------------------------------------------------

@dataclass(frozen=True)
class RoutePreferences:
    """User-provided preferences that affect route generation."""

    central_lat: float
    central_lon: float
    target_distances_miles: List[float]
    loop_preference: bool
    max_elevation_gain_ft: Optional[float]
    allow_unpaved: bool
    max_speed_limit_mph: Optional[float]
    max_arterial_pct: Optional[float]


@dataclass(frozen=True)
class RouteCandidate:
    """Minimal route metadata returned by the route generator."""

    name: str
    distance_miles: float
    elevation_gain_ft: float
    turn_count: int
    safety_score: float  # 0-100 (higher is safer)
    geometry_wkt: str  # placeholder for a real LineString geometry


@dataclass(frozen=True)
class StaffingRatios:
    """Configurable planning ratios for staffing and volunteers."""

    riders_per_sag: int = 175
    riders_per_mechanic: int = 250
    sag_per_long_route: int = 1
    long_route_threshold_miles: int = 50
    turns_per_signage_team: int = 30
    registration_seconds_per_rider: int = 90
    registration_max_wait_minutes: int = 10
    # Peak arrival assumptions for registration (flattening the rush)
    registration_peak_fraction: float = 0.25  # fraction of riders arriving in peak window
    registration_peak_window_minutes: int = 60
    rest_stop_spacing_miles: int = 12
    rest_stop_volunteers_per_stop: int = 5
    rest_stop_leads_per_stop: int = 1


@dataclass(frozen=True)
class StaffingEstimate:
    sag_vehicles: int
    mechanics_hub: int
    mechanics_roving: int
    total_mechanics: int
    signage_teams: int
    rest_stop_leads: int
    rest_stop_volunteers: int
    registration_volunteers: int


# ------------------------------------------------------------------
# 2. ROUTE GENERATION (Functional Requirement #1)
# ------------------------------------------------------------------

def prompt_float(prompt: str, default: Optional[float] = None) -> float:
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


def prompt_int(prompt: str, default: Optional[int] = None) -> int:
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Please enter an integer.")


def prompt_bool(prompt: str, default: Optional[bool] = None) -> bool:
    while True:
        raw = input(prompt).strip().lower()
        if raw == "" and default is not None:
            return default
        if raw in ("y", "yes", "true", "t", "1"):
            return True
        if raw in ("n", "no", "false", "f", "0"):
            return False
        print("Please answer yes or no.")


def build_route_preferences_from_user_input() -> RoutePreferences:
    """Prompt the user for inputs needed to generate candidate routes."""

    print("\n--- Route Generation Inputs ---")
    central_lat = prompt_float("Central start/finish lat (decimal): ")
    central_lon = prompt_float("Central start/finish lon (decimal): ")

    distances_raw = input(
        "Target distances (miles) - comma separated (e.g. 10,25,50): "
    ).strip()
    distances = [float(d.strip()) for d in distances_raw.split(",") if d.strip()]

    loop_pref = prompt_bool("Generate loop routes? (y/n) [y]: ", default=True)
    max_elev = prompt_float(
        "Max elevation gain per route (feet, optional - blank to skip): ",
        default=None,
    )

    allow_unpaved = prompt_bool("Allow unpaved surfaces? (y/n) [n]: ", default=False)
    max_speed = prompt_float(
        "Max speed limit for routes (mph, optional): ", default=None
    )
    max_arterial_pct = prompt_float(
        "Max % of route on arterials (0-100, optional): ", default=None
    )

    return RoutePreferences(
        central_lat=central_lat,
        central_lon=central_lon,
        target_distances_miles=distances,
        loop_preference=loop_pref,
        max_elevation_gain_ft=max_elev,
        allow_unpaved=allow_unpaved,
        max_speed_limit_mph=max_speed,
        max_arterial_pct=max_arterial_pct,
    )


def generate_candidate_routes(
    prefs: RoutePreferences, max_candidates_per_distance: int = 3
) -> List[RouteCandidate]:
    """Generate candidate loop routes based on user preferences.

    NOTE: This is a simplified placeholder implementation. In the full system,
    this would run a constrained routing algorithm over a road network graph
    (OSM/NetworkX/OSRM) and produce actual polylines and metrics.

    Returned candidates include enough metadata for downstream staffing and
    permit planning components to consume.
    """

    candidates: List[RouteCandidate] = []

    for target in prefs.target_distances_miles:
        for idx in range(1, max_candidates_per_distance + 1):
            # Placeholder metric calculations; replace with real routing logic.
            distance = target
            elevation_gain = max(0.0, target * 120.0)  # 120 ft per mile as a heuristic
            turns = int(round(target * 2.0 + idx))
            safety_score = max(0.0, min(100.0, 90.0 - target * 0.2 + (idx - 1) * 2.0))

            candidate = RouteCandidate(
                name=f"{int(target)}mi - option {idx}",
                distance_miles=distance,
                elevation_gain_ft=elevation_gain,
                turn_count=turns,
                safety_score=safety_score,
                geometry_wkt=(
                    "LINESTRING ("  # placeholder geometry to show shape
                    f"{prefs.central_lon} {prefs.central_lat}, "
                    f"{prefs.central_lon + 0.01} {prefs.central_lat + 0.01})"
                ),
            )
            candidates.append(candidate)

    return candidates


def print_route_candidates(routes: List[RouteCandidate]) -> None:
    """Prints a compact table of candidate routes for a user to review."""

    if not routes:
        print("No candidate routes available.")
        return

    print("\n=== Candidate Routes ===")
    for r in routes:
        print(
            f"- {r.name}: {r.distance_miles:.1f} mi, "
            f"{r.elevation_gain_ft:.0f} ft gain, {r.turn_count} turns, "
            f"Safety: {r.safety_score:.0f}/100"
        )


# ------------------------------------------------------------------
# 3. STAFFING ESTIMATION (rewritten to integrate with routes)
# ------------------------------------------------------------------

def estimate_rest_stop_count(
    route_distances_miles: Iterable[float],
    spacing_miles: int = StaffingRatios.rest_stop_spacing_miles,
) -> int:
    """Estimate the number of rest stops for a set of routes."""

    total = 0
    for dist in route_distances_miles:
        if dist <= 0:
            continue
        total += max(1, math.ceil(dist / spacing_miles))
    return total


def estimate_sag_vehicles(
    total_riders: int, routes: List[RouteCandidate], ratios: StaffingRatios
) -> int:
    """Estimate SAG vehicles needed for the event."""

    base_sag = math.ceil(total_riders / ratios.riders_per_sag)
    long_route_count = sum(
        1 for r in routes if r.distance_miles >= ratios.long_route_threshold_miles
    )
    return max(1, base_sag + long_route_count * ratios.sag_per_long_route)


def estimate_mechanics(
    total_riders: int, sag_vehicles: int, ratios: StaffingRatios
) -> Tuple[int, int, int]:
    """Estimate hub and roving mechanics based on riders and SAG vehicles."""

    hub_mechanics = max(1, math.ceil(total_riders / ratios.riders_per_mechanic))
    roving_mechanics = math.ceil(sag_vehicles / 2)
    return hub_mechanics, roving_mechanics, hub_mechanics + roving_mechanics


def estimate_signage_teams(
    routes: List[RouteCandidate], ratios: StaffingRatios
) -> int:
    """Estimate the number of signage teams needed (based on total turns)."""

    total_turns = sum(r.turn_count for r in routes)
    return max(1, math.ceil(total_turns / ratios.turns_per_signage_team))


def estimate_registration_volunteers(
    total_riders: int, ratios: StaffingRatios
) -> int:
    """Estimate registration volunteers using a flattened arrival window.

    This assumes a fraction of riders arrive during a configurable peak window
    rather than all arriving at once, which produces a more realistic staffing
    number while still providing a target throughput goal.
    """

    peak_riders = max(1, math.ceil(total_riders * ratios.registration_peak_fraction))
    peak_window_seconds = ratios.registration_peak_window_minutes * 60
    arrival_rate_rps = peak_riders / peak_window_seconds

    # One station can process `1 / seconds_per_rider` riders per second.
    station_capacity_rps = 1.0 / ratios.registration_seconds_per_rider

    stations_needed = math.ceil(arrival_rate_rps / station_capacity_rps)
    return max(1, stations_needed)


def estimate_staffing(
    total_riders: int, routes: List[RouteCandidate], ratios: StaffingRatios
) -> StaffingEstimate:
    """Estimate overall staffing needs for an event given candidate routes."""

    sag_vehicles = estimate_sag_vehicles(total_riders, routes, ratios)
    hub_mechanics, roving_mechanics, total_mechanics = estimate_mechanics(
        total_riders, sag_vehicles, ratios
    )
    signage_teams = estimate_signage_teams(routes, ratios)

    rest_stop_count = estimate_rest_stop_count(
        [r.distance_miles for r in routes], ratios.rest_stop_spacing_miles
    )
    rest_stop_volunteers = rest_stop_count * ratios.rest_stop_volunteers_per_stop
    rest_stop_leads = rest_stop_count * ratios.rest_stop_leads_per_stop

    registration_volunteers = estimate_registration_volunteers(
        total_riders, ratios
    )

    return StaffingEstimate(
        sag_vehicles=sag_vehicles,
        mechanics_hub=hub_mechanics,
        mechanics_roving=roving_mechanics,
        total_mechanics=total_mechanics,
        signage_teams=signage_teams,
        rest_stop_leads=rest_stop_leads,
        rest_stop_volunteers=rest_stop_volunteers,
        registration_volunteers=registration_volunteers,
    )


def print_staffing_estimate(estimate: StaffingEstimate) -> None:
    print("\n=== STAFFING ESTIMATE ===")
    print(f"SAG vehicles:              {estimate.sag_vehicles}")
    print(f"Mechanics (hub):           {estimate.mechanics_hub}")
    print(f"Mechanics (roving):        {estimate.mechanics_roving}")
    print(f"Total mechanics:           {estimate.total_mechanics}")
    print(f"Signage teams:             {estimate.signage_teams}")
    print(f"Rest stop leads:           {estimate.rest_stop_leads}")
    print(f"Rest stop volunteers:      {estimate.rest_stop_volunteers}")
    print(f"Registration volunteers:   {estimate.registration_volunteers}")
    print("==========================\n")


# ------------------------------------------------------------------
# 4. MAIN PROGRAM / CLI
# ------------------------------------------------------------------

def main_menu() -> None:
    """Interactive menu that connects route generation and staffing estimates."""

    routes: List[RouteCandidate] = []
    total_expected_riders: Optional[int] = None

    while True:
        print("\n=== CYCLING EVENT PLANNER ===")
        print("1) Generate candidate routes")
        print("2) Estimate staffing & volunteers")
        print("3) Generate routes + estimate staffing")
        print("4) Exit")

        choice = input("Select an option: ").strip()

        if choice == "1":
            prefs = build_route_preferences_from_user_input()
            routes = generate_candidate_routes(prefs)
            print_route_candidates(routes)

        elif choice == "2":
            if not routes:
                print("\nNo routes available yet; generate routes first.\n")
                continue

            total_expected_riders = prompt_int(
                "Total expected riders (across all routes): "
            )
            ratios = StaffingRatios()
            estimate = estimate_staffing(
                total_expected_riders, routes, ratios
            )
            print_staffing_estimate(estimate)

        elif choice == "3":
            prefs = build_route_preferences_from_user_input()
            routes = generate_candidate_routes(prefs)
            print_route_candidates(routes)

            total_expected_riders = prompt_int(
                "Total expected riders (across all routes): "
            )
            ratios = StaffingRatios()
            estimate = estimate_staffing(
                total_expected_riders, routes, ratios
            )
            print_staffing_estimate(estimate)

        elif choice == "4":
            print("\nGoodbye!\n")
            break

        else:
            print("\nInvalid choice. Please try again.\n")


if __name__ == "__main__":
    main_menu()

""" run success (Brookdale coordinates)
Excellent news: the script executed successfully and produced route + staffing results for Brookdale. The program logic is working and this confirms the main functions are generating valid output.

Input used
central latitude: 40.1983
central longitude: -74.2788
target distances: 10, 25, 50 miles
expected riders: 250
Route candidates output
9 routes (3 options for each distance)
distances exactly as requested
heuristic elevation gains and safety scores generated
Staffing estimate output
SAG vehicles: 5
Hub mechanics: 1
Roving mechanics: 3
Total mechanics: 4
Signage teams: 18
Rest stop leads: 27
Rest stop volunteers: 135
Registration volunteers: 2
 """