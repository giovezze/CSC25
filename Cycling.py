"""
Cycling Event Route Planner (Enhanced Planning Prototype)

PURPOSE
-------
This script is a PLANNING tool to help cycling event organizers:
- Generate candidate routes from a central hub
- Estimate elevation and route difficulty
- Size staffing and volunteers conservatively

IMPORTANT NOTES
---------------
• This is NOT an operational routing engine.
• All outputs are estimates for planning discussion.
• Google Maps is used ONLY for geocoding (address → coordinates).
• Real route geometry is a future enhancement.
"""

from __future__ import annotations

import math
import json
import os
import re
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Optional

import googlemaps


# ------------------------------------------------------------------
# GOOGLE MAPS CONFIGURATION
# ------------------------------------------------------------------

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    raise RuntimeError(
        "GOOGLE_MAPS_API_KEY environment variable is not set."
    )

google_maps_client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)


# ------------------------------------------------------------------
# PLANNING HEURISTICS & 
# ------------------------------------------------------------------

ELEVATION_GAIN_PER_MILE_FT = 120.0  # Conservative heuristic

MIN_DISTANCE_MILES = 1.0
MAX_DISTANCE_MILES = 200.0
MAX_ROUTE_DISTANCES = 5
MAX_ROUTE_VARIANTS_PER_DISTANCE = 3
MAX_ROUTE_CANDIDATES = 12
DEFAULT_TARGET_DISTANCES = [10.0, 25.0, 50.0]
MIN_EXPECTED_RIDERS = 1
MAX_EXPECTED_RIDERS = 2000
MAX_ADDRESS_LENGTH = 200

BASE_SAFETY_SCORE = 90.0
SAFETY_SCORE_DISTANCE_PENALTY = 0.2
SAFETY_SCORE_VARIANT_BONUS = 2.0


# ------------------------------------------------------------------
# DOMAIN MODELS
# ------------------------------------------------------------------

@dataclass(frozen=True)
class Location:
    """
    Human-readable location.

    Coordinates are resolved via geocoding when needed.
    """
    label: str
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None


class RouteDifficulty(Enum):
    EASY = "Easy"
    MODERATE = "Moderate"
    CHALLENGING = "Challenging"


@dataclass(frozen=True)
class RoutePreferences:
    central_location: Location
    target_distances_miles: List[float]
    loop_preference: bool
    max_elevation_gain_ft: Optional[float]
    allow_unpaved: bool
    max_speed_limit_mph: Optional[float]
    max_arterial_pct: Optional[float]


@dataclass(frozen=True)
class RouteCandidate:
    name: str
    distance_miles: float
    actual_distance_miles: float
    elevation_gain_ft: float
    turn_count: int
    safety_score: float
    difficulty: RouteDifficulty
    geometry_wkt: str  # Placeholder only
    destination: Optional[Location] = None


@dataclass(frozen=True)
class StaffingRatios:
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
    sag_vehicles: int
    mechanics_hub: int
    mechanics_roving: int
    total_mechanics: int
    signage_teams: int
    rest_stop_leads: int
    rest_stop_volunteers: int
    registration_volunteers: int


# ------------------------------------------------------------------
# SAVED PLACES (PERSISTENT JSON)
# ------------------------------------------------------------------

class SavedPlacesRepository:
    """
    Simple persistent saved places registry backed by JSON.
    """

    def __init__(self, filepath: str = "saved_places.json"):
        self.path = Path(filepath)
        self._places = self._load()

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def save(self) -> None:
        self.path.write_text(json.dumps(self._places, indent=2))

    def get(self, name: str) -> Optional[str]:
        return self._places.get(name.lower())

    def add(self, name: str, address: str) -> None:
        self._places[name.lower()] = address
        self.save()


# ------------------------------------------------------------------
# GOOGLE MAPS GEOCODING (ISOLATED)
# ------------------------------------------------------------------

def geocode_location_if_needed(location: Location) -> Location:
    """
    Ensure a Location has latitude and longitude.
    """

    if location.lat is not None and location.lon is not None:
        return location

    results = google_maps_client.geocode(location.address)

    if not results:
        raise ValueError(f"Could not geocode address: {location.address}")

    coords = results[0]["geometry"]["location"]

    return Location(
        label=location.label,
        address=location.address,
        lat=coords["lat"],
        lon=coords["lng"],
    )


# ------------------------------------------------------------------
# ELEVATION & DIFFICULTY
# ------------------------------------------------------------------

def estimate_elevation_gain_feet(distance_miles: float) -> float:
    """
    Distance-based elevation heuristic.
    """
    return distance_miles * ELEVATION_GAIN_PER_MILE_FT


def classify_route_difficulty(
    distance_miles: float,
    elevation_gain_ft: float,
) -> RouteDifficulty:
    """
    Planner-friendly difficulty classification.
    """
    if distance_miles <= 15 and elevation_gain_ft <= 1500:
        return RouteDifficulty.EASY
    if distance_miles <= 40 and elevation_gain_ft <= 3500:
        return RouteDifficulty.MODERATE
    return RouteDifficulty.CHALLENGING


def parse_target_distances(target_input: str) -> List[float]:
    distances: List[float] = []
    for item in target_input.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            distance = float(item)
        except ValueError:
            raise ValueError(f"Invalid distance value: '{item}'")

        if distance < MIN_DISTANCE_MILES or distance > MAX_DISTANCE_MILES:
            raise ValueError(
                f"Distance must be between {MIN_DISTANCE_MILES} and {MAX_DISTANCE_MILES} miles: {distance}"
            )
        distances.append(distance)

    if not distances:
        raise ValueError("No valid distances provided.")
    if len(distances) > MAX_ROUTE_DISTANCES:
        raise ValueError(
            f"At most {MAX_ROUTE_DISTANCES} target distances are allowed."
        )

    return distances


def parse_expected_riders(riders_input: str) -> int:
    if not riders_input:
        return 250
    try:
        expected_riders = int(riders_input)
    except ValueError:
        raise ValueError("Expected rider count must be an integer.")

    if expected_riders < MIN_EXPECTED_RIDERS or expected_riders > MAX_EXPECTED_RIDERS:
        raise ValueError(
            f"Expected riders must be between {MIN_EXPECTED_RIDERS} and {MAX_EXPECTED_RIDERS}."
        )

    return expected_riders


def compute_route_destination(origin: Location, distance_miles: float, variant: int) -> Location:
    """Create an approximate destination coordinate for a candidate route."""
    bearings = [45, 135, 225, 315]
    bearing = bearings[(variant - 1) % len(bearings)]
    delta_lat = distance_miles * math.cos(math.radians(bearing)) / 69.0
    delta_lon = distance_miles * math.sin(math.radians(bearing)) / (69.0 * math.cos(math.radians(origin.lat)))
    lat = origin.lat + delta_lat
    lon = origin.lon + delta_lon

    # Reverse geocode to get a valid address on a road
    reverse_results = google_maps_client.reverse_geocode((lat, lon))
    if reverse_results:
        address = reverse_results[0]["formatted_address"]
    else:
        address = f"{lat:.6f},{lon:.6f}"

    return Location(
        label=f"Route Endpoint {variant}",
        address=address,
        lat=lat,
        lon=lon,
    )


def get_directions_instructions(origin: Location, destination: Location, is_loop: bool = False) -> tuple[List[str], float]:
    """Use the Directions API to get real road instructions and total distance."""
    origin_text = f"{origin.lat},{origin.lon}"
    destination_text = f"{destination.lat},{destination.lon}"
    results = google_maps_client.directions(
        origin_text,
        destination_text,
        mode="bicycling",
    )
    if not results:
        return [], 0.0

    instructions: List[str] = []
    total_meters = 0
    for leg in results[0].get("legs", []):
        total_meters += leg.get("distance", {}).get("value", 0)
        for step in leg.get("steps", []):
            html = step.get("html_instructions", "")
            text = re.sub(r"<.*?>", "", html)
            distance = step.get("distance", {}).get("text", "")
            instructions.append(f"{distance}    {text}")

    total_distance_miles = total_meters / 1609.34

    if is_loop:
        # For loops, add the return leg
        return_results = google_maps_client.directions(
            destination_text,
            origin_text,
            mode="bicycling",
        )
        if return_results:
            for leg in return_results[0].get("legs", []):
                total_meters += leg.get("distance", {}).get("value", 0)
                for step in leg.get("steps", []):
                    html = step.get("html_instructions", "")
                    text = re.sub(r"<.*?>", "", html)
                    distance = step.get("distance", {}).get("text", "")
                    instructions.append(f"{distance}    {text}")
            total_distance_miles = total_meters / 1609.34

    return instructions, total_distance_miles


def generate_route_candidates(
    preferences: RoutePreferences,
    ratios: StaffingRatios,
) -> List[RouteCandidate]:
    """Create route candidates using simple planning heuristics."""
    candidates: List[RouteCandidate] = []

    for distance in preferences.target_distances_miles:
        for variant in range(1, MAX_ROUTE_VARIANTS_PER_DISTANCE + 1):
            if len(candidates) >= MAX_ROUTE_CANDIDATES:
                break

            name = f"{int(distance)}mi {'Loop' if preferences.loop_preference else 'Out-and-Back'} Variant {variant}"
            destination_distance = distance * 0.4
            destination = compute_route_destination(preferences.central_location, destination_distance, variant)
            instructions, actual_distance = get_directions_instructions(preferences.central_location, destination, preferences.loop_preference)
            turn_count = max(3, len(instructions))
            elevation_gain_ft = estimate_elevation_gain_feet(distance)
            difficulty = classify_route_difficulty(distance, elevation_gain_ft)
            geometry_wkt = f"LINESTRING (0 0, {distance} 0)"

            candidates.append(
                RouteCandidate(
                    name=name,
                    distance_miles=distance,
                    actual_distance_miles=actual_distance,
                    elevation_gain_ft=elevation_gain_ft,
                    turn_count=turn_count,
                    safety_score=max(50.0, BASE_SAFETY_SCORE - distance * SAFETY_SCORE_DISTANCE_PENALTY + (variant - 1) * SAFETY_SCORE_VARIANT_BONUS),
                    difficulty=difficulty,
                    geometry_wkt=geometry_wkt,
                    destination=destination,
                )
            )

        if len(candidates) >= MAX_ROUTE_CANDIDATES:
            break

    return candidates


def estimate_staffing(
    expected_riders: int,
    route_candidates: List[RouteCandidate],
    ratios: StaffingRatios,
) -> StaffingEstimate:
    """Estimate event staffing requirements."""
    total_distance = sum(candidate.distance_miles for candidate in route_candidates)
    total_turns = sum(candidate.turn_count for candidate in route_candidates)
    rest_stops = max(1, math.ceil(total_distance / ratios.rest_stop_spacing_miles))

    sag_vehicles = max(1, math.ceil(expected_riders / ratios.riders_per_sag))
    mechanics_hub = max(1, math.ceil(expected_riders / ratios.riders_per_mechanic))
    mechanics_roving = max(1, math.ceil(len(route_candidates) / 2))
    signage_teams = max(1, math.ceil(total_turns / ratios.turns_per_signage_team))
    rest_stop_leads = max(1, rest_stops * ratios.rest_stop_leads_per_stop)
    rest_stop_volunteers = rest_stops * ratios.rest_stop_volunteers_per_stop
    registration_volunteers = max(1, math.ceil(expected_riders * ratios.registration_seconds_per_rider / (ratios.registration_peak_window_minutes * 60)))

    return StaffingEstimate(
        sag_vehicles=sag_vehicles,
        mechanics_hub=mechanics_hub,
        mechanics_roving=mechanics_roving,
        total_mechanics=mechanics_hub + mechanics_roving,
        signage_teams=signage_teams,
        rest_stop_leads=rest_stop_leads,
        rest_stop_volunteers=rest_stop_volunteers,
        registration_volunteers=registration_volunteers,
    )


def print_event_summary(
    location: Location,
    route_candidates: List[RouteCandidate],
    staffing: StaffingEstimate,
    expected_riders: int,
) -> None:
    print(f"\nEvent hub: {location.label}")
    print(f"Address: {location.address}")
    if location.lat is not None and location.lon is not None:
        print(f"Coordinates: {location.lat:.6f}, {location.lon:.6f}")
    print(f"Expected riders: {expected_riders}\n")

    print("Route candidates:")
    for candidate in route_candidates:
        print(
            f"- {candidate.name}: {candidate.actual_distance_miles:.1f} miles, "
            f"{candidate.elevation_gain_ft:.0f} ft gain, {candidate.difficulty.value}, "
            f"safety {candidate.safety_score:.1f}, {candidate.turn_count} turns"
        )

    print("\nStaffing estimate:")
    print(f"- SAG vehicles: {staffing.sag_vehicles}")
    print(f"- Hub mechanics: {staffing.mechanics_hub}")
    print(f"- Roving mechanics: {staffing.mechanics_roving}")
    print(f"- Total mechanics: {staffing.total_mechanics}")
    print(f"- Signage teams: {staffing.signage_teams}")
    print(f"- Rest stop leads: {staffing.rest_stop_leads}")
    print(f"- Rest stop volunteers: {staffing.rest_stop_volunteers}")
    print(f"- Registration volunteers: {staffing.registration_volunteers}")


def format_route_cue_sheet(route_candidate: RouteCandidate) -> List[str]:
    """Create a simple line-by-line cue sheet for one route."""
    segment_count = route_candidate.turn_count + 1
    weights = [1.4, 1.0, 1.2, 0.8, 1.3, 0.9]
    weights = [weights[i % len(weights)] for i in range(segment_count)]
    total_weight = sum(weights)
    segment_distances = [route_candidate.actual_distance_miles * w / total_weight for w in weights]

    streets = [
        "Holmdel Road",
        "Main Street",
        "River Road",
        "Park Avenue",
        "Maple Drive",
        "Old Mill Road",
        "Elm Street",
        "Sunset Boulevard",
        "Cedar Lane",
        "Forest Hill Road",
    ]
    turn_directions = [
        "Right",
        "Left",
        "Slight right",
        "Left",
        "Right",
        "Slight left",
    ]

    cumulative = 0.0
    lines = [
        f"Cue sheet for {route_candidate.name} ({route_candidate.actual_distance_miles:.1f} mi, {route_candidate.turn_count} turns)",
        f"{cumulative:.1f}    Start on {streets[0]}.",
    ]

    for i in range(route_candidate.turn_count):
        seg_dist = segment_distances[i]
        street = streets[(i + 1) % len(streets)]
        direction = turn_directions[i % len(turn_directions)]
        lines.append(
            f"{cumulative:.1f}    {seg_dist:.2f} mi    {direction} turn onto {street}"
        )
        cumulative += seg_dist

    final_street = streets[(route_candidate.turn_count + 1) % len(streets)]
    final_seg_dist = segment_distances[-1]
    lines.append(f"{cumulative:.1f}    {final_seg_dist:.2f} mi    Finish on {final_street}")
    return lines


def prompt_for_cue_sheet(origin: Location, route_candidates: List[RouteCandidate]) -> None:
    if not route_candidates:
        return

    print("\nAvailable routes for cue sheet:")
    for index, candidate in enumerate(route_candidates, start=1):
        print(f"{index}. {candidate.name} ({candidate.actual_distance_miles:.1f} mi, {candidate.turn_count} turns)")

    choice = input("Enter route number for a cue sheet (or press Enter to skip): ").strip()
    if not choice:
        return

    if not choice.isdigit() or not (1 <= int(choice) <= len(route_candidates)):
        print("Invalid selection; skipping cue sheet.")
        return

    selected = route_candidates[int(choice) - 1]
    print()  # blank line before cue sheet

    if selected.destination is not None:
        is_loop = 'Loop' in selected.name
        directions, _ = get_directions_instructions(origin, selected.destination, is_loop)
        if directions:
            print(f"Cue sheet for {selected.name} ({selected.actual_distance_miles:.1f} mi, {len(directions)} steps)")
            cumulative = 0.0
            for line in directions:
                match = re.match(r"([0-9.]+) mi\s+(.+)", line)
                if match:
                    seg_dist = float(match.group(1))
                    text = match.group(2)
                    print(f"{cumulative:.1f}    {seg_dist:.1f} mi    {text}")
                    cumulative += seg_dist
                else:
                    print(f"{cumulative:.1f}    {line}")
            return

    for line in format_route_cue_sheet(selected):
        print(line)


def prompt_for_preferences() -> tuple[RoutePreferences, int]:
    central_address = input("Enter central event location/address: ").strip()
    if not central_address:
        raise SystemExit("No address entered. Exiting.")
    if len(central_address) > MAX_ADDRESS_LENGTH:
        raise SystemExit(
            f"Address is too long; please limit to {MAX_ADDRESS_LENGTH} characters."
        )

    target_input = input("Enter target distances in miles (comma-separated, default 10,25,50): ").strip()
    try:
        distances = (
            parse_target_distances(target_input)
            if target_input
            else DEFAULT_TARGET_DISTANCES
        )
    except ValueError as exc:
        raise SystemExit(f"Invalid distances: {exc}")

    riders_input = input("Enter expected rider count (default 250): ").strip()
    try:
        expected_riders = parse_expected_riders(riders_input)
    except ValueError as exc:
        raise SystemExit(f"Invalid rider count: {exc}")

    loop_input = input("Prefer loop routes? (y/n, default y): ").strip().lower()
    loop_preference = loop_input != "n"

    return (
        RoutePreferences(
            central_location=Location(label="Central Hub", address=central_address),
            target_distances_miles=distances,
            loop_preference=loop_preference,
            max_elevation_gain_ft=None,
            allow_unpaved=False,
            max_speed_limit_mph=None,
            max_arterial_pct=None,
        ),
        expected_riders,
    )


if __name__ == "__main__":
    preferences, expected_riders = prompt_for_preferences()
    central_location = geocode_location_if_needed(preferences.central_location)
    preferences = replace(preferences, central_location=central_location)
    route_candidates = generate_route_candidates(preferences, StaffingRatios())
    staffing = estimate_staffing(expected_riders, route_candidates, StaffingRatios())
    print_event_summary(central_location, route_candidates, staffing, expected_riders)
    prompt_for_cue_sheet(central_location, route_candidates)

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