from fastapi import APIRouter, Depends, HTTPException

from app.src.schemas import (
    GenerateBothRequest,
    GenerateBothResponse,
    GeneratePlaywrightRequest,
    GeneratePlaywrightResponse,
    GenerateTestsRequest,
    GenerateTestsResponse,
)
from app.src.services.llm_service import (
    build_playwright_prompt,
    build_tests_prompt,
    call_llm,
)
from app.src.security import require_api_key


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/generate-tests",
    response_model=GenerateTestsResponse,
    operation_id="generate_tests",
)
def generate_tests_endpoint(
    payload: GenerateTestsRequest, _: None = Depends(require_api_key)
) -> GenerateTestsResponse:
    try:
        prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        text = call_llm(prompt)
        try:
            return GenerateTestsResponse.model_validate_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Model output did not match the expected schema.",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post(
    "/generate-playwright",
    response_model=GeneratePlaywrightResponse,
    operation_id="generate_playwright",
)
def generate_playwright_endpoint(
    payload: GeneratePlaywrightRequest,
    _: None = Depends(require_api_key),
) -> GeneratePlaywrightResponse:
    try:
        prompt = build_playwright_prompt(
            payload.acceptanceCriteria,
            payload.context,
            payload.baseUrl,
        )
        text = call_llm(prompt)
        try:
            return GeneratePlaywrightResponse.model_validate_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Model output did not match the expected schema.",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post(
    "/generate-both",
    response_model=GenerateBothResponse,
    operation_id="generate_both",
)
def generate_both_endpoint(
    payload: GenerateBothRequest, _: None = Depends(require_api_key)
) -> GenerateBothResponse:
    try:
        tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        tests_text = call_llm(tests_prompt)
        try:
            tests_obj = GenerateTestsResponse.model_validate_json(tests_text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Tests output did not match the expected schema.",
            )

        pw_prompt = build_playwright_prompt(
            payload.acceptanceCriteria, payload.context, payload.baseUrl
        )
        pw_text = call_llm(pw_prompt)
        try:
            pw_obj = GeneratePlaywrightResponse.model_validate_json(pw_text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Playwright output did not match the expected schema.",
            )

        return GenerateBothResponse(tests=tests_obj, playwright=pw_obj)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")
