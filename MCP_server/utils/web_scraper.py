import asyncio
import logging
import time
import traceback
from typing import Dict, Any

import requests
from bs4 import BeautifulSoup

from urllib.parse import urljoin, urlparse
from collections import deque
from typing import Set, Dict, List, Optional

from MCP_server.models.scraping_models import (
    ScrapingRequest,
    ScrapingResponse,
    ScrapingMethod,
    ElementSelector,
    ExtractRequest,
    ExtractResponse
)

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Web scraper optimized for MCP server usage.
    Handles both static HTML and JavaScript-rendered pages.
    """
    
    def __init__(self):
        """Initialize the WebScraper with a session for connection pooling."""
        self.session = requests.Session()
    
    def cleanup(self):
        """Clean up resources - called when MCP server shuts down."""
        if hasattr(self, 'session'):
            self.session.close()
    
    def scrape(self, request: ScrapingRequest) -> ScrapingResponse:
        """
        Main entry point for scraping. Routes to static or dynamic scraping.
        
        Args:
            request: ScrapingRequest with URL and options
            
        Returns:
            ScrapingResponse with HTML content or error
        """
        try:
            method = "Dynamic" if request.javascript_loading else "Static"
            logger.info(f"[WebScraper]: {method} scraping selected for {request.url}")
            
            if request.javascript_loading:
                return self._scrape_dynamic(request)
            return self._scrape_static(request)
            
        except Exception as e:
            logger.error(
                f"[WebScraper]: Scraping failed for {request.url}\n"
                f"Error: {str(e)}\n{traceback.format_exc()}"
            )
            return self._create_error_response(
                request.url, 
                str(e), 
                ScrapingMethod.STATIC
            )
    
    def _scrape_static(self, request: ScrapingRequest) -> ScrapingResponse:
        """
        Scrape static content using requests library.
        Fast and simple for non-JavaScript websites.
        
        Args:
            request: ScrapingRequest object
            
        Returns:
            ScrapingResponse with scraped content
        """
        start_time = time.time()
        
        try:
            headers = self._prepare_headers(request)
            
            logger.info(f"[WebScraper]: Starting static scraping for {request.url}")
            response = self.session.get(
                str(request.url),
                headers=headers,
                timeout=request.timeout
            )
            response.raise_for_status()
            
            return ScrapingResponse(
                url=str(request.url),
                html=response.text,
                status_code=response.status_code,
                method=ScrapingMethod.STATIC,
                headers=dict(response.headers),
                load_time=time.time() - start_time
            )
            
        except requests.RequestException as e:
            logger.error(
                f"[WebScraper]: Static scraping failed for {request.url}\n"
                f"Error: {str(e)}\n{traceback.format_exc()}"
            )
            
            status_code = getattr(e.response, 'status_code', 0) if hasattr(e, 'response') else 0
            
            return ScrapingResponse(
                url=str(request.url),
                html="",
                status_code=status_code,
                method=ScrapingMethod.STATIC,
                error=str(e),
                load_time=time.time() - start_time
            )
    
    def _scrape_dynamic(self, request: ScrapingRequest) -> ScrapingResponse:
        """
        Scrape JavaScript-rendered content using Playwright.
        MCP always runs async, so we only use async Playwright.
        
        Args:
            request: ScrapingRequest object
            
        Returns:
            ScrapingResponse with scraped content
        """
        start_time = time.time()
        
        try:
            # Check if Playwright is installed
            try:
                from playwright.async_api import async_playwright
                import nest_asyncio
            except ImportError:
                error_msg = (
                    "Playwright or nest_asyncio not installed. "
                    "Run: pip install playwright nest-asyncio && playwright install chromium"
                )
                logger.error(f"[WebScraper]: {error_msg}")
                return self._create_error_response(
                    request.url,
                    error_msg,
                    ScrapingMethod.DYNAMIC,
                    time.time() - start_time
                )
            
            # MCP always runs async, so we use async playwright with nest_asyncio
            logger.info("[WebScraper]: Using async Playwright for MCP")
            
            # Apply nest_asyncio to handle nested event loops in MCP
            nest_asyncio.apply()
            
            # Create a new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                return loop.run_until_complete(
                    self._async_playwright_scrape(request, start_time)
                )
            finally:
                loop.close()
            
        except Exception as e:
            logger.error(
                f"[WebScraper]: Dynamic scraping failed\n"
                f"Error: {str(e)}\n{traceback.format_exc()}"
            )
            return self._create_error_response(
                request.url, 
                str(e), 
                ScrapingMethod.DYNAMIC,
                time.time() - start_time
            )
    
    async def _async_playwright_scrape(
        self, 
        request: ScrapingRequest, 
        start_time: float
    ) -> ScrapingResponse:
        """
        Async Playwright implementation for JavaScript rendering.
        This is what actually runs the browser automation.
        """
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                # Create browser context with optional user agent
                context = await browser.new_context(
                    user_agent=request.user_agent or None
                )
                
                # Set custom headers if provided
                if request.headers:
                    await context.set_extra_http_headers(request.headers)
                
                # Create new page and navigate
                page = await context.new_page()
                response = await page.goto(
                    str(request.url),
                    timeout=request.timeout * 1000,  # Convert to milliseconds
                    wait_until='networkidle'  # Wait for network to be idle
                )
                
                # Optional additional wait for dynamic content
                if request.wait_time:
                    await page.wait_for_timeout(request.wait_time * 1000)
                
                # Get the fully rendered HTML
                html_content = await page.content()
                status_code = response.status if response else 200
                headers = await response.all_headers() if response else {}
                
                return ScrapingResponse(
                    url=str(request.url),
                    html=html_content,
                    status_code=status_code,
                    method=ScrapingMethod.DYNAMIC,
                    headers=headers,
                    load_time=time.time() - start_time
                )
            finally:
                await browser.close()
    
    def extract_elements(self, extract_request: ExtractRequest) -> ExtractResponse:
        """
        Extract specific elements from HTML using CSS selectors.
        Works like jQuery - finds elements and extracts their data.
        
        Args:
            extract_request: Contains HTML and list of selectors
            
        Returns:
            ExtractResponse with extracted data for each selector
        """
        try:
            soup = BeautifulSoup(extract_request.html, 'html.parser')
            extracted_data = {}
            
            # Process each selector
            for i, selector in enumerate(extract_request.selectors):
                key = f"selector_{i}"
                extracted_data[key] = self._extract_single_selector(soup, selector)
            
            return ExtractResponse(extracted_data=extracted_data)
            
        except Exception as e:
            logger.error(f"[WebScraper]: Extraction error: {str(e)}")
            return ExtractResponse(
                extracted_data={},
                error=str(e)
            )
    
    def _extract_single_selector(
        self, 
        soup: BeautifulSoup, 
        selector: ElementSelector
    ) -> Any:
        """
        Extract data for a single CSS selector.
        Can extract text, attributes (href, src, etc.), or raw HTML.
        """       
        if not selector.css_selector:
            return None
        
        # Find elements using CSS selector
        if selector.multiple:
            # Get all matching elements
            elements = soup.select(selector.css_selector)
        else:
            # Get first matching element only
            element = soup.select_one(selector.css_selector)
            elements = [element] if element else []
        
        # Return empty result if no elements found
        if not elements:
            return [] if selector.multiple else None
        
        # Extract the requested data from elements
        if not selector.attribute:
            # No attribute specified - return raw HTML
            data = [str(el) for el in elements]
        elif selector.attribute == 'text':
            # Extract text content
            data = [el.get_text(strip=True) for el in elements]
        else:
            # Extract specific attribute (href, src, id, class, etc.)
            data = [el.get(selector.attribute) for el in elements]
        
        # Return list for multiple, single value otherwise
        if selector.multiple:
            return data
        else:
            return data[0] if data else None
        
        
    def crawl(
        self,
        start_url: str,
        max_pages: int = 50,
        max_depth: int = 3,
        same_domain_only: bool = True,
        delay_seconds: float = 0.5
    ) -> Dict[str, Any]:
        """
        Crawl a website starting from a URL, discovering its structure.
        Reuses the existing scrape and extract methods.
        
        Args:
            start_url: Starting URL for the crawl
            max_pages: Maximum pages to crawl
            max_depth: Maximum depth from start URL
            same_domain_only: Stay within the same domain
            delay_seconds: Delay between requests
        
        Returns:
            Site structure, statistics, and discovered pages
        """
        try:
            logger.info(f"[WebScraper]: Starting crawl from {start_url}")
            
            start_domain = urlparse(start_url).netloc
            
            # Initialize the crawler state 
            to_visit = deque([(start_url, 0)])  # (url, depth)
            visited = set()
            site_map = {}
            failed_urls = []
            
            pages_crawled = 0
            
            while to_visit and pages_crawled < max_pages:
                current_url, depth = to_visit.popleft()
                
                if current_url in visited or depth > max_depth:
                    continue
                
                # Set a delay to avoid overwhelming servers 
                if pages_crawled > 0:
                    time.sleep(delay_seconds)
                
                logger.info(f"[WebScraper]: Crawling {current_url} (depth: {depth})")
                
                # Use existing scrape method of the class
                request = ScrapingRequest(
                    url=current_url,
                    javascript_loading=False,  # Crawling usually doesn't need JS
                    timeout=10  # Faster timeout for crawling
                )
                response = self.scrape(request)
                
                if response.error:
                    failed_urls.append({
                        "url": current_url,
                        "error": response.error
                    })
                    visited.add(current_url)
                    continue
                
                pages_crawled += 1
                visited.add(current_url)
                
                # Extract page info using existing extract method
                extract_req = ExtractRequest(
                    html=response.html,
                    selectors=[
                        ElementSelector(css_selector="title", attribute="text", multiple=False),
                        ElementSelector(css_selector="h1", attribute="text", multiple=False),
                        ElementSelector(css_selector="a[href]", attribute="href", multiple=True)
                    ]
                )
                extract_response = self.extract_elements(extract_req)
                
                # Process extracted data
                data = extract_response.extracted_data
                title = data.get("selector_0", "")
                h1 = data.get("selector_1", "")
                raw_links = data.get("selector_2", []) or []
                
                # Process links
                discovered_links = []
                for link in raw_links:
                    if not link:
                        continue
                    
                    # Make absolute URL
                    absolute_url = urljoin(current_url, link)
                    
                    # Parse URL
                    parsed = urlparse(absolute_url)
                    
                    # Skip non-HTTP links
                    if parsed.scheme not in ['http', 'https']:
                        continue
                    
                    # Remove fragment
                    clean_url = absolute_url.split('#')[0]
                    
                    # Check domain restriction
                    if same_domain_only and parsed.netloc != start_domain:
                        continue
                    
                    discovered_links.append(clean_url)
                    
                    # Add to queue if not visited
                    if clean_url not in visited and depth < max_depth:
                        to_visit.append((clean_url, depth + 1))
                
                # Store page info
                site_map[current_url] = {
                    "url": current_url,
                    "title": title,
                    "h1": h1,
                    "depth": depth,
                    "status_code": response.status_code,
                    "load_time": response.load_time,
                    "outgoing_links": list(set(discovered_links)),
                    "link_count": len(set(discovered_links))
                }
            
            # Calculate statistics
            all_links = set()
            for page in site_map.values():
                all_links.update(page.get("outgoing_links", []))
            
            return {
                "success": True,
                "start_url": start_url,
                "pages_crawled": pages_crawled,
                "pages_discovered": len(visited) + len(to_visit),
                "site_map": site_map,
                "failed_urls": failed_urls,
                "statistics": {
                    "total_unique_links": len(all_links),
                    "max_depth_reached": max(p["depth"] for p in site_map.values()) if site_map else 0,
                    "avg_load_time": sum(p["load_time"] for p in site_map.values()) / len(site_map) if site_map else 0
                }
            }
            
        except Exception as e:
            logger.error(f"[WebScraper]: Crawl failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "start_url": start_url
            }
        
    # ========== Static Helper Methods ==========
    
    @staticmethod
    def _prepare_headers(request: ScrapingRequest) -> Dict[str, str]:
        """
        Prepare HTTP headers for the request.
        Combines default user-agent with any custom headers.
        """
        headers = request.headers or {}
        if request.user_agent and 'User-Agent' not in headers:
            headers['User-Agent'] = request.user_agent
        return headers
    
    @staticmethod
    def _create_error_response(
        url: str, 
        error: str, 
        method: ScrapingMethod,
        load_time: float = 0
    ) -> ScrapingResponse:
        """
        Create a standardized error response.
        Ensures consistent error format across all scraping methods.
        """
        return ScrapingResponse(
            url=str(url),
            html="",
            status_code=0,
            method=method,
            error=error,
            load_time=load_time
        )
    
    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        """
        Utility to parse HTML string into BeautifulSoup object.
        Can be used independently for HTML parsing needs.
        
        Args:
            html: HTML string to parse
            
        Returns:
            BeautifulSoup object for HTML traversal
        """
        return BeautifulSoup(html, 'html.parser')