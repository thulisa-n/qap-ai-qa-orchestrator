# QAP AI QA Engine

AI-driven QA Automation Platform (QAP) that converts Jira tickets into:
- Manual test scenarios
- High-value automation candidates
- Playwright test names
- Security-minded QA notes

## Run locally
1. Copy env file:
   cp app/.env.example app/.env

2. Install dependencies:
   pip install -r app/requirements.txt

3. Start server:
   python -m uvicorn app.src.app:app --reload

## Endpoint
POST /generate-tests
