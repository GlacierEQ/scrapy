import os
import time
import re
import logging
import hashlib
import random
import urllib.parse
from datetime import datetime
from typing import List, Dict, Set, Optional, Union, Callable, Pattern, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urldefrag
from collections import deque, defaultdict

from data_analyzer import DataAnalyzer
from proxy_manager import ProxyManager
from config import Config
from .memory_manager import get_memory_manager, MemoryManager
import gc

class RecursiveScraper:
    """
    Advanced recursive scraper with intelligent crawling capabilities.
    
    Features:
    - Multi-level recursion with smart depth control
    - Pattern-based URL filtering and extraction
    - Content similarity detection to avoid duplicate content
    - Rate limiting and politeness features
    - Proxy rotation support
    - Robust error handling and retry logic
    """
    
    def __init__(self, output_dir: str, config: dict = None):
        """
        Initialize the recursive scraper.
        
        Args:
            output_dir: Directory where scraped data will be stored
            config: Optional configuration dictionary to override defaults
        """
        self.output_dir = output_dir
        self.data_analyzer = DataAnalyzer()
        self.logger = logging.getLogger(__name__)
        
        # Load default config
        self.config = {
            # Recursion settings
            'max_depth': 5,                 # Maximum crawl depth
            'max_pages_per_domain': 100,    # Maximum pages to crawl per domain
            'max_total_pages': 1000,        # Maximum total pages to crawl
            
            # Browser settings
            'headless': True,               # Run browser in headless mode
            'browser_width': 1920,          # Browser window width
            'browser_height': 1080,         # Browser window height
            'page_load_timeout': 30,        # Page load timeout in seconds
            'scroll_to_bottom': True,       # Whether to scroll to bottom of page
            
            # Request behavior
            'respect_robots_txt': True,     # Whether to respect robots.txt
            'min_request_interval': 2.0,    # Minimum time between requests (seconds)
            'random_delay': True,           # Add random delay between requests
            'max_retries': 3,               # Maximum retries for failed requests
            
            # URL patterns
            'follow_url_patterns': [],      # Regex patterns for URLs to follow
            'exclude_url_patterns': [],     # Regex patterns for URLs to exclude
            'required_params': [],          # Required URL parameters
            'excluded_params': [],          # URL parameters to exclude
            'strip_url_params': False,      # Whether to strip URL parameters
            
            # Content settings
            'extract_metadata': True,       # Extract page metadata
            'extract_links': True,          # Extract links from pages
            'extract_images': True,         # Extract image information
            'extract_text': True,           # Extract text content
            'min_content_length': 500,      # Minimum content length to consider page valid
            'content_similarity_threshold': 0.85,  # Threshold for duplicate content detection
            
            # Proxy settings
            'use_proxies': False,           # Use proxy rotation
            'proxy_file': None,             # Path to proxy list file
            
            # Domain settings
            'stay_on_domain': True,         # Stay on initial domain
            'allowed_domains': [],          # Additional allowed domains
            'excluded_domains': [],         # Domains to exclude
        }
        
        # Override with supplied config
        if config:
            self.config.update(config)
        
        # Initialize datastructures
        self.visited_urls = set()          # URLs that have been processed
        self.queued_urls = deque()         # URLs waiting to be processed
        self.url_to_depth = {}             # Map of URL to its depth level
        self.url_to_parent = {}            # Map of URL to its parent URL
        self.content_hashes = {}           # Map of URL to content hash
        self.domain_count = defaultdict(int)  # Count of pages per domain
        self.last_request_time = {}        # Last request time per domain
        self.failed_attempts = defaultdict(int)  # Failed attempts per URL
        
        # Compile regex patterns if provided
        self.follow_patterns = self._compile_patterns(self.config['follow_url_patterns'])
        self.exclude_patterns = self._compile_patterns(self.config['exclude_url_patterns'])
        
        # Initialize proxy manager if needed
        self.proxy_manager = None
        if self.config['use_proxies']:
            self.proxy_manager = ProxyManager(proxy_file=self.config['proxy_file'])
        
        # Initialize robots.txt parsers
        self.robots_parsers = {}
        
        # Initialize result data structure
        self.result_data = {
            "pages": [],
            "stats": {
                "start_time": None,
                "end_time": None,
                "duration": None,
                "pages_crawled": 0,
                "pages_failed": 0,
                "total_links_found": 0
            },
            "domains": {},
            "metadata": {}
        }
        
        # Initialize memory management
        self.memory_manager = get_memory_manager()
        
        # Add memory-related config
        memory_config = {
            'chunk_size': 50,             # Number of links to process in a batch
            'offload_large_content': True, # Offload large HTML to disk
            'large_content_threshold': 5 * 1024 * 1024,  # 5 MB
            'enable_memory_monitoring': True,
        }
        
        # Update with supplied config if provided
        if config:
            self.config.update(config)
            if 'memory_config' in config:
                memory_config.update(config['memory_config'])
        
        # Store memory config
        self.memory_config = memory_config
        
        # Start memory monitoring if enabled
        if self.memory_config['enable_memory_monitoring']:
            self.memory_manager.start_monitoring()
    
    def _compile_patterns(self, pattern_list: List[str]) -> List[Pattern]:
        """Compile regex patterns."""
        compiled = []
        for pattern in pattern_list:
            try:
                compiled.append(re.compile(pattern))
            except re.error as e:
                self.logger.error(f"Invalid regex pattern '{pattern}': {e}")
        return compiled
    
    def start_crawl(self, start_url: str) -> Dict:
        """
        Start the crawling process from a given URL.
        
        Args:
            start_url: The URL to start crawling from
            
        Returns:
            Dict containing crawl results and statistics
        """
        self.logger.info(f"Starting crawl from {start_url}")
        self.result_data["stats"]["start_time"] = datetime.now().isoformat()
        
        # Initialize browser
        chrome_options = Options()
        if self.config['headless']:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument(f'--window-size={self.config["browser_width"]},{self.config["browser_height"]}')
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, self.config['page_load_timeout'])
            
            # Create output directories
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_dir = os.path.join(self.output_dir, f"recursive_scrape_{timestamp}")
            os.makedirs(base_dir, exist_ok=True)
            
            # Process the initial URL
            self._add_to_queue(start_url, 0, None)
            
            # Start the crawl loop with memory management
            with self.memory_manager.memory_safe_operation("recursive_crawl"):
                while self.queued_urls and self.result_data["stats"]["pages_crawled"] < self.config['max_total_pages']:
                    # Process URLs in batches to prevent memory issues
                    batch_size = min(self.memory_config['chunk_size'], len(self.queued_urls))
                    batch_urls = []
                    
                    for _ in range(batch_size):
                        if not self.queued_urls:
                            break
                        batch_urls.append(self.queued_urls.popleft())
                    
                    # Process each URL in batch
                    for url in batch_urls:
                        depth = self.url_to_depth[url]
                        self._process_url(driver, wait, url, depth, base_dir)
                        
                    # Check memory between batches
                    memory_usage = self.memory_manager.get_memory_usage()
                    if memory_usage["system_percent"] > 85:  # High memory usage
                        self.logger.warning(f"High memory usage detected: {memory_usage['system_percent']}%")
                        # Force garbage collection between batches if memory usage is high
                        gc.collect()
                        # Reduce batch size dynamically
                        self.memory_config['chunk_size'] = max(5, self.memory_config['chunk_size'] // 2)
                        self.logger.info(f"Reduced batch size to {self.memory_config['chunk_size']} due to high memory usage")
                    elif memory_usage["system_percent"] < 60:  # Low memory usage, can increase batch size
                        self.memory_config['chunk_size'] = min(100, self.memory_config['chunk_size'] * 2)
            
            # Update final statistics
            self.result_data["stats"]["end_time"] = datetime.now().isoformat()
            start_time = datetime.fromisoformat(self.result_data["stats"]["start_time"])
            end_time = datetime.fromisoformat(self.result_data["stats"]["end_time"])
            self.result_data["stats"]["duration"] = (end_time - start_time).total_seconds()
            
            # Generate domain statistics
            for domain, count in self.domain_count.items():
                self.result_data["domains"][domain] = {
                    "pages": count,
                    "percentage": round(count / max(1, self.result_data["stats"]["pages_crawled"]) * 100, 2)
                }
            
            # Generate path tree visualization
            self.result_data["metadata"]["url_tree"] = self._generate_url_tree(start_url)
            
            self.logger.info(f"Crawl completed. Processed {self.result_data['stats']['pages_crawled']} pages.")
            return {
                "status": "success", 
                "message": "Crawl completed successfully", 
                "data": self.result_data
            }
            
        except Exception as e:
            self.logger.error(f"Error during crawl: {str(e)}")
            return {"status": "error", "message": str(e)}
        finally:
            # Stop memory monitoring
            if self.memory_config['enable_memory_monitoring']:
                self.memory_manager.stop_monitoring()
            if driver:
                driver.quit()
    
    def _add_to_queue(self, url: str, depth: int, parent_url: str) -> None:
        """Add a URL to the queue if it meets crawl criteria."""
        # Skip if already visited or queued
        if url in self.visited_urls or url in self.url_to_depth:
            return
        
        # Check depth limit
        if depth > self.config['max_depth']:
            return
        
        # Parse URL and check domain restrictions
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        if self.config['stay_on_domain'] and parent_url:
            parent_domain = urlparse(parent_url).netloc
            if domain != parent_domain and domain not in self.config['allowed_domains']:
                return
                
        if domain in self.config['excluded_domains']:
            return
            
        if self.domain_count[domain] >= self.config['max_pages_per_domain']:
            return
            
        # Apply URL pattern filters
        if self.exclude_patterns and any(pattern.search(url) for pattern in self.exclude_patterns):
            return
            
        if self.follow_patterns and not any(pattern.search(url) for pattern in self.follow_patterns):
            if self.follow_patterns:  # Only filter if patterns were provided
                return
        
        # Process URL parameters if needed
        if self.config['strip_url_params']:
            url = urldefrag(url)[0]
            parsed_url = urlparse(url)
            url = parsed_url._replace(query='').geturl()
        
        # Check for required and excluded parameters
        if self.config['required_params'] or self.config['excluded_params']:
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Check for required parameters
            for param in self.config['required_params']:
                if param not in query_params:
                    return
            
            # Check for excluded parameters
            for param in self.config['excluded_params']:
                if param in query_params:
                    return
        
        # Add URL to queue
        self.queued_urls.append(url)
        self.url_to_depth[url] = depth
        if parent_url:
            self.url_to_parent[url] = parent_url
    
    def _process_url(self, driver: webdriver.Chrome, wait: WebDriverWait, 
                    url: str, depth: int, base_dir: str) -> None:
        """Process a single URL."""
        domain = urlparse(url).netloc
        
        # Check if we need to respect robots.txt
        if self.config['respect_robots_txt'] and not self._is_allowed_by_robots(url):
            self.logger.info(f"Skipping {url} (disallowed by robots.txt)")
            return
        
        # Apply rate limiting
        self._apply_rate_limiting(domain)
        
        # Mark as visited before processing
        self.visited_urls.add(url)
        
        # Create directory for this page
        page_dir = os.path.join(base_dir, f"page_{len(self.result_data['pages']) + 1}")
        os.makedirs(page_dir, exist_ok=True)
        
        # Try to load the page
        retry_count = 0
        while retry_count <= self.config['max_retries']:
            try:
                self.logger.info(f"Processing {url} (depth {depth})")
                
                # Load URL in browser
                driver.get(url)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
                # Scroll to bottom if configured
                if self.config['scroll_to_bottom']:
                    self._scroll_to_bottom(driver)
                
                # Get page content
                html_content = driver.page_source
                
                # Memory-safe HTML content handling
                try:
                    html_content = driver.page_source
                    content_size = len(html_content.encode('utf-8'))
                    
                    # If content is large, consider offloading to disk
                    if content_size > self.memory_config['large_content_threshold'] and self.memory_config['offload_large_content']:
                        self.logger.info(f"Large HTML content detected ({content_size / 1024 / 1024:.2f} MB), offloading to disk")
                        temp_path = self.memory_manager.offload_to_disk(html_content, prefix=f"html_{url.replace('://', '_').replace('/', '_')}")
                        
                        # Save HTML path rather than content
                        html_path = os.path.join(page_dir, "page.html")
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(f"<!-- Content offloaded to {temp_path} due to size -->")
                            
                        # Load content for analysis but don't keep in memory
                        with open(temp_path, 'rb') as f:
                            html_for_analysis = pickle.load(f)
                            
                        # Check for duplicate content
                        content_hash = self._get_content_hash(html_for_analysis)
                        if content_hash in self.content_hashes.values():
                            self.logger.info(f"Skipping {url} (duplicate content)")
                            # Remove temp file if we're not keeping this page
                            self.memory_manager.remove_temp_file(temp_path)
                            return
                        
                        self.content_hashes[url] = content_hash
                        
                        # Save HTML separately
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(html_for_analysis)
                            
                        # Clear the variable
                        html_for_analysis = None
                        gc.collect()  # Prompt garbage collection
                        
                    else:
                        # Regular HTML processing for smaller content
                        html_path = os.path.join(page_dir, "page.html")
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        
                        # Check for duplicate content
                        content_hash = self._get_content_hash(html_content)
                        if content_hash in self.content_hashes.values():
                            self.logger.info(f"Skipping {url} (duplicate content)")
                            return
                        self.content_hashes[url] = content_hash
                    
                    # Save screenshot
                    screenshot_path = os.path.join(page_dir, "screenshot.png")
                    driver.save_screenshot(screenshot_path)
                    
                    # Extract links if configured
                    links = []
                    if self.config['extract_links']:
                        links = self._extract_links(driver, url)
                        self.result_data["stats"]["total_links_found"] += len(links)
                        
                        # Add child URLs to queue
                        for link in links:
                            self._add_to_queue(link["url"], depth + 1, url)
                    
                    # Extract text content
                    text_content = ""
                    if self.config['extract_text']:
                        text_content = driver.find_element(By.TAG_NAME, "body").text
                        
                        # Skip if content is too short
                        if len(text_content) < self.config['min_content_length']:
                            self.logger.info(f"Skipping {url} (content too short)")
                            return
                    
                    # Analyze content
                    analysis = self.data_analyzer.analyze_webpage(html_content)
                    
                    # Save analysis report
                    report_path = os.path.join(page_dir, "analysis.txt")
                    with open(report_path, 'w', encoding='utf-8') as f:
                        f.write(self.data_analyzer.generate_report(analysis))
                    
                    # Add page data to results
                    page_data = {
                        "url": url,
                        "depth": depth,
                        "timestamp": datetime.now().isoformat(),
                        "title": analysis["metadata"]["title"],
                        "screenshot_path": screenshot_path,
                        "html_path": html_path,
                        "report_path": report_path,
                        "links_count": len(links),
                        "word_count": analysis["content_analysis"]["word_count"],
                        "content_hash": content_hash
                    }
                    
                    self.result_data["pages"].append(page_data)
                    self.result_data["stats"]["pages_crawled"] += 1
                    self.domain_count[domain] += 1
                    
                    # Success - no need to retry
                    break
                    
                except MemoryError:
                    self.logger.error(f"Memory error processing {url}, skipping page")
                    # Try to recover
                    gc.collect()
                    return
                except Exception as e:
                    self.logger.error(f"Error processing {url}: {str(e)}")
                    retry_count += 1
                    self.failed_attempts[url] += 1
                    time.sleep(2)  # Wait before retry
            
            except TimeoutException:
                retry_count += 1
                self.failed_attempts[url] += 1
                self.logger.warning(f"Timeout loading {url} (attempt {retry_count}/{self.config['max_retries']})")
                time.sleep(2)  # Wait before retry
        
        if retry_count > self.config['max_retries']:
            self.result_data["stats"]["pages_failed"] += 1
    
    def _apply_rate_limiting(self, domain: str) -> None:
        """Apply rate limiting for politeness."""
        if domain in self.last_request_time:
            last_request = self.last_request_time[domain]
            min_interval = self.config['min_request_interval']
            
            if self.config['random_delay']:
                # Add a random delay of up to 50% of the base interval
                min_interval += min_interval * random.uniform(0, 0.5)
            
            # Calculate time to wait
            elapsed = time.time() - last_request
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        
        # Update last request time
        self.last_request_time[domain] = time.time()
    
    def _scroll_to_bottom(self, driver: webdriver.Chrome) -> None:
        """Scroll page to bottom to load lazy content."""
        try:
            # Get initial height
            last_height = driver.execute_script("return document.body.scrollHeight")
            
            # Scroll down in steps
            for _ in range(3):  # Try a few times to reach bottom
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)  # Wait for content to load
                
                # Calculate new scroll height and compare with last scroll height
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
        except Exception as e:
            self.logger.warning(f"Error scrolling: {str(e)}")
    
    def _extract_links(self, driver: webdriver.Chrome, base_url: str) -> List[Dict]:
        """Extract links from the page."""
        links = []
        
        try:
            for element in driver.find_elements(By.TAG_NAME, "a"):
                href = element.get_attribute("href")
                if href:
                    # Normalize URL
                    href = urljoin(base_url, href)
                    
                    # Skip non-http(s) URLs
                    if not href.startswith(('http://', 'https://')):
                        continue
                    
                    # Add to links
                    links.append({
                        "text": element.text.strip(),
                        "url": href
                    })
        except Exception as e:
            self.logger.error(f"Error extracting links: {str(e)}")
        
        return links
    
    def _get_content_hash(self, content: str) -> str:
        """Generate a hash of page content for duplicate detection."""
        # Use a simpler representation for comparison to avoid minor differences
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        # Get text content
        text = soup.get_text()
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Hash content
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _is_allowed_by_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        from urllib.robotparser import RobotFileParser
        
        parsed = urlparse(url)
        domain = parsed.netloc
        
        if domain not in self.robots_parsers:
            # Create and fetch robots.txt
            rp = RobotFileParser()
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            
            try:
                rp.set_url(robots_url)
                rp.read()
                self.robots_parsers[domain] = rp
            except Exception as e:
                self.logger.warning(f"Error fetching robots.txt for {domain}: {str(e)}")
                # Assume allowed if we can't fetch robots.txt
                return True
        
        # Check if this URL is allowed
        return self.robots_parsers[domain].can_fetch("*", url)
    
    def _generate_url_tree(self, root_url: str) -> Dict:
        """Generate a tree visualization of crawled URLs."""
        tree = {"url": root_url, "children": []}
        
        # Find children of a given URL
        def find_children(parent_url):
            children = []
            for url, parent in self.url_to_parent.items():
                if parent == parent_url:
                    child = {"url": url, "children": find_children(url)}
                    children.append(child)
            return children
        
        tree["children"] = find_children(root_url)
        return tree
