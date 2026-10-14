# Architecture

## High-level design
The project follows a Django monolith architecture with a single application, `pages`, that contains both the original marketplace features and the new SkillMatch AI user journey. This keeps the existing functionality stable while layering resume generation, skill extraction, and explainable job matching on top of the current data model.

## Layers
1. Presentation layer
   - Django templates and static CSS/JS.
   - Responsive pages for dashboard, resume builder, voice demo, and marketplace flows.
2. Application logic
   - Existing job and profile actions in `pages/views.py`.
   - New skill extraction and recommendation logic in `pages/skillmatch.py`.
3. Data layer
   - `User`, `UserProfile`, `Gig`, `Application`, and rating models already exist in the app.
   - Current local config uses SQLite for demo and development use.
4. API layer
   - Skill extraction endpoint.
   - Resume generation endpoint.
   - Job recommendation endpoint.
   - Matching simulation endpoint.
5. Demo/demo-safe outputs
   - Deterministic recommendation engine and synthetic job dataset.
   - Browser speech support with typed fallback in unsupported environments.

## Design principles
- Prefer deterministic logic over unsupported AI claims.
- Explain recommendations transparently.
- Preserve existing app functionality.
- Keep the product usable for low-literacy and low-bandwidth users.
