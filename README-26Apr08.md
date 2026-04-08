# Cycling Event Planner — Today’s Debugging Summary

This summary captures the changes made to `Cycling.py` during today’s session, including debugging, logic updates, edge case handling, and validation test results.  When evaluating for correctness there were a few improvements made to correct input validation - making nulls OK on optional and ensuring preventing crashes on miles.  THe logical evaluation resulted in improvements to rest stop assesments...it assumed no re-use.  Efficiency was clean.  Apropriate had two minor changes in cleaner comments and more appropriate variable names.  Readability review resulted in several more comments to make it clearer to someone coming back to it after 6 months.

## Overview

Charity Cycling Event Scheduler
Route & Staffing Planner – Planning Prototype
Overview
This repository contains a planning‑focused prototype for organizing a charity cycling event.
The current implementation helps event organizers:

Generate candidate cycling routes from a central hub
Estimate staffing and volunteer needs based on those routes

The tool is intentionally conservative, explainable, and interactive, designed to support planning discussions and scenario evaluation, not final operational commitments.

Purpose and Scope
What This Tool Is

A planning aid for ride directors and operations leads
A way to test “what if” scenarios (routes, distances, rider counts)
A foundation for future expansion (GIS routing, permits, budgeting)

What This Tool Is Not (Yet)

A navigation or turn‑by‑turn routing system
A GIS‑backed or map‑accurate route engine
A production scheduling or workforce management system
A permitting, police coordination, or government submission tool

All outputs should be treated as planning estimates, not guarantees or commitments.

Current Capabilities
1. Route Generation (Prototype Logic)
The system prompts the user for basic route preferences:

Central start/finish latitude and longitude
Target ride distances (e.g., 10, 25, 50 miles)
Loop preference and optional constraints (captured for future use)

Using these inputs, the program generates multiple candidate routes per distance using simple heuristics:

Distance (exactly as requested)
Estimated elevation gain (heuristic)
Estimated turn count (heuristic)
Safety score (0–100, heuristic)
Placeholder geometry (WKT string)


⚠️ Note
Route generation is deliberately a placeholder.
It produces planning artifacts, not real road‑network routes.


2. Staffing & Volunteer Estimation
Staffing estimates are route‑aware, not based solely on rider count.
The model estimates:

SAG vehicles
Hub mechanics
Roving mechanics
Signage teams
Rest stop leads
Rest stop volunteers
Registration volunteers

Key characteristics of the staffing logic:

Uses worst‑case representative routes per distance
Scales support based on route count, distance, and complexity
Applies conservative assumptions to avoid under‑staffing


3. Shared Rest‑Stop Logic (Corrected)
A major logic improvement was made to properly model shared rest stops.
Key principle:

Physical rest stops are determined by the longest route.
Sharing reduces staffing per stop, not the number of stops.

How this works:

The number of physical rest stops is based on spacing along the longest route
Early stops (used by many routes) are staffed more heavily
Later stops (used by fewer routes) are right‑sized
Total volunteers never increase due to sharing

This aligns with real‑world event operations and significantly reduces unnecessary volunteer estimates.

4. Registration Staffing Model
Registration is modeled as a flow problem, not a flat ratio:

Accounts for early registration opening
Accounts for staggered route start times
Spreads arrivals over a realistic window
Estimates the number of volunteers required to avoid long waits

This approach is more realistic than simple “riders ÷ volunteers” formulas.

5. Interactive CLI Workflow
The prototype is operated via a simple command‑line menu:
1) Generate candidate routes
2) Estimate staffing & volunteers
3) Generate routes + estimate staffing
4) Exit

This supports iterative planning and discussion:

Adjust routes
Change rider counts
Re‑run estimates quickly


Validation & Testing Performed
Correctness

Fixed crashes caused by realistic user input (e.g., “10, 25, 50 miles”)
Implemented robust input validation and re‑prompting
Ensured optional inputs behave as optional
Enforced domain guardrails (e.g., positive distances, positive riders)

Logic

Verified that staffing scales logically with:

Rider count
Route distance
Route complexity


Corrected shared rest‑stop logic to prevent unintended increases
Confirmed conservative, worst‑case planning bias

Efficiency

All computations are O(n) with very small inputs
No unnecessary recomputation
No premature optimization
Performance is more than sufficient for intended scale

Appropriateness

Assumptions match common charity ride practices
Conservative bias is appropriate for public safety
Simplifications are intentional and documented
Design fits prototype stage without over‑engineering

Readability

Added intent‑focused comments explaining why, not just what
Clearly labeled heuristics and assumptions
Added narrative structure and “how to read this file” guidance
Labeled outputs explicitly as planning estimates


Example Validation Run (Brookdale)
Inputs

Central location: Brookdale
Route distances: 10 mi, 25 mi, 50 mi
Total riders: 250

Outputs (Planning Estimates)

SAG vehicles: 5
Hub mechanics: 1
Roving mechanics: 3
Total mechanics: 4
Signage teams: 18
Rest stop leads: 5
Rest stop volunteers: reduced via shared‑stop logic
Registration volunteers: 2

These results were reviewed for internal consistency and realism.

Design Philosophy

Plan conservatively to avoid under‑support
Prefer explainable heuristics over opaque optimization
Fail safely (over‑estimate rather than under‑estimate)
Defer complexity (GIS, permits, databases) until requirements stabilize


Future Enhancements (Not Yet Implemented)
Potential next steps include:

Portable bathroom estimation (using similar shared‑logic)
Food and water supply planning
Cost and budget modeling
Permit and jurisdiction overlays
Real GIS‑based routing
Modularization into routing, staffing, and CLI components

Each can be added incrementally without reworking the current core logic.

Summary
This prototype successfully demonstrates that:

Route characteristics meaningfully drive staffing needs
Shared infrastructure can reduce volunteer demand when modeled correctly
A simple, conservative, and explainable approach produces realistic planning outputs

The current codebase represents a stable, validated planning foundation suitable for further evolution.