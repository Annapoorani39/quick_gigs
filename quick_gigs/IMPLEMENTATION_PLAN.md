# Implementation Plan

## Phase 1 — Baseline repair
- Fix missing Django dependencies and verify the app starts cleanly.
- Establish a working venv and confirm the app initializes without import errors.
- Record the current repository state and identify the primary gap between the existing app and the requested SkillMatch product.

## Phase 2 — Core skill engine
- Build a deterministic skill extraction layer for English and Tamil examples.
- Normalize canonical skills and user experience phrases.
- Provide recommendation logic with transparent scoring.
- Create a demo simulation for learning a missing skill and comparing before/after results.

## Phase 3 — API and frontend integration
- Add health and skill-matching API endpoints.
- Add a dashboard page and resume-builder page.
- Add a voice-first demo page with transcript editing and browser speech support warnings.
- Keep the existing marketplace routes working and accessible.

## Phase 4 — Documentation and environment setup
- Add project docs, env templates, and deployment instructions.
- Define limits clearly for demo mode versus real AI APIs.
- Ensure secrets stay out of version control.

## Phase 5 — Verification
- Run regression tests for skill extraction and recommendation logic.
- Validate manage.py startup and the health endpoint.
- Capture any remaining blockers and document them clearly.
