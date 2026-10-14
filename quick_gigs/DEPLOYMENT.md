# Deployment Notes

## Local development
1. Activate the workspace venv.
2. Install dependencies: `pip install -r requirements.txt`.
3. Apply migrations: `python manage.py migrate`.
4. Start the server: `python manage.py runserver`.
5. Open the dashboard at `http://localhost:8000/dashboard/`.

## Environment configuration
- Copy `.env.example` to `.env` and fill in your own values.
- Keep keys private and outside version control.

## Production guidance
- Use a hosted Django environment such as Render or a comparable provider.
- Set `DEBUG=False` and configure a secure secret key.
- Serve static and media files using a proper storage strategy.
- Use environment variables instead of hard-coded settings.
- Replace SQLite with PostgreSQL when moving beyond the demo stage.

## Verification checklist
- Health endpoint resolves.
- Database migrations succeed.
- Public frontend points to the deployed backend URL, not localhost.
- CORS is restricted to the allowed origins.
- Sensitive credentials are not embedded in templates or JS.
