"""
Scrapy API Client Library

A Python client for interacting with the Scrapy API. This library handles
authentication, request formatting, and response parsing to make it easier to
use the Scrapy API in Python applications.
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import uuid
import hashlib
import requests
from urllib.parse import urljoin

# Configure logging
logger = logging.getLogger(__name__)

class ScrapyAPIError(Exception):
    """Base exception class for Scrapy API errors."""
    
    def __init__(self, message: str, code: str = None, status_code: int = None, response: Dict = None):
        """
        Initialize the API error.
        
        Args:
            message: Error message
            code: Error code from API
            status_code: HTTP status code
            response: Full response data
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class AuthenticationError(ScrapyAPIError):
    """Authentication-related errors."""
    pass


class RateLimitError(ScrapyAPIError):
    """Rate limiting errors."""
    pass


class TaskError(ScrapyAPIError):
    """Task operation errors."""
    pass


class ValidationError(ScrapyAPIError):
    """Input validation errors."""
    pass


class ScrapyClient:
    """
    Client for interacting with the Scrapy API.
    
    This client handles authentication, request formatting, and response parsing
    to provide a seamless interface for using the Scrapy API in Python applications.
    """
    
    def __init__(self, 
                 base_url: str = "http://localhost:8000/api",
                 api_key: Optional[str] = None,
                 token: Optional[str] = None,
                 auto_refresh_token: bool = True):
        """
        Initialize the Scrapy API client.
        
        Args:
            base_url: Base URL for the Scrapy API
            api_key: API key for authentication
            token: JWT token for authentication (optional if api_key is provided)
            auto_refresh_token: Whether to automatically refresh the token when expired
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.token = token
        self.auto_refresh_token = auto_refresh_token
        self.token_expires = None
        
        # Initialize session
        self.session = requests.Session()
        
        # If token is provided, parse expiration
        if self.token:
            self._parse_token_expiration()
        # If only API key is provided, get a token
        elif self.api_key:
            self.refresh_token()
    
    def _parse_token_expiration(self):
        """Parse token expiration time."""
        try:
            # JWT tokens consist of three parts: header, payload, signature
            # We need the payload part (second element after splitting by dots)
            payload = self.token.split('.')[1]
            
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            
            # Decode from base64
            import base64
            decoded = base64.b64decode(payload)
            
            # Parse JSON
            payload_data = json.loads(decoded)
            
            # Get expiration time
            if 'exp' in payload_data:
                self.token_expires = payload_data['exp']
            
        except Exception as e:
            logger.warning(f"Failed to parse token expiration: {e}")
            self.token_expires = None
    
    def refresh_token(self):
        """Get or refresh the authentication token."""
        if not self.api_key:
            raise AuthenticationError("API key is required to refresh token")
        
        response = self._request(
            method="POST",
            endpoint="/auth/token",
            data={"api_key": self.api_key},
            auth_required=False
        )
        
        self.token = response['access_token']
        
        # Calculate expiration time
        current_time = time.time()
        expires_in = response.get('expires_in', 3600)  # Default 1 hour
        self.token_expires = current_time + expires_in
        
        return self.token
    
    def _check_token(self):
        """Check if token is still valid and refresh if necessary."""
        # If we don't have a token or expiration info, we need to get one
        if not self.token or not self.token_expires:
            if self.api_key:
                self.refresh_token()
            else:
                raise AuthenticationError("Authentication token is required")
            return
        
        # If token is about to expire (within 60 seconds), refresh it
        if self.auto_refresh_token and time.time() + 60 >= self.token_expires:
            logger.info("Token is about to expire, refreshing...")
            self.refresh_token()
    
    def _request(self, 
                method: str, 
                endpoint: str, 
                data: Optional[Dict] = None,
                params: Optional[Dict] = None,
                auth_required: bool = True,
                files: Optional[Dict] = None,
                stream: bool = False) -> Any:
        """
        Make a request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request data/body
            params: Query parameters
            auth_required: Whether authentication is required
            files: Files to upload
            stream: Whether to stream the response
            
        Returns:
            Response data
            
        Raises:
            ScrapyAPIError: For API errors
            requests.exceptions.RequestException: For network errors
        """
        # Check authentication
        if auth_required:
            self._check_token()
        
        # Build request
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        headers = {}
        
        # Add authentication header if required
        if auth_required and self.token:
            headers['Authorization'] = f"Bearer {self.token}"
        
        # Make request
        try:
            if method == 'GET':
                response = self.session.get(url, params=params, headers=headers, stream=stream)
            elif method == 'POST':
                response = self.session.post(url, json=data, params=params, headers=headers, files=files)
            elif method == 'PUT':
                response = self.session.put(url, json=data, params=params, headers=headers)
            elif method == 'DELETE':
                response = self.session.delete(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle response
            response.raise_for_status()
            
            # Some endpoints might not return JSON
            if response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            else:
                return response
            
        except requests.exceptions.HTTPError as e:
            # Handle API errors
            try:
                error_data = e.response.json()
                error_message = error_data.get('error', str(e))
                error_code = error_data.get('code', 'unknown_error')
                
                if e.response.status_code == 401:
                    raise AuthenticationError(
                        message=error_message,
                        code=error_code,
                        status_code=e.response.status_code,
                        response=error_data
                    )
                elif e.response.status_code == 429:
                    raise RateLimitError(
                        message=error_message,
                        code=error_code,
                        status_code=e.response.status_code,
                        response=error_data
                    )
                elif e.response.status_code == 400:
                    raise ValidationError(
                        message=error_message,
                        code=error_code,
                        status_code=e.response.status_code,
                        response=error_data
                    )
                else:
                    raise ScrapyAPIError(
                        message=error_message,
                        code=error_code,
                        status_code=e.response.status_code,
                        response=error_data
                    )
            except (ValueError, KeyError):
                # Could not parse error response
                raise ScrapyAPIError(
                    message=str(e),
                    status_code=e.response.status_code if hasattr(e, 'response') else None
                )
                
    # API methods for status/health
    
    def get_status(self) -> Dict:
        """
        Get API status information.
        
        Returns:
            Status information
        """
        return self._request(method="GET", endpoint="/status", auth_required=False)
    
    def get_health(self) -> Dict:
        """
        Simple health check.
        
        Returns:
            Health check response
        """
        return self._request(method="GET", endpoint="/health", auth_required=False)
    
    # API methods for authentication
    
    def verify_token(self) -> Dict:
        """
        Verify that the current token is valid.
        
        Returns:
            Verification result
        """
        return self._request(method="GET", endpoint="/auth/verify")
    
    # API methods for scraping
    
    def simple_scrape(self, 
                     url: str,
                     compile_text: bool = True,
                     screenshot: bool = True,
                     save_html: bool = True,
                     user_agent: Optional[str] = None,
                     timeout: int = 30) -> Dict:
        """
        Perform a simple one-page scrape.
        
        Args:
            url: URL to scrape
            compile_text: Whether to compile text analysis
            screenshot: Whether to save screenshots
            save_html: Whether to save HTML
            user_agent: Custom user agent
            timeout: Timeout in seconds
            
        Returns:
            Scraping result
        """
        data = {
            "url": url,
            "compile_text": compile_text,
            "screenshot": screenshot,
            "save_html": save_html
        }
        
        if user_agent:
            data["user_agent"] = user_agent
            
        if timeout:
            data["timeout"] = timeout
        
        return self._request(method="POST", endpoint="/scrape/simple", data=data)
    
    def recursive_scrape(self,
                        url: str,
                        max_depth: int = 2,
                        max_pages: int = 50,
                        same_domain: bool = True,
                        include_patterns: Optional[List[str]] = None,
                        exclude_patterns: Optional[List[str]] = None,
                        async_task: bool = True,
                        **kwargs) -> Dict:
        """
        Perform a recursive scrape, starting from a URL and following links.
        
        Args:
            url: URL to start scraping from
            max_depth: Maximum depth to crawl
            max_pages: Maximum pages to scrape
            same_domain: Whether to stay on the same domain
            include_patterns: URL patterns to include
            exclude_patterns: URL patterns to exclude
            async_task: Whether to run asynchronously
            **kwargs: Additional configuration options
            
        Returns:
            Recursive scraping result or task info
        """
        data = {
            "url": url,
            "max_depth": max_depth,
            "max_pages": max_pages,
            "same_domain": same_domain,
            "async": async_task
        }
        
        if include_patterns:
            data["include_patterns"] = include_patterns
            
        if exclude_patterns:
            data["exclude_patterns"] = exclude_patterns
        
        # Add any other configuration options
        for key, value in kwargs.items():
            data[key] = value
        
        return self._request(method="POST", endpoint="/scrape/recursive", data=data)
    
    def adaptive_scrape(self,
                       url: str,
                       data_type: str = "auto",
                       use_ai: bool = False,
                       async_task: bool = True) -> Dict:
        """
        Perform an adaptive scrape that automatically detects page structure.
        
        Args:
            url: URL to scrape
            data_type: Type of data to extract ('auto', 'product', 'article', 'list', 'table')
            use_ai: Whether to use AI for extraction
            async_task: Whether to run asynchronously
            
        Returns:
            Adaptive scraping result or task info
        """
        data = {
            "url": url,
            "data_type": data_type,
            "use_ai": use_ai,
            "async": async_task
        }
        
        return self._request(method="POST", endpoint="/scrape/adaptive", data=data)
    
    def start_visual_builder(self, url: str, headless: bool = False) -> Dict:
        """
        Start a visual scraper builder session.
        
        Args:
            url: URL to load for scraper building
            headless: Whether to run in headless mode
            
        Returns:
            Session information
        """
        data = {
            "url": url,
            "headless": headless
        }
        
        return self._request(method="POST", endpoint="/visual-builder/start", data=data)
    
    # API methods for task management
    
    def list_tasks(self,
                  status: Optional[str] = None,
                  task_type: Optional[str] = None,
                  limit: int = 20,
                  offset: int = 0) -> Dict:
        """
        List tasks for the current user.
        
        Args:
            status: Filter by status (in_progress, success, error)
            task_type: Filter by job type
            limit: Maximum number of tasks to return
            offset: Pagination offset
            
        Returns:
            List of tasks
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if status:
            params["status"] = status
            
        if task_type:
            params["type"] = task_type
        
        return self._request(method="GET", endpoint="/tasks", params=params)
    
    def get_task(self, task_id: str) -> Dict:
        """
        Get details of a specific task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task details
        """
        return self._request(method="GET", endpoint=f"/tasks/{task_id}")
    
    def cancel_task(self, task_id: str) -> Dict:
        """
        Cancel a running task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            Cancellation result
        """
        return self._request(method="POST", endpoint=f"/tasks/{task_id}/cancel")
    
    def get_results(self, task_id: str) -> Dict:
        """
        Get the results of a completed task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task results
        """
        return self._request(method="GET", endpoint=f"/results/{task_id}")
    
    def download_results(self, 
                        task_id: str, 
                        format_type: str = "json",
                        download_path: Optional[str] = None) -> Union[str, Dict]:
        """
        Download task results in different formats.
        
        Args:
            task_id: ID of the task
            format_type: Format to download ('json', 'csv', 'html')
            download_path: Path to save the downloaded file
            
        Returns:
            Download URL or path to downloaded file
        """
        params = {
            "format": format_type
        }
        
        # Get download URL
        response = self._request(method="GET", endpoint=f"/download/{task_id}", params=params)
        download_url = response.get('download_url')
        
        if not download_url:
            raise ScrapyAPIError("Download URL not found in response")
        
        # If download path is provided, download the file
        if download_path:
            # Use full URL if not already absolute
            if not download_url.startswith(('http://', 'https://')):
                download_url = urljoin(self.base_url, download_url)
            
            # Download the file
            r = self.session.get(download_url, stream=True)
            r.raise_for_status()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(download_path)), exist_ok=True)
            
            # Write to file
            with open(download_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return download_path
        
        return response
    
    # Convenience methods for common workflows
    
    def scrape_and_wait(self, 
                       url: str, 
                       scrape_type: str = "simple", 
                       timeout: int = 300,
                       poll_interval: int = 2,
                       **kwargs) -> Dict:
        """
        Start a scraping operation and wait for it to complete.
        
        Args:
            url: URL to scrape
            scrape_type: Type of scrape ('simple', 'recursive', 'adaptive')
            timeout: Maximum time to wait in seconds
            poll_interval: Seconds between status checks
            **kwargs: Additional options for the scraper
            
        Returns:
            Scraping results
        """
        # Start the scrape
        if scrape_type == 'simple':
            result = self.simple_scrape(url, **kwargs)
        elif scrape_type == 'recursive':
            result = self.recursive_scrape(url, **kwargs)
        elif scrape_type == 'adaptive':
            result = self.adaptive_scrape(url, **kwargs)
        else:
            raise ValueError(f"Unsupported scrape type: {scrape_type}")
        
        # If synchronous, return results directly
        if result.get('status') in ('success', 'error'):
            return result
        
        # If asynchronous, wait for completion
        task_id = result.get('task_id')
        if not task_id:
            raise ScrapyAPIError("Task ID not found in response")
        
        # Wait for task to complete
        start_time = time.time()
        while time.time() - start_time < timeout:
            task = self.get_task(task_id)
            status = task.get('status')
            
            if status in ('success', 'error', 'cancelled'):
                # Get results
                if status == 'success':
                    return self.get_results(task_id)
                else:
                    return task
            
            # Wait before checking again
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
    
    def extract_from_multiple_pages(self,
                                   urls: List[str],
                                   scrape_type: str = "adaptive",
                                   parallel: bool = True,
                                   **kwargs) -> List[Dict]:
        """
        Extract data from multiple pages.
        
        Args:
            urls: List of URLs to scrape
            scrape_type: Type of scrape for each URL
            parallel: Whether to scrape in parallel
            **kwargs: Additional options for the scraper
            
        Returns:
            List of scraping results
        """
        results = []
        tasks = []
        
        # Start tasks
        for url in urls:
            if scrape_type == 'simple':
                result = self.simple_scrape(url, **kwargs)
            elif scrape_type == 'recursive':
                result = self.recursive_scrape(url, **kwargs)
            elif scrape_type == 'adaptive':
                result = self.adaptive_scrape(url, **kwargs)
            else:
                raise ValueError(f"Unsupported scrape type: {scrape_type}")
            
            # If synchronous, add to results directly
            if result.get('status') in ('success', 'error'):
                results.append(result)
            else:
                # If asynchronous, track the task
                task_id = result.get('task_id')
                if not task_id:
                    raise ScrapyAPIError("Task ID not found in response")
                
                tasks.append({
                    'task_id': task_id,
                    'url': url
                })
                
                # If not parallel, wait for completion before starting next
                if not parallel:
                    task_result = self.scrape_and_wait(url, scrape_type, **kwargs)
                    results.append(task_result)
                    tasks.pop()  # Remove from tasks since we already have the result
        
        # Wait for remaining tasks if parallel
        if parallel and tasks:
            for task in tasks:
                task_result = None
                try:
                    task_result = self.scrape_and_wait(task['url'], scrape_type, **kwargs)
                except Exception as e:
                    logger.error(f"Error waiting for task {task['task_id']}: {e}")
                    task_result = {
                        'status': 'error',
                        'error': str(e),
                        'task_id': task['task_id'],
                        'url': task['url']
                    }
                
                results.append(task_result)
        
        return results
