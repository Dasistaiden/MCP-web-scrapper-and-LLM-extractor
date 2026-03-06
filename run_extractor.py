"""
Run Extractor
=============
Reads scraped site JSON files from output/sites/ and extracts structured
school profiles using Ollama (local or cloud).

Edit the CONFIGURATION block, then run:

    uv run python run_extractor.py

─────────────────────────────────────────────────────────────────
OPTION A — Ollama Cloud  (recommended, fast, large model)
─────────────────────────────────────────────────────────────────
1. Sign up / log in at https://ollama.com
2. Get your API key from account settings
3. Set in CONFIGURATION below:
     BASE_URL     = "https://api.ollama.com"
     MODEL        = "deepseek-v3.1:671b-cloud"
     OLLAMA_API_KEY = "your-key-here"   (or set env var OLLAMA_API_KEY)

─────────────────────────────────────────────────────────────────
OPTION B — Local Ollama  (free, no key, slower on CPU)
─────────────────────────────────────────────────────────────────
1. Download and install Ollama: https://ollama.com
2. Pull a model:
     ollama pull qwen2.5:7b    ← recommended (~4.7 GB)
     ollama pull phi3.5        ← fastest/smallest (~2.2 GB)
3. Leave BASE_URL = "http://localhost:11434", OLLAMA_API_KEY = ""
─────────────────────────────────────────────────────────────────
"""

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit this section only
# ─────────────────────────────────────────────────────────────────────────────

# ── Cloud (Ollama Cloud) ──────────────────────────────────────────────────────
BASE_URL       = "https://api.ollama.com"
MODEL          = "qwen3-coder:480b-cloud"
OLLAMA_API_KEY = ""   # leave empty — key is loaded from .env automatically

# ── Local fallback (uncomment to use local Ollama instead) ───────────────────
# BASE_URL       = "http://localhost:11434"
# MODEL          = "qwen2.5:7b"
# OLLAMA_API_KEY = ""  # no key needed for local

# Input: folder with scraped site JSONs (output of run_scraper.py)
SITES_DIR = "output/sites"

# Output: where structured profiles are saved
STRUCTURED_DIR = "output/structured"

# Process a specific file only (leave empty = process all files in SITES_DIR)
SINGLE_FILE = ""

# Skip files that already have a structured output (avoids re-running)
SKIP_EXISTING = True

# ─────────────────────────────────────────────────────────────────────────────
# RUNNER — no need to edit below this line
# ─────────────────────────────────────────────────────────────────────────────

import logging
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()  # Loads .env file automatically

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def check_ollama():
    try:
        requests.get(f"{BASE_URL}/api/tags", timeout=3)
    except Exception:
        print(f"\nERROR: Cannot reach Ollama at {BASE_URL}")
        print("  Make sure Ollama is installed and running.")
        print("  Download: https://ollama.com\n")
        sys.exit(1)


def collect_files() -> list:
    if SINGLE_FILE:
        p = Path(SINGLE_FILE)
        if not p.exists():
            print(f"ERROR: File not found: {SINGLE_FILE}")
            sys.exit(1)
        return [p]

    sites_dir = Path(SITES_DIR)
    if not sites_dir.exists():
        print(f"ERROR: Sites directory not found: {SITES_DIR}")
        print("  Run run_scraper.py first to generate site files.")
        sys.exit(1)

    files = sorted(sites_dir.glob("*.json"))
    if not files:
        print(f"No JSON files found in {SITES_DIR}")
        sys.exit(0)
    return files


def already_extracted(site_file: Path) -> bool:
    if not SKIP_EXISTING:
        return False
    stem   = site_file.stem
    parts  = stem.rsplit("_", 1)
    domain = parts[0] if len(parts) == 2 and parts[1].isdigit() else stem
    return (Path(STRUCTURED_DIR) / f"{domain}.json").exists()


def main():
    import os
    from extractor import create_extractor

    api_key = OLLAMA_API_KEY or os.environ.get("OLLAMA_API_KEY", "")
    is_cloud = BASE_URL.startswith("https://")

    # Only check local Ollama if not using cloud
    if not is_cloud:
        check_ollama()
    elif not api_key:
        print("\nERROR: Ollama Cloud requires an API key.")
        print("  Set OLLAMA_API_KEY in CONFIGURATION or as an environment variable.\n")
        sys.exit(1)

    extractor = create_extractor(model=MODEL, base_url=BASE_URL, api_key=api_key)
    files     = collect_files()

    print(f"\n{'='*60}")
    print(f"  Mode   : {'Cloud' if is_cloud else 'Local'}")
    print(f"  Model  : {MODEL}")
    print(f"  Files  : {len(files)}")
    print(f"  Output : {STRUCTURED_DIR}/")
    print(f"{'='*60}")

    succeeded, skipped, failed = 0, 0, 0

    for i, site_file in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}]  {site_file.name}")

        if already_extracted(site_file):
            print(f"  Skipped (already extracted — set SKIP_EXISTING=False to re-run)")
            skipped += 1
            continue

        try:
            extractor.extract(str(site_file), output_dir=STRUCTURED_DIR)
            succeeded += 1
        except Exception as e:
            logger.error(f"  FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Done -- {succeeded} succeeded  |  {skipped} skipped  |  {failed} failed")
    print(f"  Results in: {STRUCTURED_DIR}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
