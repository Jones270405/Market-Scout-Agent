"""
cl_app.py — Chainlit chat logic (mounted into FastAPI via app.py)
"""

import os
import re
import sys
from pathlib import Path

import chainlit as cl

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from market_scout_agent.agent import run_pipeline

# ── Base URL for file links ───────────────────────────────────────────────────
# Set FILES_BASE_URL=https://<your-app>.onrender.com in Render environment vars.
# Falls back to localhost for local dev.
FILES_BASE_URL = os.environ.get("FILES_BASE_URL", "http://localhost:8000").rstrip("/")


# ── Company extractor ─────────────────────────────────────────────────────────

_FILLER = re.compile(
    r"^\s*("
    r"track|monitor|analyse|analyze|research|check|look\s+up|get\s+updates?\s+for|"
    r"what\s*['\u2019]?s\s+new\s+(at|for|with)|latest\s+features?\s*(of|for|from)?|"
    r"compare|tell\s+me\s+about|show\s+me|find\s+updates?\s*(on|for)?|"
    r"recent\s+updates?\s*(on|for)?|recent\s+features?\s*(of|for)?"
    r")\s+",
    re.IGNORECASE,
)
_TRAILING = re.compile(
    r"\s*(latest\s+features?|recent\s+updates?|updates?|features?|news|info|information)\s*$",
    re.IGNORECASE,
)

def _extract_companies(query: str) -> str:
    cleaned = query.strip().rstrip("?.,!")
    cleaned = _FILLER.sub("", cleaned).strip()
    cleaned = _TRAILING.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+and\s+", ", ", cleaned, flags=re.IGNORECASE)
    return cleaned if cleaned else query


# ── File path → public URL ────────────────────────────────────────────────────

def _to_url(abs_path) -> str:
    if not abs_path or str(abs_path) == "Not generated":
        return ""
    rel = os.path.relpath(str(abs_path), str(_HERE)).replace("\\", "/")
    return f"{FILES_BASE_URL}/files/{rel}"


# ── Guardrails ────────────────────────────────────────────────────────────────

OUT_OF_SCOPE = {"recipe", "weather", "homework", "poem", "joke", "song", "sport", "movie", "game", "politics"}
HARMFUL      = {"hack", "exploit", "malware", "illegal", "jailbreak", "ignore instructions", "act as"}


# ── Greeting ──────────────────────────────────────────────────────────────────

GREETING = """\
👋 **Welcome to Market Scout — Competitive Intelligence Assistant!**

I help you track and analyse competitor product updates in real time.

**Here's what you can ask me:**

| Example Query | What happens |
|---|---|
| `Stripe` | Full intelligence run for Stripe |
| `Tesla` | Latest feature updates for Tesla |
| `Stripe, PayPal` | Side-by-side analysis of both |
| `Nike` | Recent product moves by Nike |
| `OpenAI, Anthropic` | Multi-company batch run |

After each run you'll get clickable links for:
📊 Dashboard · 📄 PDF · 📝 Briefing · 📈 Excel

**Just type a company name to get started!**
"""


# ── Report builder ────────────────────────────────────────────────────────────

def _build_report(result: dict, base_url: str) -> str:
    company  = result.get("company", "")
    run_date = result.get("run_date", "")
    version  = result.get("version", "")
    summary  = result.get("summary", {})
    top_feat = result.get("top_features", [])
    files    = result.get("files", {})

    summary_rows = (
        f"| Total Features | {summary.get('total', 0)} |\n"
        f"| Last 7 Days (WEEK) | {summary.get('week', 0)} |\n"
        f"| Last 30 Days (MONTH) | {summary.get('month', 0)} |\n"
        f"| Last 365 Days (YEAR) | {summary.get('year', 0)} |\n"
        f"| Other sources | {summary.get('unver', 0)} |"
    )

    if top_feat:
        feat_lines = []
        for i, f in enumerate(top_feat, 1):
            src    = f.get("url", "")
            src_md = f"[View Source]({src})" if src else "N/A"
            feat_lines.append(
                f"{i}. **{f.get('feature', '')}**\n"
                f"   - Category: {f.get('category', '')}\n"
                f"   - Date: {f.get('date', 'unknown')}\n"
                f"   - Status: `{f.get('status', '')}`\n"
                f"   - Source: {src_md}"
            )
        features_section = "\n\n".join(feat_lines)
    else:
        features_section = "_No features found for this company._"

    # Convert stored file paths to public URLs
    raw_files = result.get("files", {})
    def _url(key):
        val = raw_files.get(key, "")
        # Already a full URL (from agent.py _file_url) — use as-is
        # If it looks like an absolute path, convert it
        if val and not val.startswith("http"):
            val = _to_url(val)
        return val

    dashboard_url = _url("dashboard")
    excel_url     = _url("excel")
    pdf_url       = _url("pdf")
    briefing_url  = _url("briefing")

    def row(label, url):
        if url:
            return f"| {label} | [Click to open]({url}) |"
        return f"| {label} | _Not generated_ |"

    files_table = "\n".join([
        row("📊 Dashboard (HTML)", dashboard_url),
        row("📈 Excel with Charts", excel_url),
        row("📄 PDF Report",        pdf_url),
        row("📝 Text Briefing",     briefing_url),
    ])

    return f"""\
## 🔍 Market Scout Report
**Company:** {company}
**Run Date:** {run_date} | **Version:** {version}

---

### 📋 Findings Summary

| Metric | Count |
|--------|-------|
{summary_rows}

---

### 🏆 Top Features Found

{features_section}

---

### 🛡️ Guardrails Active

| Guardrail | Blocks |
|-----------|--------|
| Harmful Intent Detection | hack, exploit, malware, illegal |
| Prompt Injection Guard | jailbreak, act as, ignore instructions |
| PII Detection | credit cards, SSN, emails, phones |
| Out-of-Scope Filter | recipes, weather, homework, poems |
| Query Length Guards | under 3 or over 1000 characters |
| Output Safety Filter | sensitive data in responses |

---

### 📥 Download Your Reports

| Report | Link |
|--------|------|
{files_table}

> 💡 Links open the file directly in your browser. If a file downloads instead of opening, right-click → Open in new tab.

---
_Powered by Google ADK · Groq LLaMA 3.3 · Tavily Search_
"""


# ── Chainlit hooks ────────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content=GREETING, author="Market Scout").send()


@cl.on_message
async def on_message(message: cl.Message):
    query = message.content.strip()

    if len(query) < 2:
        await cl.Message(content="⚠️ Please enter a company name.", author="Market Scout").send()
        return
    if len(query) > 1000:
        await cl.Message(content="⚠️ Query too long (max 1000 chars).", author="Market Scout").send()
        return

    lower = query.lower()

    if any(w in lower for w in HARMFUL):
        await cl.Message(content="🚫 I can only help with competitor intelligence.", author="Market Scout").send()
        return
    if any(w in lower for w in OUT_OF_SCOPE):
        await cl.Message(content="🚫 I only track competitor updates. Try: `Stripe`", author="Market Scout").send()
        return

    companies_input = _extract_companies(query)

    async with cl.Step(name="🔍 Running Market Scout pipeline...") as step:
        step.output = f"Fetching intelligence for: **{companies_input}**"
        try:
            result = run_pipeline(companies_input)
        except Exception as e:
            await cl.Message(content=f"❌ Pipeline error: {str(e)}", author="Market Scout").send()
            return

    await cl.Message(
        content=_build_report(result, FILES_BASE_URL),
        author="Market Scout",
    ).send()