# temporal_validation_agent/agent.py
"""
Temporal Validation Sub-Agent
Validates published dates and assigns WEEK / MONTH / YEAR / STALE / UNVERIFIED
status. Also categorises each feature by snippet keywords.
"""

from datetime import datetime, timedelta
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool


def validate_by_timeframe(features: list) -> list:
    """
    Validates each feature's published date and assigns recency status:
      WEEK       — published within last 7 days
      MONTH      — published within last 30 days
      YEAR       — published within last 365 days
      STALE      — older than 365 days
      UNVERIFIED — date missing or unparseable

    Also assigns category: API | Integration | Security | Performance | Product
    """
    today   = datetime.now()
    cutoffs = {
        "WEEK" : today - timedelta(days=7),
        "MONTH": today - timedelta(days=30),
        "YEAR" : today - timedelta(days=365),
    }

    for f in features:
        snippet = f.get("snippet", "").lower()

        # ── Categorise ──
        if "api" in snippet:
            f["category"] = "API"
        elif "integration" in snippet or "partnership" in snippet:
            f["category"] = "Integration"
        elif "security" in snippet or "tls" in snippet or "certificate" in snippet:
            f["category"] = "Security"
        elif "performance" in snippet:
            f["category"] = "Performance"
        else:
            f["category"] = "Product"

        # ── Validate date ──
        date_str = f.get("date", "unknown").strip()

        if date_str.lower() in ["unknown", "", "none", "null"]:
            f["status"] = "UNVERIFIED"
            continue

        try:
            if len(date_str) == 4 and date_str.isdigit():
                date_str = f"{date_str}-01-01"

            pub_date = datetime.strptime(date_str[:10], "%Y-%m-%d")

            if pub_date >= cutoffs["WEEK"]:
                f["status"] = "WEEK"
            elif pub_date >= cutoffs["MONTH"]:
                f["status"] = "MONTH"
            elif pub_date >= cutoffs["YEAR"]:
                f["status"] = "YEAR"
            else:
                f["status"] = "STALE"

            f["date"] = date_str[:10]

        except Exception:
            f["status"] = "UNVERIFIED"

    return features


validation_tool = FunctionTool(func=validate_by_timeframe)

temporal_validation_agent = LlmAgent(
    name="temporal_validation_agent",
    model=LiteLlm(model="groq/llama-3.1-8b-instant"),
    description="Validates feature dates and assigns WEEK/MONTH/YEAR/STALE/UNVERIFIED status.",
    instruction="""You are a Temporal Validation Agent.
When given a list of feature dicts, call validate_by_timeframe with that list.
Return the resulting validated list exactly as received.
""",
    tools=[validation_tool],
)