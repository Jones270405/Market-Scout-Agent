# Market Scout — Competitive Intelligence Agent

Tracks competitor product features, API updates, and releases using
Google ADK + Groq LLaMA 3.3 + Tavily Search.

## Project Structure

```
market_scout/
├── market_scout_agent/          # Root agent (entry point)
│   ├── __init__.py
│   └── agent.py                 ← root_agent lives here
├── web_retrieval_agent/         # Sub-agent: Tavily web search
│   ├── __init__.py
│   └── agent.py
├── content_extraction_agent/    # Sub-agent: parse & deduplicate results
│   ├── __init__.py
│   └── agent.py
├── temporal_validation_agent/   # Sub-agent: date validation & status
│   ├── __init__.py
│   └── agent.py
├── feature_synthesis_agent/     # Sub-agent: PDF + briefing generation
│   ├── __init__.py
│   └── agent.py
├── comparison_report_agent/     # Sub-agent: Excel + comparison tables
│   ├── __init__.py
│   └── agent.py
├── guardrails/
│   ├── __init__.py
│   └── callbacks.py             ← input/output guardrail hooks
├── .env.example                 ← copy to .env and add your keys
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env and add your TAVILY_API_KEY and GROQ_API_KEY
```

Get your keys:
- Tavily  : https://app.tavily.com
- Groq    : https://console.groq.com

### 3. Run with Google ADK UI
```bash
cd market_scout
adk web market_scout_agent
```
Then open http://localhost:8000 in your browser.

### 4. Run in terminal
```bash
adk run market_scout_agent
```

## Usage Examples

| You type | What happens |
|----------|-------------|
| `Stripe` | Tracks Stripe's latest features |
| `Track Tesla` | Tracks Tesla's latest releases |
| `Compare Stripe and PayPal` | Runs both and shows side-by-side summary |
| `Nike latest features` | Tracks Nike product updates |

## Output Files

After each run, the following files are created/updated in the working directory:

| File | Description |
|------|-------------|
| `market_scout_dashboard.html` | Persistent HTML dashboard (all runs) |
| `market_scout_data.xlsx` | Excel workbook with charts |
| `market_scout_history.json` | Raw JSON history of all runs |
| `{Company}_YYYYMMDD_HHMMSS.pdf` | Per-run PDF report |
| `{Company}_YYYYMMDD_HHMMSS_briefing.txt` | Per-run text briefing |

## Status Legend

| Colour | Status | Meaning |
|--------|--------|---------|
| 🟢 Green | WEEK | Published in last 7 days |
| 🟡 Yellow | MONTH | Published in last 30 days |
| 🔵 Blue | YEAR | Published in last 365 days |
| ⚪ Grey | UNVERIFIED | Date unknown |
| 🔴 Red | STALE | Older than 1 year |

## Guardrails

| Guardrail | What it blocks |
|-----------|---------------|
| Harmful Intent | hack, exploit, malware, illegal |
| Prompt Injection | jailbreak, act as, ignore instructions |
| PII Detection | credit cards, SSN, email, phone numbers |
| Out-of-Scope | recipes, weather, homework, poems |
| Query Length Min | queries shorter than 3 characters |
| Query Length Max | queries longer than 1000 characters |
| Output Safety | PII leaking into responses |
