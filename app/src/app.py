from fastapi import FastAPI
from fastapi.responses import Response

from app.src.routers.generation import router as generation_router
from app.src.routers.jira import router as jira_router


app = FastAPI(
    title="AI QA Engine",
    description=(
        "AI-driven QA automation API that generates structured scenarios, "
        "Playwright tests, and Jira automation artifacts."
    ),
)

app.include_router(generation_router)
app.include_router(jira_router)


@app.middleware("http")
async def add_security_headers(request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response
