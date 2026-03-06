from mcp.server.fastmcp import FastMCP
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from pydantic import HttpUrl

# Import the scraper and models
from utils.web_scraper import WebScraper
from models.scraping_models import (
    ScrapingRequest,
    ElementSelector,
    ExtractRequest
)

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
mcp = FastMCP("WebScraper")

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


# Resource for help/documentation
@mcp.resource("scraping://help")
def get_help() -> str:
    """Get help documentation for the web scraping tools"""
    return """
    🔧 WEB SCRAPING TOOLS
    =====================
    
    BASIC SCRAPING:
    • scrape_url(url, javascript=False)
      Get the full HTML of any webpage
      Use javascript=True for sites like Twitter, YouTube, React apps
    
    DATA EXTRACTION:
    • extract_data(url, css_selectors, attributes)
      Extract multiple pieces of data at once
      Example: Get all links → css_selectors=["a"], attributes=["href"]
    
    • extract_first(url, css_selector, attribute)
      Get a single value from a page
      Example: Get title → css_selector="title", attribute="text"
    
    BATCH OPERATIONS:
    • batch_scrape(urls, javascript=False)
      Scrape multiple URLs efficiently
    
    CSS SELECTOR EXAMPLES:
    • "h1" → All h1 headings
    • ".className" → Elements with class
    • "#idName" → Element with ID
    • "a[href*='example']" → Links containing 'example'
    • "div > p" → Direct paragraph children of divs
    
    ATTRIBUTES TO EXTRACT:
    • "text" → Text content
    • "href" → Link URLs
    • "src" → Image/script sources
    • "content" → Meta tag content
    • "alt" → Alt text
    • Any HTML attribute!
    
    JAVASCRIPT SITES:
    Set javascript=True for:
    • Single-page applications (React, Vue, Angular)
    • Dynamically loaded content
    • Sites that show loading spinners
    • Social media feeds
    
    Note: JavaScript scraping is slower but necessary for modern sites.
    """


if __name__ == "__main__":
    logger.info("🚀 Starting Web Scraping MCP Server")
    logger.info("Server ready for connections from Claude Desktop")
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        scraper.cleanup()
        logger.info("Server stopped")