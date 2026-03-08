# Runbook and Troubleshooting

This runbook is optimized for demos and fast incident recovery.

## Quickstart runbook

### 1) Start API
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
cp app/.env.example app/.env
python -m uvicorn app.src.app:app --host 0.0.0.0 --port 8000
```

### 2) Expose webhook locally
```bash
ngrok http 8000
```

### 3) Verify health
```bash
curl -i http://127.0.0.1:8000/health
curl -i https://<your-ngrok-url>/health
```

## Playwright runbook

### Install browsers
```bash
cd playwright-tests
npx playwright install
```

### Run tests
```bash
BASE_URL=https://the-internet.herokuapp.com TEST_USER=tomsmith TEST_PASS=SuperSecretPassword! npx playwright test tests/auth.spec.js
```

Expected baseline result:
- 3 passed
- 1 skipped (locked-account scenario intentionally skipped for demo site)

## Common errors and fixes

### 401 Unauthorized
Cause:
- `X-API-Key` header does not match `API_AUTH_TOKEN` in `app/.env`.

Fix:
- Update header in Jira rule.
- Restart API process if token changed.

### 422 json_invalid
Cause:
- Jira smart value inserted raw control characters/newlines.

Fix:
- Use `{{issue.description.asJsonString}}` in webhook body.

### ngrok ERR_NGROK_3200
Cause:
- Tunnel is offline or URL changed.

Fix:
- Restart `ngrok http 8000`.
- Update Jira webhook URL.

### Jira webhook timeout (30s)
Cause:
- Using sync endpoint for long operation.

Fix:
- Use `POST /jira/full-qa-flow-async`.

### browserType.launch: Executable doesn't exist
Cause:
- Playwright browsers missing.

Fix:
- Run `npx playwright install`.

### Cannot find module 'dotenv'
Cause:
- Missing `dotenv` in `playwright-tests`.

Fix:
- `cd playwright-tests && npm install`

### Selector timeout in generated tests
Cause:
- AI-generated selectors do not exist in target app.

Fix:
- Replace with real selectors (`#username`, `#password`, `#flash` for demo app).

## Demo checklist
1. API health is `200`.
2. ngrok URL is active.
3. Jira Rule A points to `/jira/full-qa-flow-async`.
4. Webhook includes `X-API-Key`.
5. Jira issue description includes acceptance criteria.
