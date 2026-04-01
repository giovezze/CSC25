# Cycling Event Planner — Today’s Debugging Summary

This summary captures the changes made to `Cycling.py` during today’s session, including debugging, logic updates, edge case handling, and validation test results.

## Overview

The code was originally overestimating signage teams and rest stop staffing because it treated all generated candidate routes as independent support needs. Today’s work corrected that assumption and introduced more realistic models for overlapping routes and registration demand.

## Key Debugging Work

- Identified that the staffing logic was summing candidate route turns and rest stop requirements across every alternate route option.
- Confirmed the real-world intent: multiple distance options often share the same physical route corridor, so support should be sized for the most demanding active route rather than every candidate.
- Preserved the prototype route generator while changing the staffing model to operate on representative final routes.

## Logic Changes

- Added `select_representative_routes()` to choose one representative route per unique distance, using the candidate with the highest turn count.
- Changed rest stop estimation to size rest stops based on the longest selected course, rather than summing all candidate distances.
- Changed signage estimation to size signage teams based on the most demanding selected route, with support for nested, partial-overlap, and separate route modes.
- Added `route_support_model` to `StaffingRatios` with values:
  - `nested`
  - `partial_overlap`
  - `separate`
- Added shared route overlap heuristics to estimate how much support can be reused.
- Updated registration volunteer estimates to model staggered start waves, with registration opening 2 hours before the first ride and start waves spaced by route distance.
- Extended SAG vehicle estimation so separate corridors require more support than nested routes.

## Edge Case Handling

- Added handling for `routes` being empty.
- Ensured `total_riders = 0` still returns minimum safe staffing values rather than zero staffing.
- Added route support models so the system can reflect nested routes, partial overlap, or fully separate courses.
- Added a registration window calculation that uses lead time plus wave spacing to flatten demand.

## Test Case Development

Five validation cases were created to verify the updated behavior:

1. Nested shared support with 3 routes (10mi, 25mi, 50mi).
2. Separate support with 3 routes.
3. Partial overlap support with 3 routes.
4. Single long route (50mi only).
5. Edge case with zero riders and one route.

## Test Results

All tests passed with the expected outputs:

- **Test 1 (nested)**
  - `sag_vehicles=3`
  - `signage_teams=4`
  - `rest_stop_leads=5`
  - `rest_stop_volunteers=25`
  - `registration_volunteers=2`

- **Test 2 (separate)**
  - `sag_vehicles=4`
  - `signage_teams=6`
  - `rest_stop_leads=9`
  - `rest_stop_volunteers=45`
  - `registration_volunteers=2`

- **Test 3 (partial overlap)**
  - `sag_vehicles=4`
  - `signage_teams=5`
  - `rest_stop_leads=5`
  - `rest_stop_volunteers=25`
  - `registration_volunteers=2`

- **Test 4 (single long route)**
  - `sag_vehicles=2`
  - `signage_teams=4`
  - `rest_stop_leads=5`
  - `rest_stop_volunteers=25`
  - `registration_volunteers=1`

- **Test 5 (zero riders)**
  - `sag_vehicles=1`
  - `signage_teams=1`
  - `rest_stop_leads=1`
  - `rest_stop_volunteers=5`
  - `registration_volunteers=1`

## Notes

- The file modified is `Cycling.py`.
- The current implementation now reflects real-world route overlap assumptions more accurately.
- Additional future work could further refine SAG capacity by modeling actual route duration and shared corridor length explicitly.
