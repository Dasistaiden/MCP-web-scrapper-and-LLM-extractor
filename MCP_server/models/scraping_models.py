from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any, List
from enum import Enum


class ScrapingMethod(str, Enum):
    """Scraping method used"""
    STATIC = "static"  
    DYNAMIC = "dynamic" 


class ScrapingRequest(BaseModel):
    """Request to scrape a webpage"""
    url: HttpUrl
    javascript_loading: bool = False
    timeout: int = Field(default=30, ge=1, le=120)
    wait_time: int = Field(default=3, ge=0, le=30)
    headers: Optional[Dict[str, str]] = None
    user_agent: Optional[str] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class ScrapingResponse(BaseModel):
    """Response from scraping operation"""
    url: str
    html: str
    status_code: int
    method: ScrapingMethod
    load_time: float
    error: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)


class ElementSelector(BaseModel):
    """Find the element(s) in the HTML using CSS selector"""
    css_selector: str
    attribute: str = "text"
    multiple: bool = True


class ExtractRequest(BaseModel):
    """Request to extract data from HTML using selectors"""
    html: str
    selectors: List[ElementSelector]


class ExtractResponse(BaseModel):
    """Response with extracted data"""
    extracted_data: Dict[str, Any]
    error: Optional[str] = None