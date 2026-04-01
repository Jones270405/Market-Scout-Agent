# market_scout_agent/agent.py
"""
Market Scout — Root Agent
ADK requires this file to expose a variable named exactly `root_agent`.
"""

import os
import sys
import json
from datetime import datetime

# ── Ensure project root is on sys.path so sub-packages resolve ──
_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from guardrails.callbacks import input_guardrail, output_guardrail
from web_retrieval_agent.agent import get_search_results
from content_extraction_agent.agent import extract_features
from temporal_validation_agent.agent import validate_by_timeframe
from feature_synthesis_agent.agent import generate_pdf, generate_briefing
from comparison_report_agent.agent import update_excel

# ─── Persistent file paths ────────────────────────────────────────────────────
DASHBOARD_FILE = os.path.join(_PROJECT_ROOT, "market_scout_dashboard.html")
HISTORY_FILE   = os.path.join(_PROJECT_ROOT, "market_scout_history.json")


# ─── History helpers ──────────────────────────────────────────────────────────

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []


def save_history(history: list) -> None:
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ─── Dashboard builder ────────────────────────────────────────────────────────

def update_dashboard(all_runs: list) -> None:
    """Regenerates the persistent HTML dashboard from full run history."""
    version       = datetime.now().strftime("v%Y.%m.%d")
    timeline_html = ""

    status_colors = {
        "WEEK"      : "#C6EFCE",
        "MONTH"     : "#FFEB9C",
        "YEAR"      : "#DDEBF7",
        "UNVERIFIED": "#F2F2F2",
        "STALE"     : "#FFC7CE",
    }

    for run in reversed(all_runs):
        features  = run.get("features", [])
        company   = run.get("company", "")
        run_date  = run.get("run_date", "")
        week_cnt  = sum(1 for f in features if f.get("status") == "WEEK")
        month_cnt = sum(1 for f in features if f.get("status") in ["WEEK", "MONTH"])
        year_cnt  = sum(1 for f in features if f.get("status") in ["WEEK", "MONTH", "YEAR"])
        unver_cnt = sum(1 for f in features if f.get("status") == "UNVERIFIED")

        feature_rows = ""
        for f in features:
            bg  = status_colors.get(f.get("status", ""), "#FFFFFF")
            url = f.get("url", "")
            link = '<a href="' + url + '" target="_blank">View Source</a>' if url else "N/A"
            feature_rows += (
                "<tr style='background:" + bg + "'>"
                "<td>" + f.get("feature", "") + "</td>"
                "<td><span class='badge'>" + f.get("category", "") + "</span></td>"
                "<td>" + f.get("date", "unknown") + "</td>"
                "<td><strong>" + f.get("status", "") + "</strong></td>"
                "<td>" + link + "</td>"
                "</tr>"
            )

        no_data = "<tr><td colspan='5' style='text-align:center;color:#888'>No features found</td></tr>"
        timeline_html += (
            "<div class='run-card'>"
            "<div class='run-header'>"
            "<div>"
            "<span class='company-tag'>" + company + "</span>"
            "<span class='run-date'>📅 " + run_date + "</span>"
            "</div>"
            "<div class='run-stats'>"
            "<span class='stat green'>7d: " + str(week_cnt) + "</span>"
            "<span class='stat orange'>30d: " + str(month_cnt) + "</span>"
            "<span class='stat blue'>365d: " + str(year_cnt) + "</span>"
            "<span class='stat grey'>❓: " + str(unver_cnt) + "</span>"
            "</div></div>"
            "<table>"
            "<tr><th>Feature</th><th>Category</th><th>Date</th><th>Status</th><th>Source</th></tr>"
            + (feature_rows if feature_rows else no_data) +
            "</table></div>"
        )

    total_runs     = len(all_runs)
    total_features = sum(len(r.get("features", [])) for r in all_runs)
    companies      = list(set(r.get("company", "") for r in all_runs))
    now_str        = datetime.now().strftime("%B %d, %Y at %H:%M")

    # Build HTML using concatenation to avoid any f-string curly braces
    css = (
        "<style>"
        "*{margin:0;padding:0;box-sizing:border-box}"
        "body{font-family:'Segoe UI',sans-serif;background:#f0f4f8;color:#333}"
        ".header{background:linear-gradient(135deg,#1F4E79,#2E86AB);color:white;padding:30px 40px}"
        ".header h1{font-size:28px;margin-bottom:5px}"
        ".header p{opacity:.8;font-size:14px}"
        ".container{max-width:1400px;margin:30px auto;padding:0 20px}"
        ".overview{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:30px}"
        ".overview-card{background:white;border-radius:12px;padding:20px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.08)}"
        ".overview-card .number{font-size:36px;font-weight:bold;color:#1F4E79}"
        ".overview-card .label{font-size:13px;color:#888;margin-top:5px}"
        ".legend{background:white;border-radius:12px;padding:15px 25px;margin-bottom:25px;box-shadow:0 2px 8px rgba(0,0,0,.08);display:flex;gap:20px;align-items:center;flex-wrap:wrap}"
        ".legend-item{display:flex;align-items:center;gap:8px;font-size:13px}"
        ".legend-dot{width:14px;height:14px;border-radius:3px}"
        ".run-card{background:white;border-radius:12px;padding:25px;margin-bottom:25px;box-shadow:0 2px 8px rgba(0,0,0,.08)}"
        ".run-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;padding-bottom:15px;border-bottom:2px solid #f0f0f0}"
        ".company-tag{background:#1F4E79;color:white;padding:5px 15px;border-radius:20px;font-weight:bold;font-size:16px;margin-right:10px}"
        ".run-date{color:#888;font-size:14px}"
        ".run-stats{display:flex;gap:10px}"
        ".stat{padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold}"
        ".stat.green{background:#C6EFCE;color:#2E7D32}"
        ".stat.orange{background:#FFEB9C;color:#E65100}"
        ".stat.blue{background:#DDEBF7;color:#1565C0}"
        ".stat.grey{background:#F2F2F2;color:#666}"
        "table{width:100%;border-collapse:collapse;font-size:14px}"
        "th{background:#1F4E79;color:white;padding:10px 12px;text-align:left}"
        "td{padding:10px 12px;border-bottom:1px solid #f0f0f0}"
        "td a{color:#2E86AB;text-decoration:none}"
        "td a:hover{text-decoration:underline}"
        ".badge{background:#e8f0fe;color:#1F4E79;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:bold}"
        ".version{text-align:right;font-size:12px;color:#aaa;margin-top:20px;margin-bottom:20px}"
        ".section-title{font-size:20px;font-weight:bold;color:#1F4E79;margin-bottom:20px;border-left:4px solid #2E86AB;padding-left:15px}"
        "</style>"
    )

    no_runs_msg = "<div style='text-align:center;padding:40px;color:#888'>No runs yet</div>"

    html = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
        "<title>Market Scout Dashboard</title>"
        + css +
        "</head><body>"
        "<div class='header'>"
        "<h1>🔍 Market Scout — Intelligence Dashboard</h1>"
        "<p>Live Competitive Intelligence | Last updated: " + now_str + " | " + version + "</p>"
        "</div>"
        "<div class='container'>"
        "<div class='overview' style='margin-top:25px'>"
        "<div class='overview-card'><div class='number'>" + str(total_runs) + "</div><div class='label'>Total Runs</div></div>"
        "<div class='overview-card'><div class='number'>" + str(total_features) + "</div><div class='label'>Total Features Tracked</div></div>"
        "<div class='overview-card'><div class='number'>" + str(len(companies)) + "</div><div class='label'>Companies Tracked</div></div>"
        "</div>"
        "<div class='legend'>"
        "<strong>Status Legend:</strong>"
        "<div class='legend-item'><div class='legend-dot' style='background:#C6EFCE'></div>WEEK — Last 7 days</div>"
        "<div class='legend-item'><div class='legend-dot' style='background:#FFEB9C'></div>MONTH — Last 30 days</div>"
        "<div class='legend-item'><div class='legend-dot' style='background:#DDEBF7'></div>YEAR — Last 365 days</div>"
        "<div class='legend-item'><div class='legend-dot' style='background:#F2F2F2'></div>UNVERIFIED — Date unknown</div>"
        "<div class='legend-item'><div class='legend-dot' style='background:#FFC7CE'></div>STALE — Older than 1 year</div>"
        "</div>"
        "<div class='section-title'>📋 Run History (Latest First)</div>"
        + (timeline_html if timeline_html else no_runs_msg) +
        "<div class='version'>Market Scout " + version + " | Google ADK + Groq LLaMA 3.3 | market_scout_data.xlsx</div>"
        "</div></body></html>"
    )

    with open(DASHBOARD_FILE, "w", encoding="utf-8") as fh:
        fh.write(html)


# ─── Main pipeline ────────────────────────────────────────────────────────────

def run_pipeline(companies_input: str) -> dict:
    """
    Full market intelligence pipeline.
    Input : company name or comma-separated list.
    Output: structured dict the agent formats as the final markdown reply.
    """
    companies = [c.strip() for c in companies_input.split(",") if c.strip()]
    history   = load_history()
    run_date  = datetime.now().strftime("%Y-%m-%d %H:%M")
    version   = datetime.now().strftime("v%Y.%m.%d")
    pdf_files = []

    for company in companies:
        print("\n" + "=" * 50)
        print("Processing: " + company)
        print("=" * 50)

        # 1 — Search
        print("  Searching web...")
        raw = get_search_results(company)

        # 2 — Extract + deduplicate
        print("  Extracting features...")
        features = extract_features(raw)
        print("  " + str(len(features)) + " unique features found")

        # 3 — Validate dates + categorise
        print("  Validating timeframes...")
        features = validate_by_timeframe(features)
        week  = sum(1 for f in features if f.get("status") == "WEEK")
        month = sum(1 for f in features if f.get("status") in ["WEEK", "MONTH"])
        year  = sum(1 for f in features if f.get("status") in ["WEEK", "MONTH", "YEAR"])
        unver = sum(1 for f in features if f.get("status") == "UNVERIFIED")
        print("  Week:" + str(week) + " Month:" + str(month) + " Year:" + str(year) + " Unverified:" + str(unver))

        # 4 — PDF
        print("  Generating PDF...")
        pdf_path = generate_pdf(company, features, run_date)
        pdf_files.append(pdf_path)
        print("  PDF: " + str(pdf_path))

        # 5 — Briefing
        print("  Generating briefing...")
        briefing_path = generate_briefing(company, features, run_date)
        pdf_files.append(briefing_path)
        print("  Briefing: " + str(briefing_path))

        history.append({
            "company" : company,
            "run_date": run_date,
            "features": features,
            "summary" : {
                "total": len(features),
                "week" : week,
                "month": month,
                "year" : year,
                "unver": unver,
            },
        })

    # 6 — Persist history
    save_history(history)

    # 7 — Rebuild HTML dashboard
    print("  Updating dashboard...")
    update_dashboard(history)

    # 8 — Rebuild Excel
    print("  Updating Excel...")
    excel_path = update_excel(history)

    # ── Build return dict ──
    last_company  = companies[-1]
    last_run      = history[-1]
    last_features = last_run["features"]
    last_summary  = last_run["summary"]

    top_features = [
        {
            "feature" : f.get("feature", ""),
            "category": f.get("category", ""),
            "date"    : f.get("date", "unknown"),
            "status"  : f.get("status", ""),
            "url"     : f.get("url", ""),
        }
        for f in last_features
        if f.get("status") in ["WEEK", "MONTH", "YEAR", "UNVERIFIED"]
    ][:5]

    pdf_file   = next((p for p in pdf_files if str(p).endswith(".pdf")), None)
    brief_file = next((p for p in pdf_files if str(p).endswith("_briefing.txt")), None)

    return {
        "company"     : last_company,
        "run_date"    : run_date,
        "version"     : version,
        "summary"     : last_summary,
        "top_features": top_features,
        "files"       : {
            "dashboard": DASHBOARD_FILE,
            "excel"    : excel_path,
            "pdf"      : pdf_file   if pdf_file   else "Not generated",
            "briefing" : brief_file if brief_file else "Not generated",
        },
    }


# ─── Tool + Root Agent ────────────────────────────────────────────────────────

pipeline_tool = FunctionTool(func=run_pipeline)

# IMPORTANT: The instruction string must contain ZERO curly braces.
# ADK's instructions_utils.py regex r'{+[^{}]*}+' matches ANY braces
# including doubled ones, and raises KeyError if the name isn't in session state.

_INSTRUCTION = (
    "You are Market Scout, a Competitive Intelligence Assistant.\n\n"
    "You have ONE tool called run_pipeline.\n\n"
    "Call run_pipeline whenever the user mentions a company name or asks to track,\n"
    "monitor, or get updates for a company. Pass the company name as the argument.\n"
    "For multiple companies, pass them comma-separated.\n\n"
    "Examples:\n"
    "- User says 'Track Stripe' -> call run_pipeline with 'Stripe'\n"
    "- User says 'Tesla' -> call run_pipeline with 'Tesla'\n"
    "- User says 'Compare Stripe and PayPal' -> call run_pipeline with 'Stripe, PayPal'\n"
    "- User says 'Nike latest features' -> call run_pipeline with 'Nike'\n\n"
    "After run_pipeline returns a result dictionary, YOU MUST immediately compose\n"
    "and output a full markdown report using the values from that dictionary.\n"
    "Never output a blank response or just the raw dictionary after the tool call.\n\n"
    "Structure your markdown response exactly as follows, substituting actual values:\n\n"
    "## Market Scout Report\n"
    "Company: [company value from dict]\n"
    "Run Date: [run_date value] | Version: [version value]\n\n"
    "### Findings Summary\n"
    "Present a markdown table with these rows:\n"
    "- Total Features: [summary.total]\n"
    "- Last 7 Days (WEEK): [summary.week]\n"
    "- Last 30 Days (MONTH): [summary.month]\n"
    "- Last 365 Days (YEAR): [summary.year]\n"
    "- Unverified: [summary.unver]\n\n"
    "### Top Features Found\n"
    "For each item in top_features list, output:\n"
    "Number. Feature name\n"
    "- Category: category value\n"
    "- Date: date value\n"
    "- Status: status value\n"
    "- Source: url value\n"
    "If top_features is empty, write: No features found for this company.\n\n"
    "### Guardrails Active\n"
    "Always include this table:\n"
    "| Guardrail | Blocks |\n"
    "|-----------|--------|\n"
    "| Harmful Intent Detection | hack, exploit, malware, illegal |\n"
    "| Prompt Injection Guard | jailbreak, act as, ignore instructions |\n"
    "| PII Detection | credit cards, SSN, emails, phones |\n"
    "| Out-of-Scope Filter | recipes, weather, homework, poems |\n"
    "| Query Length Guards | under 3 or over 1000 characters |\n"
    "| Output Safety Filter | sensitive data in responses |\n\n"
    "### Download Your Reports\n"
    "Present a table with these file paths from the files dict:\n"
    "- Dashboard (HTML): files.dashboard value\n"
    "- Excel with Charts: files.excel value\n"
    "- PDF Report: files.pdf value\n"
    "- Text Briefing: files.briefing value\n\n"
    "Add a note: Copy any path above and paste it into your browser or File Explorer.\n"
    "The Dashboard shows ALL previous runs in one place.\n\n"
    "Powered by Google ADK, Groq LLaMA 3.3, and Tavily Search.\n\n"
    "RULES:\n"
    "- Always call run_pipeline first when given a company name.\n"
    "- Always render the full markdown report after the tool returns.\n"
    "- Never output a blank or raw-dict response after the tool call.\n"
    "- Harmful requests: respond with 'I can only help with competitor intelligence.'\n"
    "- Off-topic requests: respond with 'I only track competitor updates.'\n"
)

root_agent = LlmAgent(
    name="market_scout_agent",
    model=LiteLlm(model="groq/llama-3.1-8b-instant"),
    description=(
        "Market Scout — Competitive Intelligence System. "
        "Tracks competitor features with persistent dashboard, Excel, and PDF reports."
    ),
    instruction=_INSTRUCTION,
    tools=[pipeline_tool],
    before_model_callback=input_guardrail,
    after_model_callback=output_guardrail,
)