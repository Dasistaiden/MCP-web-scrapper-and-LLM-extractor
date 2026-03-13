import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))   # shared modules: schema, db_reference

from mcp.server.fastmcp import FastMCP
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, List, Any, Union
from pydantic import HttpUrl

from MCP_server.utils.web_scraper import WebScraper
from MCP_server.models.scraping_models import (
    ScrapingRequest,
    ElementSelector,
    ExtractRequest
)
from schema import EXTRACTION_TEMPLATE, SchoolProfile, FIELD_URL_HINTS
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraping_server.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Create the MCP server
mcp = FastMCP("whed-tools")

# Initialize the web scraper (single instance for all requests)
scraper = WebScraper()


def _save_result(result: Union[Dict, List], save_path: str) -> str:
    """Save scraping result as JSON to the specified path.
    
    If save_path is a directory, auto-generate a timestamped filename inside it.
    Returns the final path where the file was saved.
    """
    path = Path(save_path)

    if path.is_dir() or save_path.endswith(("/", "\\")):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = path / f"scrape_{timestamp}.json"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"Result saved to: {path}")
    return str(path)


@mcp.tool()
def scrape_url(
    url: str,
    javascript: bool = False,
    wait_seconds: int = 3,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scrape a webpage and return its HTML content.
    
    Args:
        url: The webpage URL to scrape
        javascript: Set to True for JavaScript-rendered sites (slower but handles dynamic content)
        wait_seconds: How long to wait for JavaScript to load (only used when javascript=True)
        save_path: Optional file path to save the result as JSON (e.g. "C:/Users/me/Desktop/result.json").
                   If a directory is given, a timestamped filename is generated automatically.
    
    Returns:
        Dictionary with html content, status code, and load time
    """
    try:
        logger.info(f"Scraping: {url} (JavaScript: {javascript})")
        
        # Create request object
        request = ScrapingRequest(
            url=HttpUrl(url),
            javascript_loading=javascript,
            wait_time=wait_seconds if javascript else 0
        )
        
        # Perform scraping
        response = scraper.scrape(request)
        
        # Return simplified response
        if response.error:
            logger.error(f"Scraping failed: {response.error}")
            result = {
                "success": False,
                "error": response.error,
                "url": url
            }
        else:
            logger.info(f"Successfully scraped {url} in {response.load_time:.2f}s")
            result = {
                "success": True,
                "url": url,
                "html": response.html,
                "status_code": response.status_code,
                "load_time": response.load_time,
                "method": response.method.value
            }

        if save_path:
            saved_to = _save_result(result, save_path)
            result["saved_to"] = saved_to

        return result
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


@mcp.tool()
def extract_data(
    url: str,
    css_selectors: List[str],
    attributes: Optional[List[str]] = None,
    javascript: bool = False,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scrape a webpage and extract specific data using CSS selectors.
    
    Args:
        url: The webpage to scrape
        css_selectors: List of CSS selectors (e.g., ["h1", "a.link", "#content"])
        attributes: List of attributes to extract for each selector (e.g., ["text", "href", "text"])
                   If not provided, defaults to "text" for all selectors
        javascript: Set to True for JavaScript-rendered sites
        save_path: Optional file path to save the result as JSON (e.g. "C:/Users/me/Desktop/result.json").
                   If a directory is given, a timestamped filename is generated automatically.
    
    Returns:
        Dictionary with extracted data for each selector
    
    Example:
        extract_data(
            url="https://example.com",
            css_selectors=["h1", "a"],
            attributes=["text", "href"]
        )
    """
    try:
        logger.info(f"Extracting from {url}: {css_selectors}")
        
        # First scrape the page
        request = ScrapingRequest(
            url=HttpUrl(url),
            javascript_loading=javascript
        )
        
        response = scraper.scrape(request)
        
        if response.error:
            return {
                "success": False,
                "error": f"Scraping failed: {response.error}",
                "url": url
            }
        
        # Prepare selectors for extraction
        if not attributes:
            attributes = ["text"] * len(css_selectors)
        
        element_selectors = [
            ElementSelector(
                css_selector=selector,
                attribute=attr,
                multiple=True  # Always get all matches
            )
            for selector, attr in zip(css_selectors, attributes)
        ]
        
        # Extract data
        extract_request = ExtractRequest(
            html=response.html,
            selectors=element_selectors
        )
        
        extract_response = scraper.extract_elements(extract_request)
        
        # Format results with meaningful names
        results = {}
        for i, selector in enumerate(css_selectors):
            key = f"selector_{i}"
            data = extract_response.extracted_data.get(key, [])
            results[selector] = data
        
        result = {
            "success": True,
            "url": url,
            "data": results,
            "status_code": response.status_code
        }

        if save_path:
            saved_to = _save_result(result, save_path)
            result["saved_to"] = saved_to

        return result
        
    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


@mcp.tool()
def extract_first(
    url: str,
    css_selector: str,
    attribute: str = "text",
    javascript: bool = False,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract the first matching element from a webpage.
    Useful for getting single values like page title, main heading, etc.
    
    Args:
        url: The webpage to scrape
        css_selector: CSS selector for the element (e.g., "h1", "title", "meta[name='description']")
        attribute: What to extract - "text" for content, or attribute name like "href", "content", "src"
        javascript: Set to True for JavaScript-rendered sites
        save_path: Optional file path to save the result as JSON (e.g. "C:/Users/me/Desktop/result.json").
                   If a directory is given, a timestamped filename is generated automatically.
    
    Returns:
        Dictionary with the extracted value
    
    Example:
        extract_first(url="https://example.com", css_selector="title", attribute="text")
    """
    try:
        logger.info(f"Extracting first {css_selector} from {url}")
        
        # Scrape the page
        request = ScrapingRequest(
            url=HttpUrl(url),
            javascript_loading=javascript
        )
        
        response = scraper.scrape(request)
        
        if response.error:
            return {
                "success": False,
                "error": f"Scraping failed: {response.error}",
                "url": url
            }
        
        # Extract single element
        element_selector = ElementSelector(
            css_selector=css_selector,
            attribute=attribute,
            multiple=False  # Only get first match
        )
        
        extract_request = ExtractRequest(
            html=response.html,
            selectors=[element_selector]
        )
        
        extract_response = scraper.extract_elements(extract_request)
        value = extract_response.extracted_data.get("selector_0")
        
        result = {
            "success": True,
            "url": url,
            "selector": css_selector,
            "attribute": attribute,
            "value": value,
            "found": value is not None
        }

        if save_path:
            saved_to = _save_result(result, save_path)
            result["saved_to"] = saved_to

        return result
        
    except Exception as e:
        logger.error(f"Error extracting first: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


@mcp.tool()
def batch_scrape(
    urls: List[str],
    javascript: bool = False,
    save_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Scrape multiple URLs efficiently.
    
    Args:
        urls: List of URLs to scrape
        javascript: Set to True if the sites need JavaScript rendering
        save_path: Optional file path to save all results as a JSON array (e.g. "C:/Users/me/Desktop/batch.json").
                   If a directory is given, a timestamped filename is generated automatically.
    
    Returns:
        List of scraping results for each URL
    """
    results = []
    total = len(urls)
    
    for i, url in enumerate(urls, 1):
        logger.info(f"Batch scraping {i}/{total}: {url}")
        
        result = scrape_url(url, javascript=javascript)
        result["index"] = i - 1
        results.append(result)
    
    successful = sum(1 for r in results if r.get("success"))
    logger.info(f"Batch complete: {successful}/{total} successful")

    if save_path:
        _save_result(results, save_path)

    return results

@mcp.tool()
def crawl_website(
    start_url: str,
    max_pages: int = 50,
    max_depth: int = 3,
    same_domain_only: bool = True,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crawl a website to discover its structure and pages.
    
    Args:
        start_url: Starting URL
        max_pages: Maximum pages to crawl (default 50)
        max_depth: Maximum link depth (default 3)
        same_domain_only: Stay on same domain (default True)
        save_path: Optional file path to save the site map as JSON (e.g. "C:/Users/me/Desktop/sitemap.json").
                   If a directory is given, a timestamped filename is generated automatically.
    
    Returns:
        Site map with discovered pages and statistics
    """
    result = scraper.crawl(
        start_url=start_url,
        max_pages=max_pages,
        max_depth=max_depth,
        same_domain_only=same_domain_only,
        delay_seconds=0.5  # Delay between requests to avoid overloading servers (you can adjust this if you want)
    )

    if save_path:
        saved_to = _save_result(result, save_path)
        result["saved_to"] = saved_to

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Extraction tools — let the host LLM extract structured profiles directly
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_extraction_schema() -> Dict[str, Any]:
    """
    Return the WHED extraction schema (REQUIRED fields only).

    The host LLM should use this template to know which fields to extract
    from scraped website content. Each field includes its type and priority.

    Typical workflow:
      1. crawl_website / scrape_url  → get site content
      2. get_extraction_schema       → know what to extract
      3. get_db_context(domain)      → get allowed values & reference example
      4. (Host LLM extracts data)
      5. validate_profile(json)      → check the extraction
      6. save_profile(domain, json)  → persist the result
    """
    return {
        "success": True,
        "schema": EXTRACTION_TEMPLATE,
        "instructions": (
            "Extract data from website content into this JSON structure. "
            "Fill REQUIRED fields actively; use null when information is missing. "
            "For enum fields, use only values from get_db_context() allowed lists. "
            "Return a single flat JSON object matching this schema."
        ),
    }


@mcp.tool()
def get_db_context(domain: str) -> Dict[str, Any]:
    """
    Return WHED database reference data for a given institution domain.

    Provides two types of grounding to reduce hallucination:
      1. Picklists — valid enum values (institution types, funding, divisions, etc.)
      2. Reference example — a complete record from the same country

    Args:
        domain: Institution website domain (e.g. 'www.ampa.edu.au')

    Returns:
        Dictionary with picklists, country code, and a reference example
    """
    try:
        from db_reference import (
            is_db_available, build_db_context, detect_country_code,
            get_picklists, get_national_inst_types, get_reference_example,
        )
    except ImportError:
        return {
            "success": False,
            "error": "db_reference module not available (pymysql not installed?)",
        }

    if not is_db_available():
        return {
            "success": False,
            "error": "WHED database not reachable. Check .env DB settings.",
        }

    country_code = detect_country_code(domain)

    try:
        picklists = get_picklists()
    except Exception as e:
        return {"success": False, "error": f"Failed to load picklists: {e}"}

    result: Dict[str, Any] = {
        "success": True,
        "domain": domain,
        "country_code": country_code,
        "allowed_values": {
            "institution_type_international": [
                f"{p['code']} ({p['label']})" for p in picklists["inst_class"]
            ],
            "funding_type": [
                f"{p['code']} ({p['label']})" for p in picklists["funding_type"]
            ],
            "division_type": [p["label"] for p in picklists["division_type"]],
            "job_function": [
                f"{p['label']} (code: {p['code']})" for p in picklists["job_function"]
            ],
            "gender": [
                f"{p['code']} ({p['label']})" for p in picklists["gender"]
            ],
            "fields_of_study_sample": picklists["fos"][:60],
            "languages": picklists["languages"][:40],
            "credential_categories": [
                f"{p['label']} ({p['code']})" for p in picklists["cred_cat"]
            ],
            "credential_levels": [
                f"{p['label']} ({p['code']})" for p in picklists["cred_level"]
            ],
        },
    }

    if country_code:
        nat_types = get_national_inst_types(country_code)
        if nat_types:
            result["allowed_values"]["institution_type_national"] = nat_types

        ref_example = get_reference_example(country_code)
        if ref_example:
            result["reference_example"] = ref_example

    return result


@mcp.tool()
def validate_profile(profile_json: str) -> Dict[str, Any]:
    """
    Validate an extracted institution profile against the Pydantic schema
    and WHED database picklists.

    Args:
        profile_json: JSON string of the extracted profile
                      (must match the structure from get_extraction_schema)

    Returns:
        Dictionary with validation status, cleaned data, and any warnings
    """
    from pydantic import ValidationError

    try:
        data = json.loads(profile_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}

    now = datetime.now().isoformat(timespec="seconds")
    data.setdefault("domain", "unknown")
    data.setdefault("source_url", "")
    data.setdefault("extracted_at", now)
    data.setdefault("extraction_model", "mcp-host-llm")

    pydantic_ok = True
    pydantic_errors = None
    try:
        profile = SchoolProfile(**data)
        cleaned = profile.model_dump()
    except ValidationError as e:
        pydantic_ok = False
        pydantic_errors = str(e)
        cleaned = data

    db_warnings = []
    domain = data.get("domain", "")
    try:
        from db_reference import (
            is_db_available, get_picklists, detect_country_code,
            get_national_inst_types,
        )
        if is_db_available():
            picklists = get_picklists()
            org = cleaned.get("org_basics", {})

            valid_ic = {p["code"] for p in picklists["inst_class"]}
            ic = org.get("institution_type_international")
            if ic and ic not in valid_ic:
                db_warnings.append(
                    f"institution_type_international '{ic}' not in DB: {sorted(valid_ic)}"
                )

            valid_ft = {p["code"] for p in picklists["funding_type"]}
            ft = org.get("funding_type")
            if ft and ft not in valid_ft:
                db_warnings.append(f"funding_type '{ft}' not in DB: {sorted(valid_ft)}")

            country = detect_country_code(domain)
            if country:
                valid_nat = set(get_national_inst_types(country))
                nat = org.get("institution_type_national")
                if nat and valid_nat and nat not in valid_nat:
                    db_warnings.append(
                        f"institution_type_national '{nat}' not in DB for {country}"
                    )

            valid_dt = {p["label"] for p in picklists["division_type"]}
            for div in cleaned.get("divisions", []):
                dt = div.get("division_type")
                if dt and dt not in valid_dt:
                    db_warnings.append(f"division_type '{dt}' not in DB")

            valid_fos = set(picklists["fos"])
            for div in cleaned.get("divisions", []):
                for fos in div.get("fields_of_study", []):
                    if fos and fos not in valid_fos:
                        db_warnings.append(f"field_of_study '{fos}' not in WHED FOS list")

            valid_cred_level = {p["label"] for p in picklists["cred_level"]}
            for i, dp in enumerate(cleaned.get("degree_programs", [])):
                lvl = dp.get("level")
                if lvl and lvl not in valid_cred_level:
                    db_warnings.append(
                        f"degree_programs[{i}].level '{lvl}' not in WHED credential_levels"
                    )
    except Exception:
        pass

    return {
        "success": True,
        "pydantic_valid": pydantic_ok,
        "pydantic_errors": pydantic_errors,
        "db_warnings": db_warnings,
        "cleaned_profile": cleaned,
    }


@mcp.tool()
def save_profile(
    domain: str,
    profile_json: str,
    output_dir: str = "output/structured",
) -> Dict[str, Any]:
    """
    Save a validated institution profile to disk as JSON.

    Args:
        domain: Institution domain (e.g. 'www.ampa.edu.au'), used as filename
        profile_json: JSON string of the profile to save
        output_dir: Directory to save into (default: output/structured)

    Returns:
        Dictionary with save status and file path
    """
    try:
        data = json.loads(profile_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}

    now = datetime.now().isoformat(timespec="seconds")
    data.setdefault("domain", domain)
    data.setdefault("source_url", "")
    data.setdefault("extracted_at", now)
    data.setdefault("extraction_model", "mcp-host-llm")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{domain}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Profile saved: {out_path}")
    return {
        "success": True,
        "saved_to": str(out_path),
        "domain": domain,
        "fields_count": {
            "org_basics": len(data.get("org_basics", {})),
            "key_contacts": len(data.get("key_contacts", [])),
            "divisions": len(data.get("divisions", [])),
            "degree_programs": len(data.get("degree_programs", [])),
        },
    }


# Resource for help/documentation
@mcp.resource("scraping://help")
def get_help() -> str:
    """Get help documentation for the web scraping tools"""
    return """
    WEB SCRAPING & EXTRACTION TOOLS
    ================================

    SCRAPING:
    - scrape_url(url)              Get full HTML of a webpage
    - extract_data(url, selectors) Extract data via CSS selectors
    - extract_first(url, selector) Get a single element value
    - batch_scrape(urls)           Scrape multiple URLs
    - crawl_website(start_url)     Discover site structure and pages

    STRUCTURED EXTRACTION (MCP-native, no external LLM needed):
    - get_extraction_schema()      Get the WHED field template (what to extract)
    - get_db_context(domain)       Get allowed values & reference example from WHED DB
    - validate_profile(json)       Validate extraction against schema + DB
    - save_profile(domain, json)   Save validated profile to disk

    EXTRACTION WORKFLOW:
    1. crawl_website(url) or scrape_url(url)  -> get site content
    2. get_extraction_schema()                -> know what fields to fill
    3. get_db_context(domain)                 -> get picklists & reference
    4. (You extract the data from the content)
    5. validate_profile(json_string)          -> check for errors
    6. save_profile(domain, json_string)      -> persist the result
    """


if __name__ == "__main__":
    logger.info("🚀 Starting Web Scraping MCP Server")
    logger.info("Server ready for connections")
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        scraper.cleanup()
        logger.info("Server stopped")