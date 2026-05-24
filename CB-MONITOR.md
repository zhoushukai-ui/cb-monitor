# CB Monitor — Project Conventions

## Development Process

- **Test-Driven Development**: All new features and bug fixes must include corresponding test cases. Run the full test suite before reporting work as complete:
  ```bash
  python -m pytest backend/tests/ -v
  ```
- When fixing a bug, first add a test that reproduces the issue, then fix the code, then verify the test passes.
- Tests use in-memory SQLite (`sqlite+aiosqlite://`) with fixtures in `backend/tests/conftest.py`.

## Architecture Principles

### Mobile Deployment Readiness
Design with the expectation that most users will access via mobile. While current development is web-only, the architecture should not assume a desktop-only environment:
- API layer should remain clean and separate from presentation
- Avoid desktop-specific assumptions in backend data APIs
- Responsive frontend patterns preferred where practical

### Crawling Strategy

With ~300 convertible bonds, announcement-link crawling is distributed evenly across the day:
- ~1 request per 3-8 minutes (randomized interval)
- Distributed across 24 hours to avoid triggering rate limits on public disclosure sites (巨潮资讯网)
- Randomized daily schedule (not fixed interval) — requests land at different times each day

## Project Structure

- `backend/` — FastAPI application
- `backend/routers/` — API and page routes
- `backend/services/` — Data collection (akshare, Tushare)
- `backend/templates/` — Jinja2 templates
- `backend/locales/` — i18n JSON files (en, zh)
- `backend/tests/` — Pytest test suite
- `deploy/` — Docker and deployment config

## Config

- Environment variables via `.env` file
- `ADMIN_TOKEN` — enables admin portal at `/admin`
- `TUSHARE_TOKEN` — enables stock fundamentals data
