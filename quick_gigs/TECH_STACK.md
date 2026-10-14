# Technology Stack

## Frontend
- Django templates with vanilla HTML/CSS/JS for the current implementation.
- Responsive layout and modern card-based design with accessibility-friendly controls.
- Client-side speech recognition where supported by the browser.

## Backend
- Python 3.14 in the local workspace environment.
- Django 6.0.2 as the primary framework.
- Django auth and profile flows for the app’s user management.

## Database
- SQLite for the current local demo environment.
- Existing user, gig, application, and rating models are preserved and used.

## AI providers
- This implementation uses a deterministic, explainable skill-matching engine rather than hard-coded external AI provider calls.
- Real provider integrations are optional and documented as future extension points.

## NLP and skill extraction
- Curated skill ontology with English and Tamil alias matching.
- Rule-based extraction with transparent, reviewable outputs.

## Embeddings and semantic search
- Not implemented in the current deployment; the system avoids claiming vector search when no embedding pipeline exists.

## Recommendation engine
- Current job-match page uses open `Gig` rows from SQLite and the transparent formula: matched required skills / total listed required skills × 100.
- Missing skills and curated or general learning links are displayed alongside each match.
- Jobs without requirements show no percentage.
- The separate curated skill engine remains available for unit-tested recommendation/demo helpers; those seeded roles are not represented as live jobs in the current website.

## Authentication
- Django auth plus user profiles and allauth-ready configuration.

## Voice recognition
- Browser Web Speech API when supported.
- Manual typed fallback preserved when speech recognition is unavailable.

## Resume generation
- Editable resume form backed by the existing Django API.
- PDF and DOCX extraction uses pypdf and python-docx; uploads are size-limited and processed in memory, not saved.
- Latin-script PDF download generated with ReportLab; Tamil and other non-Latin text uses browser print/save-as-PDF so glyph shaping is preserved.
- No unsupported or invented credentials are added without user input. Scanned-document OCR is not implemented.

## Storage
- Local media storage in the existing Django project configuration.

## Visualizations
- Responsive match cards display scores calculated from the current open job records.
- Per-page learning progress is client-side only and is not persisted.

## Testing
- Django tests for skill extraction, database-backed matching, zero/no-requirement scoring, PDF and DOCX uploads, PDF downloads, and profile skill persistence.
- JavaScript syntax is validated with Node.js; no npm build is applicable because the frontend has no `package.json`.

## Deployment
- Prepared for Django app hosting environments with environment-based config variables.
- Public deployment requires credentials and access that are not available in this workspace.

## Monitoring
- Health endpoint and structured JSON responses are exposed for uptime checks.

## Security
- Secret keys and credentials are kept out of the source tree via environment configuration and .gitignore.
- Resume files are not stored; file type and size are checked and skill persistence requires authentication and CSRF.
- Resume generation/PDF endpoints process only request data and do not persist resume details.
