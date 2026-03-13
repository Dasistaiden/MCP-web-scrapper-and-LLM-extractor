# WHED Tools — Higher Education Intelligence Pipeline

An MCP-native pipeline for collecting structured intelligence on higher education institutions, aligned with the IAU World Higher Education Database (WHED) schema.

**Scrape → Extract → Validate → Save** — the Host LLM performs extraction directly using MCP tools. No external LLM required.

Built on [samirsaci/mcp-webscraper](https://github.com/samirsaci/mcp-webscraper).

---

## Overview

| Step | How |
|------|-----|
| **Scrape** | MCP `crawl_website` or standalone `run_scraper.py` — schema-driven crawl, PDF extraction |
| **Extract** | Host LLM reads scraped content, uses `get_extraction_schema` + `get_db_context` |
| **Validate** | `validate_profile` — Pydantic schema + WHED DB picklist checks |
| **Save** | `save_profile` — write to `output/structured/` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  HOST LLM  (Claude in Cursor / any MCP client)                  │
│                                                                 │
│  crawl_website(url)      →  get_extraction_schema()             │
│  scrape_url(url)             get_db_context(domain)            │
│                                     │                           │
│  Host LLM reads content and fills JSON                          │
│                                     │                           │
│  validate_profile(json)  →  save_profile(domain, json)           │
└─────────────────────────────────────────────────────────────────┘
         │                      │                       │
         ▼                      ▼                       ▼
   output/pages/           schema.py              output/structured/
   output/sites/           db_reference.py
```

---

## Project Structure

```
mcp-webscraper/
├── MCP_server/
│   ├── server.py           # MCP entry — 9 tools (scrape + extraction)
│   ├── models/
│   └── utils/
│       └── web_scraper.py  # Scraper (static, Playwright, pdfplumber)
├── schema.py               # SchoolProfile, EXTRACTION_TEMPLATE, FIELD_URL_HINTS
├── db_reference.py         # WHED DB — picklists, reference examples, ground truth
├── run_scraper.py          # Standalone CLI — schema-driven crawl, PDF extraction
├── run_comparison.py       # 3-way comparison: Baseline vs MCP vs Ground Truth
├── docs/
│   ├── USAGE_GUIDE.md      # Architecture, flow, outputs, comparison
│   ├── PROJECT_ITERATIONS.md
│   └── MCP_VS_N8N_COMPARISON.md
└── output/
    ├── pages/              # Per-page cache from crawl
    ├── sites/              # Combined site crawl
    ├── structured/         # MCP extraction output
    ├── structured_baseline/# Legacy extractions (for comparison)
    ├── ground_truth/       # WHED DB exports
    └── comparisons/
```

---

## Prerequisites

- Python 3.10+
- [uv](https://astral.sh/uv) package manager
- [Cursor](https://cursor.sh) (for MCP usage)
- MySQL with WHED database (optional — for DB grounding and comparison)

---

## Installation

```bash
git clone https://github.com/your-username/mcp-webscraper.git
cd mcp-webscraper
uv sync
uv run playwright install chromium
```

Copy `.env.example` to `.env` and add WHED DB credentials (if available).

### Connect MCP to Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "whed-tools": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/mcp-webscraper",
        "python",
        "MCP_server/server.py"
      ]
    }
  }
}
```

---

## MCP Tools (whed-tools)

| Tool | Description |
|------|-------------|
| `scrape_url` | Fetch HTML from a URL |
| `extract_data` | Extract by CSS selector |
| `extract_first` | First matching element |
| `batch_scrape` | Multiple URLs |
| `crawl_website` | Discover and crawl site |
| `get_extraction_schema` | WHED field template (REQUIRED only) |
| `get_db_context` | Picklists + reference example for domain |
| `validate_profile` | Pydantic + DB picklist validation |
| `save_profile` | Save profile to `output/structured/` |

### Example prompt

> "Crawl https://www.example.edu and extract a WHED profile. Use get_extraction_schema and get_db_context, then validate and save."

---

## Standalone Scripts

### Scrape (schema-driven, with PDFs)

Edit `run_scraper.py` (TARGET_URL, MODE, etc.), then:

```bash
uv run python run_scraper.py
```

- Uses `schema.FIELD_URL_HINTS` to follow only relevant URLs
- Extracts text from PDFs via `pdfplumber`

### Comparison

```bash
uv run python run_comparison.py                  # All domains
uv run python run_comparison.py www.ampa.edu.au  # Single domain
```

Compares **Baseline** (legacy) vs **MCP** vs **Ground Truth** (WHED DB). See `docs/USAGE_GUIDE.md` for interpretation.

---

## Schema & DB Grounding

- **REQUIRED** fields are in `EXTRACTION_TEMPLATE`; **DEFERRED** fields are in Pydantic but not prompted.
- With WHED DB: picklists, few-shot examples, and post-validation reduce hallucination.
- Edit `schema.py` to add or reactivate fields.

---

## Documentation

| Doc | Content |
|-----|---------|
| [USAGE_GUIDE.md](docs/USAGE_GUIDE.md) | Architecture, flow, outputs, comparison interpretation |
| [PROJECT_ITERATIONS.md](docs/PROJECT_ITERATIONS.md) | Evolution from Ollama to MCP-native |
| [MCP_VS_N8N_COMPARISON.md](docs/MCP_VS_N8N_COMPARISON.md) | KPI comparison with N8N + Firecrawl |

---

## License

MIT — based on [samirsaci/mcp-webscraper](https://github.com/samirsaci/mcp-webscraper).
