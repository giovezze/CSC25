# Security Risk Assessment — May 7, 2026

This document summarizes the security review of `Cycling.py` and related workspace configuration.

## Findings

### 1. Hardcoded secret exposure
- `Cycling.py` does not hardcode the Google Maps API key.
- `.vscode/launch.json` currently contains `GOOGLE_MAPS_API_KEY` in plaintext.
- This is a real secret exposure risk and should be removed from repository-managed files.

### 2. Missing input validation
- `central_address` is only checked for non-empty value.
- `target_distances_miles` is parsed from arbitrary comma-separated floats and can include zero, negative, or excessively large values.
- `expected_riders` is parsed as any integer without range validation.
- `loop_input` treats any value other than `n` as yes, which is permissive.

### 3. Overly permissive logic / abuse potential
- There is no limit on number of distances entered or the total number of route variants generated.
- This can lead to excessive Google Maps API usage and unexpected costs.
- A malicious or careless user could cause large numbers of API calls.

### 4. Lack of error handling
- External API calls are not wrapped in robust exception handling.
  - `google_maps_client.geocode(...)`
  - `google_maps_client.directions(...)`
- JSON loading in `SavedPlacesRepository._load()` is not protected against malformed or corrupted data.
- Invalid numeric input can raise unhandled exceptions.

### 5. Other risk areas
- `SavedPlacesRepository` writes to a fixed JSON path without explicit path sanitization, though current usage is limited.
- The script depends on `GOOGLE_MAPS_API_KEY` being set externally; this should be documented and managed securely.
- `format_route_cue_sheet()` still generates synthetic street segments in some cases, which is not a security risk but may be misleading.

## Recommendations

1. Remove `GOOGLE_MAPS_API_KEY` from `.vscode/launch.json` and use a local-only environment variable or secret manager. ✅ Implemented.
   - `.vscode/launch.json` was updated to remove the hardcoded key.
   - The user should continue setting the key in their terminal or local environment.
2. Add validation for:
   - distance values (`>= 1`, upper bound of 200 miles)
   - rider count (`>= 1`, upper bound of 2000)
   - maximum number of route entries (`max 5`).
3. Limit route generation and Directions API calls to a bounded number. ✅ Implemented.
   - The planner now generates at most 12 route candidates and bounds Directions API requests accordingly.
4. Wrap external API calls in `try/except` blocks and present friendlier failure messages.
5. Protect JSON file loading with error handling for malformed content.
6. Document the requirement that the API key must be provided via environment variables and not committed.

## Summary

The code has no obvious injection vulnerabilities, but the main security exposures are operational: secret handling, input validation, resource usage, and error handling. Addressing these recommendations will reduce risk and improve robustness.
