from utils.web_scraper import WebScraper
from models.scraping_models import ScrapingRequest
from pydantic import HttpUrl

scraper = WebScraper()

website_test = 'https://books.toscrape.com/'

# Test static approach
request_static = ScrapingRequest(
    url=HttpUrl(website_test),
    javascript_loading=False)
response = scraper.scrape(request_static)
print(f"Static Scraping Success: {response.error is None}")
print(f"HTML length: {len(response.html)}")

print(3*"---")

# Test dynamic approach
request_dynamic = ScrapingRequest(
    url=HttpUrl(website_test),
    javascript_loading=True)
response = scraper.scrape(request_dynamic)
print(f"Dynamic Scraping Success: {response.error is None}")
print(f"HTML length: {len(response.html)}")

print(3*"---")

# Test crawler
print("Testing Crawler...")
crawl_result = scraper.crawl(
    start_url=website_test,
    max_pages=5,  # Small number for testing
    max_depth=2,   # Shallow depth for testing
    same_domain_only=True,
    delay_seconds=0.2  # Shorter delay for testing
)

if crawl_result.get("success"):
    print(f"Crawler Success: True")
    print(f"Pages crawled: {crawl_result.get('pages_crawled')}")
    print(f"Pages discovered: {crawl_result.get('pages_discovered')}")
    print(f"Failed URLs: {len(crawl_result.get('failed_urls', []))}")
    
    # Show first few discovered pages
    site_map = crawl_result.get('site_map', {})
    print(f"\nFirst {min(3, len(site_map))} pages discovered:")
    for i, (url, info) in enumerate(list(site_map.items())[:3], 1):
        print(f"  {i}. {info.get('title', 'No title')}")
        print(f"     URL: {url}")
        print(f"     Links found: {info.get('link_count', 0)}")
        print(f"     Depth: {info.get('depth', 0)}")
    
    # Show statistics
    stats = crawl_result.get('statistics', {})
    print(f"\nStatistics:")
    print(f"  Total unique links: {stats.get('total_unique_links', 0)}")
    print(f"  Max depth reached: {stats.get('max_depth_reached', 0)}")
    print(f"  Avg load time: {stats.get('avg_load_time', 0):.2f}s")
else:
    print(f"Crawler Success: False")
    print(f"Error: {crawl_result.get('error')}")