# Contributing Guide

Thanks for contributing to QAP AI QA Engine.

## Development setup
1. Clone the repository.
2. Create and activate Python virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
3. Install backend dependencies:
   - `pip install -r app/requirements.txt`
4. Install Playwright dependencies:
   - `cd playwright-tests`
   - `npm install`
   - `npx playwright install`

## Run checks before opening a PR
- Backend tests:
  - `PYTHONPATH=. python -m pytest app/tests -q`
- Playwright tests:
  - `cd playwright-tests`
  - `BASE_URL=https://the-internet.herokuapp.com TEST_USER=tomsmith TEST_PASS=SuperSecretPassword! npm test`

## Branch and commit conventions
- Prefer feature branches for changes (for example: `feature/readme-observability`).
- Keep commits focused and descriptive.
- Include the "why" in commit messages, not only the "what".

## Pull request checklist
- [ ] Changes are scoped and documented.
- [ ] README/docs updated if behavior changed.
- [ ] Tests added or updated when relevant.
- [ ] CI passes in Bitbucket and/or GitHub Actions.
- [ ] No secrets included in committed files.

## Security expectations
- Never commit `.env` files or API tokens.
- Follow existing input validation and path safety patterns in `app/src/schemas.py` and `app/src/services/file_service.py`.
- Keep error responses generic to avoid leaking internal details.
