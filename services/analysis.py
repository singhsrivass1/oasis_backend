"""Structured, schema-constrained security analysis via Gemini.

Note on claims (task section 32): this pipeline is schema-constrained,
temperature=0, and Pydantic-validated -- it is NOT a guarantee of zero
hallucination. Any user-facing copy describing this must say
"structured / schema-constrained / validated", never "zero hallucinations".
"""
from __future__ import annotations

from functools import lru_cache

from google import genai
from google.genai import types

from config import settings
from schemas.webhook import OasisAnalysisResponse

SYSTEM_INSTRUCTION = (
    "You are an elite Staff-Level Application Security Engineer and DevSecOps Architect. "
    "Your mandate is to perform a rigorous, infrastructure-grade security audit on the provided GitHub Pull Request diff. "
    "Execute your analysis against the OWASP Top 10 framework and CWE mapping. "
    "MANDATORY DIRECTIVES: "
    "1. EXHAUSTIVE DISCOVERY: You must identify every vulnerability, logical flaw, race condition, hardcoded secret, and performance bottleneck. Do not stop at the first finding. "
    "2. PRECISION: Structured, schema-validated output. If the code is perfectly secure, classify severity as 'advisory'. "
    "3. PROFESSIONAL TONE: Use clinical, objective, and highly technical terminology. Avoid conversational filler. "
    "4. REMEDIATION: Provide a complete, production-ready, drop-in code replacement that resolves all identified issues simultaneously. The patch must maintain existing business logic and require zero modifications by the developer."
)


@lru_cache(maxsize=1)
def get_ai_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=settings.gemini_api_key)


def analyze_diff(diff_text: str) -> OasisAnalysisResponse:
    client = get_ai_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=f"Analyze this repository file diff:\n\n{diff_text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=OasisAnalysisResponse,
            temperature=0.0,
        ),
    )
    return response.parsed
