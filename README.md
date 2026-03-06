# MCP Web Scraper — Higher Education Intelligence Pipeline

A two-stage pipeline for collecting structured intelligence on higher education institutions:

1. **Scrape** — crawl institution websites via MCP tools (Cursor AI) or a standalone script
2. **Extract** — send raw content to an LLM (Ollama) and receive validated, structured JSON profiles

Built on top of [samirsaci/mcp-webscraper](https://github.com/samirsaci/mcp-webscraper).

---

## What it does

Given a university or conservatory website, the pipeline produces a structured `SchoolProfile` containing:

- Basic details (name, address, phone, email, type, year founded)
- Key contacts (President, Rector, Dean, International Office — name, title, email)
- Academic departments and subjects
- Degree programs (level, duration, language, tuition fees, entry requirements)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1 — SCRAPING                                         │
│                                                             │
│  Option A: Cursor AI  ──►  scrapping.py (MCP server)        │
│  Option B: CLI        ──►  run_scraper.py                   │
│                                │                            │
│                                ▼                            │
│                    output/sites/<domain>_<date>.json        │
└─────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2 — EXTRACTION                                       │
│                                                             │
│  run_extractor.py  ──►  extractor.py  ──►  Ollama LLM       │
│                                │                            │
│                                ▼                            │
│                    output/structured/<domain>.json          │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mcp-webscraper/
├── models/
│   └── scraping_models.py      # Pydantic request/response models
├── utils/
│   └── web_scraper.py          # Core WebScraper class (static + JS + PDF)
├── scrapping.py                # MCP server — exposes tools to Cursor AI
├── run_scraper.py              # Standalone scraper CLI (no AI needed)
├── extractor.py                # LLM extraction logic (Ollama)
├── run_extractor.py            # Runner for the extractor (configure here)
├── schema.py                   # SchoolProfile schema + crawl URL hints
├── pyproject.toml              # Dependencies (managed by uv)
├── .env.example                # API key template
└── output/
    ├── sites/                  # Raw crawl results (one JSON per domain)
    ├── pages/                  # Individual page results
    └── structured/             # Final LLM-extracted profiles
```

---

## Prerequisites

- Python 3.10+
- [uv](https://astral.sh/uv) package manager
- [Cursor](https://cursor.sh) (for MCP-based usage)
- [Ollama](https://ollama.com) (local) **or** an Ollama Cloud API key (for extraction)

---

## Installation

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/mcp-webscraper.git
cd mcp-webscraper
uv sync
```

### 2. Install Playwright browser (for JavaScript-rendered sites)

```bash
uv run playwright install chromium
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env and add your OLLAMA_API_KEY (only needed for Ollama Cloud)
```

---

## Stage 1 — Scraping

### Option A: Via Cursor MCP (recommended)

Add the MCP server to your Cursor settings (`Settings > MCP`):

```json
{
  "mcpServers": {
    "WebScrapingServer": {
      "command": "uv",
      "args": [
        "run",
        "--with", "mcp[cli]",
        "mcp",
        "run",
        "C:/path/to/mcp-webscraper/scrapping.py"
      ]
    }
  }
}
```

Then ask Cursor AI naturally:

```
"Crawl https://www.example-university.edu — I need all pages related to
courses, staff, fees, and contact information."
```

Cursor AI will decide which MCP tools to call and in what order.

#### Available MCP Tools

| Tool | Description |
|------|-------------|
| `scrape_url` | Fetch raw HTML from a single URL |
| `extract_data` | Extract elements by CSS selector |
| `extract_first` | Get the first matching element |
| `batch_scrape` | Scrape multiple URLs at once |
| `crawl_website` | Discover and crawl an entire site |

### Option B: Standalone script

Edit the `CONFIGURATION` block at the top of `run_scraper.py`, then run:

```bash
uv run python run_scraper.py
```

Key settings:

```python
START_URL   = "https://www.example-university.edu"
MAX_PAGES   = 100
MAX_DEPTH   = 4
OUTPUT_DIR  = "output/sites"
```

Output: `output/sites/<domain>_<YYYYMMDD>.json`

---

## Stage 2 — LLM Extraction

Edit the `CONFIGURATION` block in `run_extractor.py`:

```python
# Ollama Cloud (recommended — fast, large model)
BASE_URL       = "https://api.ollama.com"
MODEL          = "qwen3-coder:480b-cloud"
OLLAMA_API_KEY = ""   # loaded from .env automatically

# Local Ollama (free, no key, slower)
# BASE_URL = "http://localhost:11434"
# MODEL    = "qwen2.5:7b"
```

Then run:

```bash
uv run python run_extractor.py
```

The extractor will:
1. Read all JSONs from `output/sites/`
2. Prioritize high-value pages (course, staff, fee pages) within the LLM context budget
3. Send a structured prompt to Ollama
4. Validate the response against `SchoolProfile` in `schema.py`
5. Save to `output/structured/<domain>.json`

### Local Ollama setup

```bash
# Install Ollama: https://ollama.com
ollama pull qwen2.5:7b    # ~4.7 GB, recommended
ollama pull phi3.5        # ~2.2 GB, fastest
```

---

## Customising the Schema

All extracted fields are defined in `schema.py`. Editing `SchoolProfile` automatically updates:
- The LLM prompt template (`EXTRACTION_TEMPLATE`)
- Output validation
- URL crawl hints (`FIELD_URL_HINTS`) — controls which pages `run_scraper.py` prioritises

---

## Output Format

`output/structured/<domain>.json` example:

```json
{
  "domain": "www.example-university.edu",
  "source_url": "https://www.example-university.edu",
  "extracted_at": "2026-03-06T14:00:00",
  "extraction_model": "qwen3-coder:480b-cloud",
  "basic_details": {
    "name": "Example University",
    "address": "123 University Ave, City, Country",
    "phone": "+1 234 567 8900",
    "email": "info@example-university.edu",
    "institution_type": "public",
    "year_founded": 1905,
    "website": "https://www.example-university.edu"
  },
  "key_contacts": [
    {
      "name": "Jane Smith",
      "title": "President",
      "email": "president@example-university.edu",
      "verification_status": "unverified"
    }
  ],
  "departments": [...],
  "degree_programs": [...]
}
```

---

## Troubleshooting

**MCP server not appearing in Cursor**

Restart Cursor after editing MCP settings. Check `scraping_server.log` for errors.

**Playwright / JavaScript scraping fails**

```bash
uv run playwright install chromium
```

**Ollama Cloud: API key error**

Ensure `OLLAMA_API_KEY` is set in `.env` or in the `CONFIGURATION` block of `run_extractor.py`.

**Local Ollama not reachable**

```bash
# Check Ollama is running
ollama list
# Start if needed
ollama serve
```

---

## License

MIT License — based on [samirsaci/mcp-webscraper](https://github.com/samirsaci/mcp-webscraper).
