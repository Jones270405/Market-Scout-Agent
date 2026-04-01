# guardrails/callbacks.py
"""
Input and Output Guardrails for Market Scout.
ADK before_model_callback / after_model_callback hooks.
"""

import re

# ADK callback type imports — wrapped in try/except for version compatibility
try:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.genai.types import Content, Part
except ImportError:
    # Fallback for different ADK versions
    from google.adk.agents import CallbackContext
    from google.adk.models import LlmRequest, LlmResponse
    from google.genai.types import Content, Part

# ─── Block patterns ───────────────────────────────────────────────────────────

HARMFUL_PATTERNS = [
    r"\bhack\b", r"\bexploit\b", r"\bmalware\b", r"\billegal\b",
    r"\bransomware\b", r"\bvirus\b", r"\bphishing\b", r"\bddos\b",
]

INJECTION_PATTERNS = [
    r"jailbreak",
    r"act as",
    r"ignore (previous|all|your) instructions",
    r"you are now",
    r"pretend (you are|to be)",
    r"disregard",
]

PII_PATTERNS = [
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",          # credit card
    r"\b\d{3}-\d{2}-\d{4}\b",                               # SSN
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", # email
]

OUT_OF_SCOPE_PATTERNS = [
    r"\brecipe\b", r"\bweather\b", r"\bhomework\b", r"\bpoem\b",
    r"\bsong\b",   r"\bstory\b",   r"\bjoke\b",     r"\btranslate\b",
]

MIN_QUERY_LEN = 3
MAX_QUERY_LEN = 1000


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_text(request: LlmRequest) -> str:
    """Pulls plain text from the last user turn in the request."""
    try:
        for content in reversed(request.contents or []):
            if content.role == "user":
                for part in content.parts or []:
                    if hasattr(part, "text") and part.text:
                        return part.text.strip()
    except Exception:
        pass
    return ""


def _block(message: str) -> LlmResponse:
    """Builds a blocking LlmResponse that short-circuits the LLM call."""
    return LlmResponse(
        content=Content(
            role="model",
            parts=[Part(text=message)],
        )
    )


# ─── Input guardrail ─────────────────────────────────────────────────────────

def input_guardrail(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
):
    """
    Runs BEFORE the LLM sees the user message.
    Returns None  → allow the request through.
    Returns LlmResponse → block and reply immediately.
    """
    text = _extract_text(llm_request)

    if not text:
        return None

    lower = text.lower()

    # Length guards
    if len(text) < MIN_QUERY_LEN:
        return _block(
            f"⚠️ Query too short (min {MIN_QUERY_LEN} chars). "
            "Please enter a company name, e.g. 'Track Stripe'."
        )
    if len(text) > MAX_QUERY_LEN:
        return _block(
            f"⚠️ Query too long (max {MAX_QUERY_LEN} chars). "
            "Please shorten your request."
        )

    # Harmful intent
    for pattern in HARMFUL_PATTERNS:
        if re.search(pattern, lower):
            return _block(
                "🚫 Harmful intent detected. "
                "I can only help with competitor intelligence."
            )

    # Prompt injection
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            return _block(
                "🚫 Prompt injection attempt detected. "
                "I can only help with competitor intelligence."
            )

    # PII in input
    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            return _block(
                "🚫 Personal information detected in your query. "
                "Please enter only a company name to track."
            )

    # Out of scope
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, lower):
            return _block(
                "ℹ️ I only track competitor updates. "
                "Try: 'Track Stripe' or 'Compare PayPal and Stripe'."
            )

    return None  # ✅ Allow through


# ─── Output guardrail ────────────────────────────────────────────────────────

def output_guardrail(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
):
    """
    Runs AFTER the LLM produces its response.
    Redacts any PII that may have leaked into the output.
    Returns None → pass through unchanged.
    Returns LlmResponse → replace with sanitised version.
    """
    try:
        if not llm_response.content or not llm_response.content.parts:
            return None

        modified  = False
        new_parts = []

        for part in llm_response.content.parts:
            if hasattr(part, "text") and part.text:
                text = part.text
                for pattern in PII_PATTERNS:
                    sanitised = re.sub(pattern, "[REDACTED]", text)
                    if sanitised != text:
                        text     = sanitised
                        modified = True
                new_parts.append(Part(text=text))
            else:
                new_parts.append(part)

        if modified:
            return LlmResponse(
                content=Content(role="model", parts=new_parts)
            )

    except Exception:
        pass

    return None  # ✅ Pass through unchanged