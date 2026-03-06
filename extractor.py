"""
extractor.py — LLM-based structured data extraction
=====================================================
Uses a locally running Ollama instance (no API key needed).
Install Ollama: https://ollama.com
Pull a model:   ollama pull qwen2.5:7b

Reads a site JSON from output/sites/, sends content to the LLM,
validates the response against schema.py, and saves to output/structured/.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from pydantic import ValidationError

from schema import EXTRACTION_TEMPLATE, SchoolProfile

logger = logging.getLogger(__name__)

# Max characters of scraped text to send.
# Local models (CPU): keep low to avoid timeouts.
# Cloud models:       can go much higher.
MAX_CONTENT_CHARS_LOCAL = 8_000
MAX_CONTENT_CHARS_CLOUD = 120_000


# ─────────────────────────────────────────────────────────────────────────────
# Shared prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def _score_page(url: str) -> int:
    """
    Higher score = higher priority. Pages with relevant keywords go first.
    Returns -1 to skip entirely (images / unextractable binaries).

    PDFs are NOT auto-skipped here: if run_scraper.py successfully extracted
    text from a PDF, it will have non-empty full_text and should compete for
    the LLM budget just like any other page.
    """
    url_lower = url.lower()

    # Skip image and other binary formats that are never text-extractable
    _IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
                   ".mp3", ".mp4", ".zip", ".exe")
    if any(url_lower.endswith(ext) for ext in _IMAGE_EXTS):
        return -1

    # Highest priority: course/program pages (web or PDF)
    if any(k in url_lower for k in ("course", "program", "degree", "bachelor", "master",
                                     "postgrad", "undergrad", "study", "department",
                                     "faculty", "school-of", "contemporary", "classical",
                                     "music-theatre", "dance", "composition",
                                     "handbook", "prospectus", "catalog", "syllabus")):
        return 3

    # High priority: contact/staff/about/fee pages (web or PDF)
    if any(k in url_lower for k in ("people", "staff", "contact", "about", "team",
                                     "rector", "president", "international",
                                     "fee", "fees", "tuition", "cost")):
        return 2

    # Normal priority
    return 1


def _normalize_url(url: str) -> str:
    """Normalize http/https and trailing slashes for deduplication."""
    return url.replace("http://", "https://").rstrip("/")


def _build_prompt(site_data: dict, max_chars: int = MAX_CONTENT_CHARS_LOCAL) -> str:
    domain = site_data.get("domain", "")
    pages  = site_data.get("pages", [])

    # ── Filter, deduplicate, prioritize ──────────────────────────────────────
    seen_urls = set()
    scored = []
    for page in pages:
        url   = page.get("url", "")
        score = _score_page(url)
        if score < 0:
            continue                           # Skip PDFs / images
        norm = _normalize_url(url)
        if norm in seen_urls:
            continue                           # Skip duplicates (http vs https)
        seen_urls.add(norm)
        text = page.get("full_text", "").strip()
        if not text:
            continue
        scored.append((score, url, text))

    # ── Budget allocation: ensure each tier gets a fair share ─────────────────
    MAX_PER_PAGE = 12_000
    # Homepage always first (score=1 but no keyword — catch it specially)
    # Allocate: 20% for basic/contact (score ≤ 2), 80% for courses (score = 3)
    # But ensure at least one page from each tier if available.
    by_score: dict[int, list] = {1: [], 2: [], 3: []}
    for score, url, text in scored:
        by_score.setdefault(score, []).append((url, text))

    budget_contact  = max_chars // 5          # ~20% for contact / about / people
    budget_courses  = max_chars - budget_contact  # ~80% for course pages

    def _pick(pages_list, budget):
        out, used = [], 0
        for url, text in pages_list:
            if used >= budget:
                break
            chunk = text[:MAX_PER_PAGE]
            section = f"--- PAGE: {url} ---\n{chunk}"
            remaining = budget - used
            if len(section) > remaining:
                section = section[:remaining]
            out.append(section)
            used += len(section)
        return out, used

    contact_sections, contact_used = _pick(by_score[2] + by_score[1], budget_contact)
    course_sections,  _            = _pick(by_score[3], budget_courses)
    sections = contact_sections + course_sections

    combined_text = "\n\n".join(sections)
    template_json = json.dumps(EXTRACTION_TEMPLATE, indent=2, ensure_ascii=False)

    return f"""You are a data extraction assistant. Extract structured information about a higher education institution from its website content.

WEBSITE DOMAIN: {domain}

INSTRUCTIONS:
- Extract only information that is explicitly stated.
- Use null for any field that is missing or unclear.
- Include all key contacts mentioned by name (President, Rector, Dean, International Office head, senior staff).
- List every academic department and the subjects they teach.
- List every degree program with its level (Bachelor/Master/Doctorate/Certificate/Diploma).
- Return ONLY a valid JSON object matching the template. No explanation, no markdown.

OUTPUT TEMPLATE:
{template_json}

WEBSITE CONTENT:
{combined_text}"""


# ─────────────────────────────────────────────────────────────────────────────
# JSON parser (shared)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json(raw_text: str, domain: str) -> dict:
    text = raw_text

    # Strip markdown code fences if present
    if "```" in text:
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text  = "\n".join(lines)

    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in LLM response for {domain}")

    return json.loads(text[start:end])


# ─────────────────────────────────────────────────────────────────────────────
# Save helper
# ─────────────────────────────────────────────────────────────────────────────

def _save(data: dict, domain: str, output_dir: str) -> str:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / f"{domain}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(filename)


# ─────────────────────────────────────────────────────────────────────────────
# Base extractor
# ─────────────────────────────────────────────────────────────────────────────

class _BaseExtractor:
    model: str = ""

    def _call_llm(self, prompt: str) -> str:
        raise NotImplementedError

    def extract(self, site_json_path: str, output_dir: Optional[str] = None) -> dict:
        path = Path(site_json_path)
        logger.info(f"Extracting from {path.name}")

        with open(path, encoding="utf-8") as f:
            site_data = json.load(f)

        domain     = site_data.get("domain", path.stem)
        source_url = site_data.get("start_url", "")

        print(f"\n  Domain  : {domain}")
        print(f"  Pages   : {site_data.get('pages_crawled', 0)}")
        print(f"  Model   : {self.model}")
        print(f"  Sending to LLM...")

        prompt   = self._build_prompt(site_data)
        raw_text = self._call_llm(prompt)
        logger.info(f"Received {len(raw_text)} chars from LLM")

        extracted = _parse_json(raw_text, domain)
        extracted["domain"]           = domain
        extracted["source_url"]       = source_url
        extracted["extracted_at"]     = datetime.now().isoformat(timespec="seconds")
        extracted["extraction_model"] = self.model

        try:
            profile = SchoolProfile(**extracted)
            result  = profile.model_dump()
            print(f"  Validation : OK")
        except ValidationError as e:
            logger.warning(f"Schema validation warnings for {domain}: {e}")
            result = extracted
            result["validation_errors"] = str(e)
            print(f"  Validation : WARNINGS (saved anyway)")

        if output_dir:
            saved_path = _save(result, domain, output_dir)
            print(f"  Saved      : {saved_path}")

        return result

    def _build_prompt(self, site_data: dict) -> str:
        return _build_prompt(site_data)


# ─────────────────────────────────────────────────────────────────────────────
# Ollama extractor  (local or cloud)
# ─────────────────────────────────────────────────────────────────────────────

class OllamaExtractor(_BaseExtractor):
    """
    Works with both local Ollama and Ollama Cloud (api.ollama.com).

    Local (no API key):
      base_url = "http://localhost:11434"
      Models  : qwen2.5:7b, llama3.1:8b, mistral:7b, phi3.5

    Cloud (set OLLAMA_API_KEY env var or pass api_key=):
      base_url = "https://api.ollama.com"
      Models  : deepseek-v3.1:671b-cloud  (large, high quality)
    """

    def __init__(
        self,
        model: str    = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        api_key: str  = "",
    ):
        self.model    = model
        self.base_url = base_url.rstrip("/")
        self.api_key  = api_key
        self.is_cloud = bool(api_key)

    def _build_prompt(self, site_data: dict) -> str:
        max_chars = MAX_CONTENT_CHARS_CLOUD if self.is_cloud else MAX_CONTENT_CHARS_LOCAL
        return _build_prompt(site_data, max_chars)

    def _call_llm(self, prompt: str) -> str:
        url     = f"{self.base_url}/api/chat"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model":    self.model,
            "stream":   True,
            "format":   "json",
            "messages": [{"role": "user", "content": prompt}],
            "options":  {"temperature": 0.1},
        }

        resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
        resp.raise_for_status()

        chunks = []
        total_tokens = 0
        print("  Generating ", end="", flush=True)

        for line in resp.iter_lines():
            if not line:
                continue
            data  = json.loads(line)
            token = data.get("message", {}).get("content", "")
            if token:
                chunks.append(token)
                total_tokens += 1
                if total_tokens % 50 == 0:
                    print(".", end="", flush=True)
            if data.get("done"):
                break

        print(f" ({total_tokens} tokens)")
        return "".join(chunks)


def create_extractor(
    model: str    = "qwen2.5:7b",
    base_url: str = "http://localhost:11434",
    api_key: str  = "",
) -> OllamaExtractor:
    return OllamaExtractor(model=model, base_url=base_url, api_key=api_key)
