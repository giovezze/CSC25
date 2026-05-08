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
4. Wrap external API calls in `try/except` blocks and present friendlier failure messages. ✅ Implemented.
   - Geocoding, reverse geocoding, and Directions API calls now return controlled failures instead of crashing.
5. Protect JSON file loading with error handling for malformed content. ✅ Implemented.
   - `SavedPlacesRepository._load()` now falls back to an empty store on corrupted JSON.
6. Document the requirement that the API key must be provided via environment variables and not committed.

## Summary

The code has no obvious injection vulnerabilities, but the main security exposures are operational: secret handling, input validation, resource usage, and error handling. Addressing these recommendations will reduce risk and improve robustness.

RAN OUT OF co-pilot chat messages.  Switched to CHAT GPT.  

Here is log of that conversation. I have serious reservations about co-pilot.  Had a logic issue that it took 6 tries to get close on with it.  Exhausted my allowance.  Chat-GPT helped in one try.  

Summary of What Was Fixed
✅ Runtime & Correctness

Fixed broken type hints
Unified distance parsing
Guarded math edge cases
Removed duplicate logic paths

✅ Logic Restored

Representative routes used for staffing
Rest stops based on longest route
Shared-stop inflation eliminated
Mechanics tied to SAG, not variants

✅ API Safety

Cached geocoding
Hard cap on route candidates
Limited Directions calls
Directions only used after pruning


✅ Where You Are Now
You now have:

A correct
logically consistent
API-safe
readable
appropriate
extensible

planning prototype.
If you want next, we can:

Reintroduce shared-stop staffing tiers
Add bathrooms/food modeling
Add scenario comparison
Add dry-run / no-API mode
Add unit-style validation checks

Just tell me where you want to go next.
Provide your feedback on BizChatYou said: Looks good,  ran well.   At this point I want you to put on your security expert hat. Lets review the code to ensure it is secure and poses little to know exposure for exploitation.
Look for:
Missing input validation
Hardcoded secrets
Overly permissive logic
Lack of error handling
other risks that bad actors can exploitCopilot said: CopilotGreat question — this is exactly the right moment to do a security review, because the code is now functional, correct, and feature‑rich. I’ll put on the security engineer hat and walk through this systematically.
I’ll cover the areas you asked for and a few additional ones that matter for a tool like this.

Security Review of the Enhanced Planning Prototype
Threat Model (Important Context)
Before diving in, it’s important to define what we’re protecting against.
This is a local, operator‑run planning tool, not a public web service.
So the primary risks are:

Accidental exposure of secrets (API keys)
Unexpected crashes or data leakage
API abuse (quota exhaustion, cost exposure)
Malicious or malformed user input
Unsafe file or OS interactions (now or in the future)

We are not dealing with:

Authentication
Multi‑tenant access
Network‑exposed endpoints
Untrusted remote users

That means our bar is:
✅ “Low risk of accidental misuse or easy exploitation.”

1️⃣ Secrets Management
✅ What You Did Right

No hardcoded secrets
API key is read from environment variable:
PythonGOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")Show more lines

Program fails fast if key is missing

✅ This is best practice.

⚠️ Remaining Risks
Risk: Accidental key leakage via logs or stack traces

If a Google Maps call raises an exception, Python may print a stack trace
Stack trace could include request details (rare, but possible)

✅ Mitigation (Recommended)

Catch and sanitize exceptions around Google Maps calls
Avoid printing exception objects directly

Severity: Low
Likelihood: Low
Impact: Medium (API key misuse)

2️⃣ Input Validation (User‑Supplied Data)
✅ What Is Strong
You have robust validation for:

Route distances
Rider counts
Address length
Empty inputs
Numeric ranges

Examples:
Pythonif not (MIN_DISTANCE_MILES <= value <= MAX_DISTANCE_MILES):Show more lines
✅ This significantly reduces malformed input risk.

⚠️ Remaining Gaps
A. Address Input Is Not Sanitized Beyond Length
Pythonaddress = input("Enter central event address: ").strip()``Show more lines
While this is not directly dangerous, addresses are passed to:

Google Geocoding
Printed to console

Risk vectors:

Terminal escape characters
Very long Unicode strings
Control characters

✅ Mitigation (Recommended)

Strip control characters
Optionally restrict to printable characters

Severity: Low
Likelihood: Low
Impact: Low

B. Regex Use on Google HTML Instructions
Pythontext = re.sub(r"<.*?>", "", html)Show more lines
This is safe, but:

Regex is greedy
Could behave unexpectedly with malformed HTML

✅ Acceptable for prototype
✅ No code execution risk
✅ No injection vector

3️⃣ Overly Permissive Logic
✅ What Is Well‑Contained

No file writes except optional JSON (saved places removed in this version)
No dynamic code execution
No shell calls
No eval/exec
No filesystem traversal

✅ Very good containment.

⚠️ Over‑Permissive API Usage (Primary Risk)
Risk: Google Maps API quota exhaustion
Even after fixes, this line is still the largest security/cost risk:
Pythongoogle_maps_client.directions(...)Show more lines
Why this matters:

A user can repeatedly run the tool
Each run can make multiple paid API calls
A malicious or careless user can burn quota

✅ You already mitigated this partially by:

Capping variants
Limiting bearings
Limiting candidates

✅ Further Mitigations (Strongly Recommended)

Add a hard per‑run API call budget
Add a --dry-run or NO_API mode
Cache Directions results (in‑memory or file)

Severity: Medium
Likelihood: Medium
Impact: High (cost)

4️⃣ Error Handling & Fail‑Safe Behavior
✅ What You Did Right

Fail fast when API key is missing
Guard against empty results
Validate numerical inputs
Avoid division by zero in most places

✅ The program generally fails safely.

⚠️ Remaining Error‑Handling Gaps
A. Uncaught Google API Exceptions
Example:
Pythondirections = google_maps_client.directions(...)Show more lines
If Google returns:

Rate‑limit error
Network error
Malformed response

The program may crash.
✅ Mitigation (Recommended)
Wrap API calls in try/except and degrade gracefully:

Skip candidate
Warn user
Continue planning


B. Trusting Google Response Structure
You assume:
Pythonleg["distance"]["value"]Show more lines
If Google changes schema or returns partial data:

KeyError
TypeError

✅ Acceptable risk for prototype
✅ But worth guarding if shared with others

5️⃣ File & OS Interaction Risks
✅ Current Status: Very Safe

No file writes
No user‑controlled file paths
No path traversal
No permissions issues

✅ Excellent security posture here.

6️⃣ Data Leakage & Privacy
✅ What You Avoided

No persistence of addresses or routes
No logging to disk
No exporting of PII
No telemetry

✅ Good privacy posture.

⚠️ Minor Consideration

Console output includes addresses and coordinates
If logs are captured centrally, this could be sensitive

✅ Acceptable for planning
✅ Just document it

7️⃣ Dependency Risk
googlemaps Library
✅ Well‑known library
✅ Maintained
✅ No dynamic execution
⚠️ Ensure:

Version is pinned if this moves to shared usage
Dependency updates are reviewed


✅ Security Scorecard


AreaStatusHardcoded secrets✅ NoneAPI key handling✅ GoodInput validation✅ StrongInjection risks✅ NoneFile system risks✅ NoneAPI abuse risk⚠️ ModerateError handling⚠️ PartialExploit surface✅ Very small

✅ Summary Verdict

This code poses LOW SECURITY RISK for its intended use.

The only meaningful exposure is:

Google Maps API quota / cost abuse
Uncaught API errors causing crashes

Both are manageable and not exploitable in the traditional sense.

✅ Recommended Security Improvements (Priority Order)
🔒 High Value / Low Cost

Wrap all Google Maps API calls in try/except
Add per‑run API call limit
Add optional “no API” / “dry run” mode

🔒 Nice to Have

Sanitize address input (printable chars only)
Guard against unexpected API response shapes
Add warning banner when using live APIs


✅ Bottom Line
You’ve done a very solid job from a security standpoint — especially for a prototype.
If this were:

A public web service → more work needed
A shared internal tool → add API throttling
A personal planning tool → already acceptable

If you want, next I can:

Apply the security fixes directly to the code
Add a dry‑run / offline mode
Add a security checklist to the README
Do a cost‑risk hardening pass

Just tell me how far you want to go.
Provide your feedback on BizChatYou said: Lets do the high value fixes....Copilot said: CopilotPerfect. I’ll apply only the high‑value security fixes we agreed on, without changing your planning logic, and then show you the full corrected code.
✅ High‑Value Security Fixes Applied
I implemented exactly these:


API call safety

Centralized, counted Google Maps API calls
Hard per‑run API call budget
Graceful degradation when the limit is hit (no crash)

rror handling around all Google Maps calls

No raw exceptions bubbling to the console
Fail‑soft behavior (skip candidate, warn user)

Dry‑run / no‑API mode

Allows safe testing without consuming quota
Controlled by environment variable



Input sanitization

Strip control characters from addresses
Prevent terminal escape abuse

Safer logging

No exception objects printed directly
No accidental key leakage

Nothing else was changed.

Risk AreaStatusHardcoded secrets✅ NoneAPI abuse✅ CappedAPI crashes✅ HandledInput abuse✅ SanitizedTerminal injection✅ PreventedFail‑safe behavior✅ YesCost exposure✅ Controlled

✅ Final Verdict
You now have a secure, cost‑aware, fail‑soft planning prototype that is:

Safe to run repeatedly
Safe to share internally
Safe from easy misuse
Safe from accidental API abuse

If you want next, I can:

Add a security checklist to README
Add a per‑run API usage report
Add offline test fixtures
Add unit tests for abuse scenarios

Just say the word.
Provide your feedback on BizChatYou said: That looks good.  Now I would like you to document the code so that an intermediate level programmer can read, understand, improve and debug.  Limit improvements to commenting.Copilot said: CopilotExcellent request — this is the right final step before sharing or extending the code.
Below is your full program, unchanged in logic or behavior, with only comments added or expanded so that an intermediate‑level programmer can:

Understand what each section does
Understand why design decisions were made
Debug issues safely
Improve or extend the code confidently

I have not:

Changed algorithms
Changed control flow
Changed security logic
Changed APIs
Added features

This is documentation-only.


✅ What This Documentation Achieves
An intermediate developer can now:
✅ Understand the planning philosophy
✅ Identify heuristics vs rules
✅ Safely debug Google Maps interactions
✅ Extend routing logic later
✅ Modify staffing ratios confidently
✅ Reason about security controls