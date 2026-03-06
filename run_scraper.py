"""
Run Scraper
===========
Edit the CONFIGURATION block below, then run:

    uv run python run_scraper.py
"""

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit this section only
# ─────────────────────────────────────────────────────────────────────────────

# Single URL (used when BATCH_URLS is empty)
TARGET_URL = "https://www.ampa.edu.au/"

# Batch URLs — when non-empty, TARGET_URL is ignored
BATCH_URLS = [
    # "https://www.example.com/",
    # "https://www.another-site.com/",
]

# Mode: "scrape" | "extract" | "crawl" | "full" | "crawl_full"
#   full       = extract all visible text + record images/PDFs for a single page
#   crawl_full = crawl every page of the site AND extract full content per page
MODE = "crawl_full"

# CSS selectors and their attributes (only used in extract mode)
# Each pair: (selector, attribute)  — use "text" for visible text, "href" for links
SELECTORS = [
    ("h1",    "text"),
    ("h2",    "text"),
    ("h3",    "text"),
    ("a",     "href"),
]

# Crawl settings (used in "crawl" and "crawl_full" modes)
CRAWL_MAX_PAGES = 200
CRAWL_MAX_DEPTH = 3
CRAWL_SAME_DOMAIN = True   # False = follow external links too
CRAWL_DELAY_SECONDS = 0.5  # Delay between requests (be polite to servers)

# Enable JavaScript rendering (slower, needed for React/Vue/Angular sites)
JAVASCRIPT = False

# Schema-driven crawl: only follow URLs whose path contains a keyword from
# schema.FIELD_URL_HINTS.  Skips PDFs, images, login pages, and unrelated pages.
# Set to False to crawl everything (original behaviour).
SCHEMA_DRIVEN_CRAWL = True

# PDF text extraction settings
# Attempt to extract text from PDF links discovered during crawling.
EXTRACT_PDFS = True
PDF_MAX_SIZE_MB = 5       # Skip PDFs larger than this (likely image-based / scanned)
PDF_MAX_CHARS  = 30_000   # Cap extracted text per PDF before storing

# Output folder — results are saved here as timestamped JSON files
# Use None to skip saving
SAVE_DIR = "output"

# ─────────────────────────────────────────────────────────────────────────────
# RUNNER — no need to edit below this line
# ─────────────────────────────────────────────────────────────────────────────

import io
import json
import logging
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

from bs4 import BeautifulSoup
from pydantic import HttpUrl

from models.scraping_models import ElementSelector, ExtractRequest, ScrapingRequest
from utils.web_scraper import WebScraper
from schema import FIELD_URL_HINTS, url_matches_schema

# File extensions that are never useful to scrape as web pages
_SKIP_EXTENSIONS = frozenset([
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov",
])

# Tags whose content is purely structural/decorative — stripped before text extraction
_NOISE_TAGS = ["script", "style", "nav", "header", "footer", "aside",
               "noscript", "iframe", "svg", "button", "form"]


def extract_full_content(html: str, url: str, status_code: int, load_time: float) -> dict:
    """Parse raw HTML into structured content: text, images, PDFs."""
    soup = BeautifulSoup(html, "html.parser")

    # ── Remove noise ──────────────────────────────────────────────────────
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    # ── Title ─────────────────────────────────────────────────────────────
    title = soup.title.get_text(strip=True) if soup.title else ""

    # ── Text blocks (one entry per meaningful element) ────────────────────
    text_blocks = []
    seen = set()
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6",
                               "p", "li", "td", "th", "blockquote", "pre"]):
        text = " ".join(tag.get_text(separator=" ", strip=True).split())
        if text and len(text) > 15 and text not in seen:
            seen.add(text)
            text_blocks.append(text)

    # ── Images (OCR deferred) ─────────────────────────────────────────────
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src", "")
        if src:
            images.append({
                "src": urljoin(url, src),
                "alt": img.get("alt", "").strip(),
                "ocr_pending": True
            })

    # ── PDF links (OCR deferred) ──────────────────────────────────────────
    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            pdfs.append({
                "href": urljoin(url, href),
                "link_text": a.get_text(strip=True),
                "ocr_pending": True
            })

    return {
        "url": url,
        "title": title,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "status_code": status_code,
        "load_time_seconds": round(load_time, 3),
        "text_blocks": text_blocks,
        "full_text": "\n\n".join(text_blocks),
        "images": images,
        "pdfs": pdfs,
    }


def _write_json(path: Path, data) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(path)


def save_json(data, label: str) -> str:
    """Save to output/ root (used by non-crawl_full modes)."""
    if not SAVE_DIR:
        return ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _write_json(Path(SAVE_DIR) / f"{label}_{timestamp}.json", data)


def save_page_cache(page_data: dict, domain: str) -> str:
    """Save a single page to output/pages/<domain>/ as a cache file."""
    if not SAVE_DIR:
        return ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = slug(page_data["url"]) + f"_{timestamp}.json"
    return _write_json(Path(SAVE_DIR) / "pages" / domain / filename, page_data)


def save_site(site_data: dict) -> str:
    """Save the complete per-school file to output/sites/<domain>_<date>.json."""
    if not SAVE_DIR:
        return ""
    domain = site_data["domain"]
    date = datetime.now().strftime("%Y%m%d")
    return _write_json(Path(SAVE_DIR) / "sites" / f"{domain}_{date}.json", site_data)


def extract_pdf_text(pdf_url: str) -> str | None:
    """
    Download a PDF and extract its text content.
    Returns the extracted text (capped at PDF_MAX_CHARS), or None if:
      - pdfplumber is not installed
      - download fails
      - PDF exceeds PDF_MAX_SIZE_MB
      - PDF is image-based (no extractable text)
    """
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed — skipping PDF extraction")
        return None

    try:
        resp = requests.get(
            pdf_url, timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
            stream=True,
        )
        if resp.status_code != 200:
            return None

        # Check size before downloading fully
        content = b""
        for chunk in resp.iter_content(chunk_size=65536):
            content += chunk
            if len(content) > PDF_MAX_SIZE_MB * 1024 * 1024:
                logger.debug(f"PDF too large (>{PDF_MAX_SIZE_MB} MB), skipping: {pdf_url}")
                return None

        text_pages = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:40]:          # At most 40 pages
                text = page.extract_text()
                if text and text.strip():
                    text_pages.append(text.strip())

        combined = "\n\n".join(text_pages).strip()
        if len(combined) < 100:                  # Probably image-based
            return None
        return combined[:PDF_MAX_CHARS]

    except Exception as exc:
        logger.debug(f"PDF extraction failed ({pdf_url}): {exc}")
        return None


def slug(url: str) -> str:
    """Turn a URL into a safe filename prefix."""
    return url.replace("https://", "").replace("http://", "").replace("/", "_").strip("_")[:50]


def domain_of(url: str) -> str:
    return urlparse(url).netloc


def crawl_and_extract(scraper: WebScraper, start_url: str) -> dict:
    """
    BFS-crawl an entire site and extract full content from every page.
    - Each page is cached immediately to  output/pages/<domain>/
    - After crawling, one combined file is written to output/sites/<domain>_<date>.json
    """
    start_domain = domain_of(start_url)
    to_visit = deque([(start_url, 0)])  # (url, depth)
    visited: set = set()
    pdf_visited: set = set()            # Track attempted PDFs to avoid duplicates
    pages = []
    failed = []

    print(f"\n{'='*60}")
    print(f"  CRAWL FULL  {start_domain}")
    print(f"  Max pages      : {CRAWL_MAX_PAGES}  |  Max depth : {CRAWL_MAX_DEPTH}")
    print(f"  Schema-driven  : {SCHEMA_DRIVEN_CRAWL}")
    print(f"{'='*60}")

    while to_visit and len(pages) < CRAWL_MAX_PAGES:
        url, depth = to_visit.popleft()

        if url in visited or depth > CRAWL_MAX_DEPTH:
            continue

        if visited:
            time.sleep(CRAWL_DELAY_SECONDS)

        visited.add(url)
        print(f"\n  [{len(pages)+1:>3}] depth={depth}  {url}")

        request = ScrapingRequest(
            url=HttpUrl(url),
            javascript_loading=JAVASCRIPT,
            timeout=10
        )
        response = scraper.scrape(request)

        if response.error:
            print(f"         ERROR: {response.error}")
            failed.append({"url": url, "error": response.error})
            continue

        page_data = extract_full_content(
            response.html, url, response.status_code, response.load_time
        )
        pages.append(page_data)

        print(f"         title  : {page_data['title'] or '(no title)'}")
        print(f"         blocks : {len(page_data['text_blocks'])}  |  "
              f"images : {len(page_data['images'])}  |  "
              f"pdfs : {len(page_data['pdfs'])}")

        # Cache individual page immediately (safe against mid-run failures)
        if SAVE_DIR:
            cached = save_page_cache(page_data, start_domain)
            print(f"         cache  --> {cached}")

        # ── PDF text extraction ───────────────────────────────────────────────
        if EXTRACT_PDFS:
            for pdf_ref in page_data.get("pdfs", []):
                pdf_url = pdf_ref.get("href", "")
                if not pdf_url or pdf_url in pdf_visited:
                    continue
                # Only attempt PDFs that match schema keywords
                if not url_matches_schema(pdf_url):
                    continue
                pdf_visited.add(pdf_url)

                time.sleep(CRAWL_DELAY_SECONDS)
                print(f"         pdf    : {pdf_url[:80]}")
                text = extract_pdf_text(pdf_url)
                if text:
                    pdf_page = {
                        "url": pdf_url,
                        "title": pdf_ref.get("link_text", "") or urlparse(pdf_url).path.split("/")[-1],
                        "scraped_at": datetime.now().isoformat(timespec="seconds"),
                        "status_code": 200,
                        "load_time_seconds": 0.0,
                        "source_type": "pdf",
                        "text_blocks": [t for t in text.split("\n\n") if len(t.strip()) > 15],
                        "full_text": text,
                        "images": [],
                        "pdfs": [],
                    }
                    pages.append(pdf_page)
                    print(f"                 extracted {len(text):,} chars from PDF")
                    if SAVE_DIR:
                        cached = save_page_cache(pdf_page, start_domain)
                        print(f"                 cache  --> {cached}")
                else:
                    print(f"                 (no text — image-based or too large)")

        # Discover links for next depth
        if depth < CRAWL_MAX_DEPTH:
            soup = BeautifulSoup(response.html, "html.parser")
            added = skipped_schema = skipped_ext = 0
            for a in soup.find_all("a", href=True):
                abs_url = urljoin(url, a["href"]).split("#")[0]
                parsed = urlparse(abs_url)

                if parsed.scheme not in ("http", "https"):
                    continue
                if CRAWL_SAME_DOMAIN and parsed.netloc != start_domain:
                    continue
                if abs_url in visited:
                    continue

                # Always skip binary file extensions
                path_lower = parsed.path.lower()
                if any(path_lower.endswith(ext) for ext in _SKIP_EXTENSIONS):
                    skipped_ext += 1
                    continue

                # Schema-driven filter: skip pages unlikely to hold schema data
                if SCHEMA_DRIVEN_CRAWL and not url_matches_schema(abs_url):
                    skipped_schema += 1
                    continue

                to_visit.append((abs_url, depth + 1))
                added += 1

            print(f"         links  : +{added} queued"
                  + (f"  |  {skipped_schema} schema-filtered" if skipped_schema else "")
                  + (f"  |  {skipped_ext} file-filtered" if skipped_ext else ""))

    # ── Build the per-school combined object ─────────────────────────────
    site_data = {
        "domain": start_domain,
        "start_url": start_url,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "pages_crawled": len(pages),
        "pages_failed": len(failed),
        "failed_urls": failed,
        "statistics": {
            "total_text_blocks": sum(len(p["text_blocks"]) for p in pages),
            "total_images": sum(len(p["images"]) for p in pages),
            "total_pdfs": sum(len(p["pdfs"]) for p in pages),
            "avg_load_time_seconds": round(
                sum(p["load_time_seconds"] for p in pages) / len(pages), 3
            ) if pages else 0,
        },
        "pages": pages,
    }

    print(f"\n{'='*60}")
    print(f"  Done -- {len(pages)} pages scraped, {len(failed)} failed")
    print(f"  Text blocks : {site_data['statistics']['total_text_blocks']}  |  "
          f"Images : {site_data['statistics']['total_images']}  |  "
          f"PDFs : {site_data['statistics']['total_pdfs']}")
    print(f"{'='*60}")

    return site_data


def run_single(scraper: WebScraper, url: str) -> dict:
    print(f"\n{'-'*60}")
    print(f"  URL  : {url}")
    print(f"  Mode : {MODE.upper()}")
    print(f"{'-'*60}")

    request = ScrapingRequest(url=HttpUrl(url), javascript_loading=JAVASCRIPT)
    response = scraper.scrape(request)

    if response.error:
        print(f"  ERROR: {response.error}")
        return {"success": False, "url": url, "error": response.error}

    if MODE == "scrape":
        result = {
            "success": True,
            "url": url,
            "status_code": response.status_code,
            "load_time": response.load_time,
            "html": response.html,
        }
        print(f"  Status    : {response.status_code}")
        print(f"  Load time : {response.load_time:.2f}s")
        print(f"  HTML size : {len(response.html):,} chars")

    elif MODE == "extract":
        element_selectors = [
            ElementSelector(css_selector=sel, attribute=attr, multiple=True)
            for sel, attr in SELECTORS
        ]
        extract_response = scraper.extract_elements(
            ExtractRequest(html=response.html, selectors=element_selectors)
        )
        data = {}
        for i, (sel, _) in enumerate(SELECTORS):
            items = [v for v in (extract_response.extracted_data.get(f"selector_{i}") or []) if v]
            data[sel] = items
            print(f"  [{sel}] --> {len(items)} results", end="")
            if items:
                preview = items[0][:80] if isinstance(items[0], str) else items[0]
                print(f"  (e.g. {preview!r})", end="")
            print()
        result = {"success": True, "url": url, "status_code": response.status_code, "data": data}

    elif MODE == "crawl":
        result = scraper.crawl(
            start_url=url,
            max_pages=CRAWL_MAX_PAGES,
            max_depth=CRAWL_MAX_DEPTH,
            same_domain_only=True,
            delay_seconds=0.5,
        )
        stats = result.get("statistics", {})
        print(f"  Pages crawled  : {result.get('pages_crawled')}")
        print(f"  Pages found    : {result.get('pages_discovered')}")
        print(f"  Unique links   : {stats.get('total_unique_links', 0)}")
        print(f"  Avg load time  : {stats.get('avg_load_time', 0):.2f}s")

    elif MODE == "full":
        result = extract_full_content(response.html, url, response.status_code, response.load_time)
        print(f"  Title      : {result['title'] or '(no title)'}")
        print(f"  Text blocks: {len(result['text_blocks'])}")
        print(f"  Full text  : {len(result['full_text']):,} chars")
        print(f"  Images     : {len(result['images'])}  (ocr_pending)")
        print(f"  PDFs       : {len(result['pdfs'])}  (ocr_pending)")

    else:
        raise ValueError(f"Unknown MODE: {MODE!r}")

    saved = save_json(result, slug(url))
    if saved:
        print(f"  Saved --> {saved}")

    return result


def main():
    scraper = WebScraper()

    try:
        if MODE == "crawl_full":
            start_urls = BATCH_URLS if BATCH_URLS else [TARGET_URL]
            total = len(start_urls)
            for i, start_url in enumerate(start_urls, 1):
                print(f"\n[School {i}/{total}]")
                site_data = crawl_and_extract(scraper, start_url)
                if SAVE_DIR:
                    site_path = save_site(site_data)
                    print(f"  Site file --> {site_path}\n")

        else:
            # All other modes: run per-URL (single or batch)
            urls = BATCH_URLS if BATCH_URLS else [TARGET_URL]
            is_batch = bool(BATCH_URLS)

            print(f"\n{'='*60}")
            print(f"  {'BATCH' if is_batch else 'SINGLE'} mode -- {len(urls)} URL(s)")
            print(f"{'='*60}")

            all_results = []
            for url in urls:
                result = run_single(scraper, url)
                all_results.append(result)

            if is_batch and SAVE_DIR:
                summary_path = save_json(all_results, "batch_summary")
                ok = sum(1 for r in all_results if r.get("success"))
                print(f"\n{'='*60}")
                print(f"  Batch done: {ok}/{len(urls)} succeeded")
                print(f"  Summary  --> {summary_path}")
                print(f"{'='*60}\n")

    finally:
        scraper.cleanup()


if __name__ == "__main__":
    main()
