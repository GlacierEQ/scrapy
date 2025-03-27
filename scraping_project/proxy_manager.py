import logging
import random
import requests
import time
from typing import List, Dict, Any, Optional, Union
from concurrent.futures import ThreadPoolExecutor
from requests.exceptions import RequestException, ProxyError, Timeout
import os
import json

class ProxyManager:
    """
    Manages and rotates a pool of proxies for web scraping.
    
    Features:
    - Proxy validation and testing
    - Rotation strategies (random, sequential, by country)
    - Proxy health tracking
    - Support for authentication
    """
    
    def __init__(self, proxies: List[str] = None, proxy_file: str = None,
                 test_url: str = "https://httpbin.org/ip", timeout: int = 10):
        """
        Initialize the proxy manager.
        
        Args:
            proxies: List of proxy strings in format "protocol://[user:pass@]host:port"
            proxy_file: Path to a file containing proxy strings (one per line)
            test_url: URL used to test proxy connectivity
            timeout: Timeout for proxy testing in seconds
        """
        self.logger = logging.getLogger(__name__)
        self.test_url = test_url
        self.timeout = timeout
        
        # Proxy pool structure
        self.proxy_pool = []
        self.active_proxies = []
        self.failed_proxies = []
        
        # Proxy rotation state
        self._current_index = 0
        
        # Load proxies
        if proxies:
            self.add_proxies(proxies)
        
        if proxy_file:
            self.load_proxies_from_file(proxy_file)
            
        self.logger.info(f"Initialized proxy manager with {len(self.proxy_pool)} proxies")
    
    def add_proxies(self, proxies: List[str]) -> None:
        """Add proxies to the pool."""
        for proxy in proxies:
            proxy_obj = self._parse_proxy(proxy)
            if proxy_obj:
                self.proxy_pool.append(proxy_obj)
    
    def load_proxies_from_file(self, filepath: str) -> None:
        """Load proxies from a file."""
        try:
            if not os.path.exists(filepath):
                self.logger.warning(f"Proxy file not found: {filepath}")
                return
                
            with open(filepath, 'r') as file:
                lines = file.readlines()
                
            proxies = [line.strip() for line in lines if line.strip()]
            self.add_proxies(proxies)
            self.logger.info(f"Loaded {len(proxies)} proxies from file")
            
        except Exception as e:
            self.logger.error(f"Error loading proxies from file: {e}")
    
    def _parse_proxy(self, proxy_str: str) -> Dict:
        """Parse proxy string and return structured object."""
        try:
            # Basic validation
            if not "://" in proxy_str:
                proxy_str = f"http://{proxy_str}"
            
            parts = proxy_str.split("://")
            protocol = parts[0]
            rest = parts[1]
            
            # Check for authentication
            auth_part = ""
            host_port = rest
            
            if "@" in rest:
                auth_part, host_port = rest.split("@", 1)
            
            # Construct proxy object
            proxy_obj = {
                "url": proxy_str,
                "protocol": protocol,
                "host_port": host_port,
                "auth": auth_part if auth_part else None,
                "last_used": 0,
                "success_count": 0,
                "fail_count": 0,
                "avg_response_time": 0,
                "is_active": True,
                "country": None  # Can be set later if geo-tracking is enabled
            }
            
            return proxy_obj
        except Exception as e:
            self.logger.error(f"Error parsing proxy string {proxy_str}: {e}")
            return None
    
    def test_proxies(self, parallel: bool = True, max_workers: int = 10) -> Dict:
        """
        Test all proxies in the pool and update their status.
        
        Args:
            parallel: If True, test proxies in parallel
            max_workers: Maximum number of parallel workers
        
        Returns:
            Dict with counts of working and failed proxies
        """
        if parallel:
            working, failed = self._test_proxies_parallel(max_workers)
        else:
            working, failed = self._test_proxies_sequential()
        
        self.active_proxies = [p for p in self.proxy_pool if p["is_active"]]
        self.failed_proxies = [p for p in self.proxy_pool if not p["is_active"]]
        
        result = {
            "working": working,
            "failed": failed,
            "total": working + failed
        }
        
        self.logger.info(f"Proxy test results: {result}")
        return result
    
    def _test_proxies_sequential(self) -> tuple:
        """Test proxies one by one."""
        working = 0
        failed = 0
        
        for proxy in self.proxy_pool:
            result = self._test_proxy(proxy)
            if result["success"]:
                working += 1
            else:
                failed += 1
        
        return working, failed
    
    def _test_proxies_parallel(self, max_workers: int) -> tuple:
        """Test proxies in parallel using ThreadPoolExecutor."""
        working = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(self._test_proxy, self.proxy_pool))
            
            for result in results:
                if result["success"]:
                    working += 1
                else:
                    failed += 1
        
        return working, failed
    
    def _test_proxy(self, proxy: Dict) -> Dict:
        """
        Test a single proxy and update its status.
        
        Returns:
            Dict with test results
        """
        start_time = time.time()
        success = False
        error_message = None
        
        try:
            proxies = {
                "http": proxy["url"],
                "https": proxy["url"]
            }
            
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                success = True
                
                # Update proxy stats
                proxy["success_count"] += 1
                
                # Calculate and update average response time
                response_time = time.time() - start_time
                if proxy["avg_response_time"] > 0:
                    # Weighted average (more weight to recent measurements)
                    proxy["avg_response_time"] = (
                        0.7 * response_time + 0.3 * proxy["avg_response_time"]
                    )
                else:
                    proxy["avg_response_time"] = response_time
                    
                # Try to get country info from response
                try:
                    proxy_info = response.json()
                    proxy["country"] = proxy_info.get("country_code")
                except:
                    pass
                
            else:
                error_message = f"Status code: {response.status_code}"
                proxy["fail_count"] += 1
                
        except (ProxyError, Timeout) as e:
            error_message = f"Proxy error: {str(e)}"
            proxy["fail_count"] += 1
        except RequestException as e:
            error_message = f"Request error: {str(e)}"
            