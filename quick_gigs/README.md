# SkillMatch AI

SkillMatch AI is a Django-based career platform for people whose real-world experience may not be reflected in formal degrees. The system focuses on practical skills, voice-first experience capture, explainable job matching, and resume generation from spoken or written experience.

## Product goals
- Recognize and normalize real-world skills from user experience.
- Match users to jobs based on skills, location, and language compatibility.
- Generate a resume from confirmed experience without inventing qualifications.
- Support a demo-friendly, multilingual flow for English and Tamil users.

## Current implementation status
This repository preserves the existing marketplace features while adding a demo-ready SkillMatch layer built on top of Django. The platform is intentionally deterministic and transparent rather than claiming unsupported AI behavior without a real provider.

## SkillMatch features
- **Voice experience capture:** English and Tamil browser speech recognition where supported, with editable transcript and typed fallback.
- **Resume extraction:** PDF and DOCX text extraction; detected skills and labeled sections are suggestions for review. Scanned PDFs need OCR and are not interpreted.
- **Resume builder:** Editable contact, objective, education, skills, projects, experience, certifications, languages, and target-job fields; PDF download. Tamil and other non-Latin text uses the browser print/save-as-PDF flow to avoid corrupted glyphs.
- **Job matching:** `/job-matches/` compares the profile with open jobs stored in the existing `Gig` database. Formula: matched listed required skills / all listed required skills × 100. Jobs without requirements receive no score. No demo vacancy is presented as live.
- **Skill gaps:** Matched and missing requirements, learning links, and temporary per-page progress tracking.
- **Skill improvement simulator:** Projects best match changes after adding a skill against jobs with listed requirements; it does not persist simulated data.
- **Profile privacy:** Resume uploads are size-limited, processed in memory, and not stored. Saving reviewed skills requires login and CSRF protection.

## Quick start
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open:
- http://localhost:8000/
- http://localhost:8000/dashboard/
- http://localhost:8000/job-matches/
- http://localhost:8000/resume-builder/
- http://localhost:8000/voice-demo/

## Key files
- `pages/skillmatch.py` — skill extraction, scoring, and recommendation engine.
- `pages/views.py` — job and SkillMatch endpoints.
- `templates/skillmatch-dashboard.html` — dashboard experience.
- `templates/job-matches.html` — published job matches and skill gaps.
- `templates/resume-builder.html` — resume workflow.
- `templates/voice-demo.html` — voice-first experience capture.
- `static/js/skillmatch.js` — browser speech, extraction, resume, and live matching interactions.

## Verification
Run backend checks and tests from the project directory:
```powershell
python manage.py check
python manage.py test pages
```

There is no `package.json`: the current frontend is server-rendered Django templates with HTML, CSS, and vanilla JavaScript, so no npm build step is required.

## Documentation
- `PROJECT_AUDIT.md`
- `IMPLEMENTATION_PLAN.md`
- `TECH_STACK.md`
- `ARCHITECTURE.md`
- `DEPLOYMENT.md`
- `PROGRESS.md`
