"""
API data models for request and response validation.

This module defines Pydantic models for validating API requests and responses,
providing clear documentation and type safety for the API endpoints.
"""

import re
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl, validator, root_validator


# Enums for standard options
class DataType(str, Enum):
    """Enum for data type options."""
    AUTO = "auto"
    PRODUCT = "product"
    ARTICLE = "article"
    LIST = "list"
    TABLE = "table"
    GENERIC = "generic"


class JobType(str, Enum):
    """Enum for job type options."""
    SIMPLE_SCRAPE = "simple_scrape"
    RECURSIVE_SCRAPE = "recursive_scrape"
    ADAPTIVE_SCRAPE = "adaptive_scrape"
    VISUAL_SCRAPE = "visual_scrape"
    SCHEDULED_SCRAPE = "scheduled_scrape"


class JobStatus(str, Enum):
    """Enum for job status options."""
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    QUEUED = "queued"


class OutputFormat(str, Enum):
    """Enum for output format options."""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    XLSX = "xlsx"
    XML = "xml"


class ScheduleType(str, Enum):
    """Enum for schedule type options."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONE_TIME = "one_time"


# Request Models
class ApiKeyRequest(BaseModel):
    """Model for API key generation request."""
    user_id: str = Field(..., description="User ID")
    name: str = Field(None, description="Name for the API key")
    permissions: List[str] = Field(None, description="List of permissions")


class TokenRequest(BaseModel):
    """Model for token generation request."""
    api_key: str = Field(..., description="API key")
    expiration: int = Field(3600, description="Token expiration time in seconds")


class SimpleScrapeRequest(BaseModel):
    """Model for simple scrape request."""
    url: HttpUrl = Field(..., description="URL to scrape")
    compile_text: bool = Field(True, description="Whether to compile text analysis")
    screenshot: bool = Field(True, description="Whether to save screenshots")
    save_html: bool = Field(True, description="Whether to save HTML")
    user_agent: Optional[str] = Field(None, description="Custom user agent")
    timeout: int = Field(30, description="Timeout in seconds")


class RecursiveScrapeRequest(BaseModel):
    """Model for recursive scrape request."""
    url: HttpUrl = Field(..., description="URL to start scraping from")
    max_depth: int = Field(2, ge=1, le=10, description="Maximum depth to crawl")
    max_pages: int = Field(50, ge=1, le=1000, description="Maximum pages to scrape")
    same_domain: bool = Field(True,