"""
Adaptive scraping system that automatically detects website structure and extracts data.

This module provides an intelligent scraper that can:
1. Automatically identify important data structures on websites
2. Extract structured data without predefined selectors
3. Learn from examples and adapt to similar websites
4. Handle different website layouts and changes
"""

import os
import re
import logging
import json
import time
import hashlib
import random
from typing import Dict, List, Any, Optional, Set, Union, Tuple
from datetime import datetime
from collections import Counter, defaultdict

import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .memory_manager import get_memory_manager
from .error_handler import error_context, retry
from .resilient_browser import ResilientBrowser
from .ai_analyzer import AIContentAnalyzer

# Import optional machine learning dependencies
try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import DBSCAN
    from sklearn.metrics.pairwise import cosine_similarity
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

logger = logging.getLogger(__name__)
memory_manager = get_memory_manager()

class AdaptiveScraper:
    """
    Intelligent scraper that automatically adapts to website structures.
    
    Features:
    - Automatic detection of data structures (lists, tables, etc.)
    - Content pattern recognition and extraction
    - Learning from examples to improve extraction
    - Handling pagination and dynamic content
    """
    
    def __init__(self, output_dir: str, use_ai: bool = False):
        """
        Initialize the adaptive scraper.
        
        Args:
            output_dir: Directory to store output files
            use_ai: Whether to use AI capabilities for advanced content analysis
        """
        self.output_dir = output_dir
        self.use_ai = use_ai
        os.makedirs(output_dir, exist_ok=True)
        
        # Browser for interactive scraping
        self.browser = ResilientBrowser(headless=True)
        
        # Optional AI analyzer
        self.ai_analyzer = AIContentAnalyzer() if use_ai else None
        
        # Extraction patterns learned from examples
        self.extraction_patterns = {}
        
        # Cache for page structures
        self.structure_cache = {}
        
        logger.info("Adaptive Scraper initialized")
    
    def extract_data(self, url: str, data_type: str = None, examples: List[Dict] = None) -> Dict[str, Any]:
        """
        Extract structured data from a URL.
        
        Args:
            url: URL to scrape
            data_type: Type of data to extract (e.g., 'product', 'article', 'list')
            examples: Example data items to learn from
            
        Returns:
            Dictionary with extracted data
        """
        try:
            self.browser.start()
            
            # Load the page
            self.browser.get(url)
            
            # Wait for page to load completely
            WebDriverWait(self.browser.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            html = self.browser.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Take a screenshot for reference
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = os.path.join(self.output_dir, f"{timestamp}_screenshot.png")
            self.browser.driver.save_screenshot(screenshot_path)
            
            # Extract data based on the requested type
            if data_type == 'list':
                data = self._extract_list_items(soup, examples)
            elif data_type == 'product':
                data = self._extract_product_data(soup, examples)
            elif data_type == 'article':
                data = self._extract_article_content(soup, examples)
            elif data_type == 'table':
                data = self._extract_table_data(soup, examples)
            else:
                # Auto-detect the most likely data structure
                data = self._auto_detect_and_extract(soup, url)
            
            # Apply AI analysis if enabled
            if self.use_ai and self.ai_analyzer and data:
                self._enhance_with_ai(data)
            
            # Save the extraction results
            result_path = os.path.join(self.output_dir, f"{timestamp}_extraction.json")
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'url': url,
                    'data_type': data_type or 'auto',
                    'extraction_time': datetime.now().isoformat(),
                    'data': data
                }, f, indent=2, ensure_ascii=False)
            
            return {
                'status': 'success',
                'url': url,
                'data_type': data_type or 'auto',
                'item_count': len(data) if isinstance(data, list) else 1,
                'data': data,
                'screenshot_path': screenshot_path,
                'result_path': result_path
            }
            
        except Exception as e:
            logger.error(f"Extraction error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'url': url
            }
        finally:
            self.browser.close()
    
    def learn_from_example(self, url: str, target_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Learn extraction patterns from an example URL and known data.
        
        Args:
            url: Example URL to learn from
            target_data: The expected data extraction result
            
        Returns:
            Dictionary with learning results
        """
        try:
            self.browser.start()
            
            # Load the page
            self.browser.get(url)
            html = self.browser.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Analyze the page structure
            page_structure = self._analyze_page_structure(soup)
            
            # Find patterns that match the target data
            patterns = self._discover_patterns(soup, target_data)
            
            if patterns:
                # Store the patterns for future use
                pattern_id = hashlib.md5(url.encode()).hexdigest()
                self.extraction_patterns[pattern_id] = {
                    'url': url,
                    'patterns': patterns,
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"Learned {len(patterns)} extraction patterns from {url}")
                return {
                    'status': 'success',
                    'pattern_id': pattern_id,
                    'pattern_count': len(patterns),
                    'patterns': patterns
                }
            else:
                logger.warning(f"Could not discover patterns from {url}")
                return {
                    'status': 'error',
                    'message': 'No patterns discovered',
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"Learning error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'url': url
            }
        finally:
            self.browser.close()
    
    def extract_similar(self, url: str, pattern_id: str) -> Dict[str, Any]:
        """
        Extract data from a new URL using previously learned patterns.
        
        Args:
            url: URL to extract data from
            pattern_id: ID of the pattern to use
            
        Returns:
            Dictionary with extracted data
        """
        if pattern_id not in self.extraction_patterns:
            return {'status': 'error', 'message': 'Pattern ID not found'}
            
        patterns = self.extraction_patterns[pattern_id]['patterns']
        
        try:
            self.browser.start()
            
            # Load the page
            self.browser.get(url)
            html = self.browser.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Apply the learned patterns
            data = self._apply_patterns(soup, patterns)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_path = os.path.join(self.output_dir, f"{timestamp}_similar_extraction.json")
            
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'url': url,
                    'pattern_id': pattern_id,
                    'extraction_time': datetime.now().isoformat(),
                    'data': data
                }, f, indent=2, ensure_ascii=False)
            
            return {
                'status': 'success',
                'url': url,
                'item_count': len(data) if isinstance(data, list) else 1,
                'data': data,
                'result_path': result_path
            }
            
        except Exception as e:
            logger.error(f"Similar extraction error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'url': url
            }
        finally:
            self.browser.close()
    
    def handle_pagination(self, base_url: str, data_type: str = None, max_pages: int = 5) -> Dict[str, Any]:
        """
        Handle pagination and extract data from multiple pages.
        
        Args:
            base_url: Starting URL for pagination
            data_type: Type of data to extract
            max_pages: Maximum number of pages to process
            
        Returns:
            Dictionary with combined data from all pages
        """
        all_data = []
        current_url = base_url
        page_count = 0
        
        try:
            self.browser.start()
            
            while current_url and page_count < max_pages:
                logger.info(f"Processing page {page_count + 1}: {current_url}")
                
                # Load the page
                self.browser.get(current_url)
                html = self.browser.driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract data from the current page
                if data_type == 'list':
                    data = self._extract_list_items(soup, None)
                elif data_type == 'product':
                    data = self._extract_product_data(soup, None)
                elif data_type == 'article':
                    data = self._extract_article_content(soup, None)
                elif data_type == 'table':
                    data = self._extract_table_data(soup, None)
                else:
                    data = self._auto_detect_and_extract(soup, current_url)
                
                # Add the extracted data to our collection
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)
                
                # Find the next page link
                next_url = self._find_next_page_link(soup, current_url)
                
                if next_url == current_url:
                    # We're stuck in a loop
                    break
                    
                current_url = next_url
                page_count += 1
                
                # Add a small delay between pages
                time.sleep(random.uniform(1.0, 2.0))
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_path = os.path.join(self.output_dir, f"{timestamp}_paginated_extraction.json")
            
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'base_url': base_url,
                    'pages_processed': page_count,
                    'extraction_time': datetime.now().isoformat(),
                    'data': all_data
                }, f, indent=2, ensure_ascii=False)
            
            return {
                'status': 'success',
                'base_url': base_url,
                'pages_processed': page_count,
                'item_count': len(all_data),
                'data': all_data,
                'result_path': result_path
            }
            
        except Exception as e:
            logger.error(f"Pagination error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'base_url': base_url,
                'pages_processed': page_count,
                'partial_data': all_data if all_data else None
            }
        finally:
            self.browser.close()
    
    def save_extraction_patterns(self, filepath: str) -> bool:
        """Save learned extraction patterns to a file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.extraction_patterns, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving extraction patterns: {str(e)}")
            return False
    
    def load_extraction_patterns(self, filepath: str) -> bool:
        """Load extraction patterns from a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                patterns = json.load(f)
                self.extraction_patterns.update(patterns)
            return True
        except Exception as e:
            logger.error(f"Error loading extraction patterns: {str(e)}")
            return False
    
    def _auto_detect_and_extract(self, soup: BeautifulSoup, url: str) -> Union[List[Dict], Dict]:
        """
        Automatically detect the type of data on the page and extract it.
        
        Args:
            soup: BeautifulSoup object of the page
            url: URL of the page
            
        Returns:
            Extracted data as a list of dictionaries or a single dictionary
        """
        # Check for common page types
        if self._is_product_page(soup):
            logger.info("Detected product page")
            return self._extract_product_data(soup, None)
            
        elif self._is_article_page(soup):
            logger.info("Detected article page")
            return self._extract_article_content(soup, None)
            
        elif self._is_listing_page(soup):
            logger.info("Detected listing page")
            return self._extract_list_items(soup, None)
            
        elif self._is_table_page(soup):
            logger.info("Detected table page")
            return self._extract_table_data(soup, None)
            
        else:
            # Generic extraction as fallback
            logger.info("No specific page type detected, using generic extraction")
            return self._extract_generic_data(soup)
    
    def _extract_list_items(self, soup: BeautifulSoup, examples: List[Dict] = None) -> List[Dict]:
        """
        Extract list items from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            examples: Example list items to learn from
            
        Returns:
            List of extracted items
        """
        items = []
        
        # If we have examples, try to learn from them
        if examples and len(examples) > 0:
            patterns = self._discover_list_patterns(soup, examples)
            if patterns:
                return self._apply_list_patterns(soup, patterns)
        
        # Otherwise use heuristics to find lists
        potential_lists = []
        
        # Look for common list containers
        for container_tag in ['ul', 'ol', 'div', 'section']:
            containers = soup.find_all(container_tag)
            
            for container in containers:
                # Get direct children that could be list items
                if container_tag in ['ul', 'ol']:
                    children = container.find_all('li', recursive=False)
                else:
                    # For div/section, look for repeated elements with same class
                    child_classes = [c.get('class', []) for c in container.children if isinstance(c, Tag)]
                    flat_classes = [c for sublist in child_classes for c in sublist if c]
                    
                    if not flat_classes:
                        continue
                        
                    # Count occurrences of each class
                    class_counts = Counter(flat_classes)
                    common_classes = [c for c, count in class_counts.items() if count >= 3]
                    
                    if not common_classes:
                        continue
                    
                    # Find children with the most common class
                    most_common_class = max(class_counts.items(), key=lambda x: x[1])[0]
                    children = container.find_all(attrs={"class": most_common_class})
                
                # If we have enough similar children, treat as a list
                if len(children) >= 3:
                    potential_lists.append((container, children))
        
        # Sort potential lists by number of items (prefer larger lists)
        potential_lists.sort(key=lambda x: len(x[1]), reverse=True)
        
        if not potential_lists:
            return []
            
        # Take the most promising list
        container, list_items = potential_lists[0]
        
        # Process each list item
        for item in list_items:
            item_data = {}
            
            # Extract title/heading
            heading = item.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
            if heading:
                item_data['title'] = heading.get_text(strip=True)
            
            # Extract links
            links = item.find_all('a')
            if links:
                item_data['links'] = [{
                    'text': a.get_text(strip=True),
                    'href': a.get('href')
                } for a in links]
            
            # Extract images
            images = item.find_all('img')
            if images:
                item_data['images'] = [{
                    'alt': img.get('alt', ''),
                    'src': img.get('src')
                } for img in images]
            
            # Extract paragraphs
            paragraphs = item.find_all('p')
            if paragraphs:
                item_data['text'] = ' '.join([p.get_text(strip=True) for p in paragraphs])
            elif not item_data.get('title') and not item_data.get('links'):
                # If no specific data found, use the full text
                item_data['text'] = item.get_text(strip=True)
            
            # Add the item if we extracted any data
            if item_data:
                items.append(item_data)
        
        return items
    
    def _extract_product_data(self, soup: BeautifulSoup, examples: List[Dict] = None) -> Dict[str, Any]:
        """
        Extract product data from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            examples: Example product data to learn from
            
        Returns:
            Dictionary with product information
        """
        product = {}
        
        # If we have examples, try to learn from them
        if examples and len(examples) > 0:
            patterns = self._discover_product_patterns(soup, examples[0])
            if patterns:
                return self._apply_product_patterns(soup, patterns)
        
        # Title - look for common product title patterns
        title_candidates = []
        
        # Look in logical places for the title
        title_candidates.extend(soup.find_all(['h1', 'h2']))
        title_candidates.extend(soup.find_all(class_=lambda c: c and any(x in c for x in [
            'product-title', 'product-name', 'title', 'product_title', 'productName'
        ])))
        
        for candidate in title_candidates:
            text = candidate.get_text(strip=True)
            if text and len(text) < 200:  # Reasonable title length
                product['title'] = text
                break
        
        # Price - look for price patterns
        price_candidates = []
        price_candidates.extend(soup.find_all(class_=lambda c: c and any(x in c for x in [
            'price', 'product-price', 'productPrice', 'offer-price'
        ])))
        
        # Look for price patterns with regex
        price_regex = re.compile(r'(\$|€|£|USD|EUR|GBP)?(\s)?\d+(\.\d{2})?')
        for candidate in price_candidates:
            text = candidate.get_text(strip=True)
            if price_regex.search(text):
                product['price'] = text
                break
        
        # Description
        desc_candidates = []
        desc_candidates.extend(soup.find_all(class_=lambda c: c and any(x in c for x in [
            'description', 'product-description', 'productDescription', 'product-info'
        ])))
        
        for candidate in desc_candidates:
            text = candidate.get_text(strip=True)
            if text and len(text) > 20:  # Reasonable description length
                product['description'] = text
                break
        
        # Images
        image_containers = soup.find_all(class_=lambda c: c and any(x in c for x in [
            'product-image', 'product-img', 'productImage', 'gallery'
        ]))
        
        product_images = []
        
        # First check in likely image containers
        for container in image_containers:
            images = container.find_all('img')
            if images:
                for img in images:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        product_images.append({
                            'src': src,
                            'alt': img.get('alt', '')
                        })
        
        # If we didn't find images in containers, look for any prominent images
        if not product_images:
            # Filter for reasonably sized images
            main_images = [img for img in soup.find_all('img') if 
                          img.get('width') and int(img.get('width', '0')) > 200]
            
            for img in main_images[:3]:  # Limit to first 3 large images
                src = img.get('src') or img.get('data-src')
                if src:
                    product_images.append({
                        'src': src,
                        'alt': img.get('alt', '')
                    })
        
        if product_images:
            product['images'] = product_images
        
        # Features/Specifications
        spec_containers = soup.find_all(class_=lambda c: c and any(x in c for x in [
            'specifications', 'specs', 'features', 'product-specs', 'product-details'
        ]))
        
        specs = {}
        
        for container in spec_containers:
            # Look for definition lists
            dl = container.find('dl')
            if dl:
                dts = dl.find_all('dt')
                dds = dl.find_all('dd')
                for i in range(min(len(dts), len(dds))):
                    key = dts[i].get_text(strip=True)
                    value = dds[i].get_text(strip=True)
                    if key and value:
                        specs[key] = value
            
            # Look for tables
            table = container.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value:
                            specs[key] = value
        
        if specs:
            product['specifications'] = specs
        
        return product
    
    def _extract_article_content(self, soup: BeautifulSoup, examples: List[Dict] = None) -> Dict[str, Any]:
        """
        Extract article content from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            examples: Example article data to learn from
            
        Returns:
            Dictionary with article content
        """
        article = {}
        
        # If we have examples, try to learn from them
        if examples and len(examples) > 0:
            patterns = self._discover_article_patterns(soup, examples[0])
            if patterns:
                return self._apply_article_patterns(soup, patterns)
        
        # Title - usually the main heading
        title_tag = soup.find('h1')
        if title_tag:
            article['title'] = title_tag.get_text(strip=True)
        
        # Author
        author_candidates = []
        author_candidates.extend(soup.find_all(class_=lambda c: c and any(x in c for x in [
            'author', 'byline', 'writer', 'contributor'
        ])))
        
        for candidate in author_candidates:
            text = candidate.get_text(strip=True)
            if text and len(text) < 100:  # Reasonable author name/bio length
                article['author'] = text
                break
        
        # Date
        date_candidates = []
        date_candidates.extend(soup.find_all(class_=lambda c: c and any(x in c for x in [
            'date', 'time', 'published', 'pubdate', 'timestamp'
        ])))
        
        for candidate in date_candidates:
            text = candidate.get_text(strip=True)
            if text:
                article['date'] = text
                break
        
        # Main content
        content_candidates = []
        content_candidates.extend(soup.find_all(class_=lambda c: c and any(x in c for x in [
            'content', 'article', 'post', 'entry', 'story', 'text'
        ])))
        
        # Also look for article tag
        article_tag = soup.find('article')
        if article_tag:
            content_candidates.append(article_tag)
        
        # Process the most likely content container
        content_container = None
        max_paragraphs = 0
        
        for candidate in content_candidates:
            paragraphs = candidate.find_all('p')
            if len(paragraphs) > max_paragraphs:
                content_container = candidate
                max_paragraphs = len(paragraphs)
        
        # Extract content by paragraphs
        if content_container:
            paragraphs = content_container.find_all('p')
            article['content'] = [p.get_text(strip=True) for p in paragraphs]
            
            # Extract subheadings within the content
            subheadings = content_container.find_all(['h2', 'h3', 'h4'])
            if subheadings:
                article['subheadings'] = [h.get_text(strip=True) for h in subheadings]
            
            # Extract images within the content
            images = content_container.find_all('img')
            if images:
                article['images'] = [{
                    'src': img.get('src'),
                    'alt': img.get('alt', '')
                } for img in images if img.get('src')]
        
        return article
    
    def _extract_table_data(self, soup: BeautifulSoup, examples: List[Dict] = None) -> List[Dict]:
        """
        Extract data from tables on the page.
        
        Args:
            soup: BeautifulSoup object of the page
            examples: Example table data to learn from
            
        Returns:
            List of dictionaries with table data
        """
        tables = soup.find_all('table')
        if not tables:
            return []
        
        all_table_data = []
        
        for table in tables:
            headers = []
            header_row = table.find('thead')
            if header_row:
                header_cells = header_row.find_all('th')
                if not header_cells:
                    header_cells = header_row.find_all('td')
                headers = [cell.get_text(strip=True) for cell in header_cells]
            
            # If no headers in thead, check first row
            if not headers:
                first_row = table.find('tr')
                if first_row:
                    header_cells = first_row.find_all('th')
                    if not header_cells:
                        header_cells = first_row.find_all('td')
                    headers = [cell.get_text(strip=True) for cell in header_cells]
            
            # Process data rows
            data_rows = table.find_all('tr')
            if header_row and len(data_rows) > 0:
                # Skip header row if we already processed it
                data_rows = data_rows[1:]
            
            table_data = []
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                
                if headers and len(cells) <= len(headers):
                    # Create a dictionary mapping headers to cell values
                    row_data = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            row_data[headers[i]] = cell.get_text(strip=True)
                    table_data.append(row_data)
                else:
                    # No headers or mismatched cells, use indices
                    row_data = {f"col_{i}": cell.get_text(strip=True) 
                               for i, cell in enumerate(cells)}
                    table_data.append(row_data)
            
            all_table_data.extend(table_data)
        
        return all_table_data
    
    def _extract_generic_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract generic data when no specific structure is detected."""
        data = {}
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            data['page_title'] = title_tag.get_text(strip=True)
            
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            data['meta_description'] = meta_desc.get('content', '')
            
        # Extract headings
        headings = {}
        for i in range(1, 7):
            h_tags = soup.find_all(f'h{i}')
            if h_tags:
                headings[f'h{i}'] = [h.get_text(strip=True) for h in h_tags]
        
        if headings:
            data['headings'] = headings
            
        # Extract links
        links = []
        for a in soup.find_all('a', href=True):
            link_text = a.get_text(strip=True)
            if link_text:  # Only include links with text
                links.append({
                    'text': link_text,
                    'href': a['href']
                })
        
        if links:
            data['links'] = links
            
        # Extract images
        images = []
        for img in soup.find_all('img', src=True):
            images.append({
                'src': img['src'],
                'alt': img.get('alt', '')
            })
            
        if images:
            data['images'] = images
            
        # Extract text paragraphs
        paragraphs = []
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text and len(text) > 20:  # Skip very short paragraphs
                paragraphs.append(text)
                
        if paragraphs:
            data['paragraphs'] = paragraphs
            
        return data
    
    def _is_product_page(self, soup: BeautifulSoup) -> bool:
        """
        Determine if the page is a product page based on heuristics.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            True if the page appears to be a product page
        """
        # Check for product indicators
        product_indicators = [
            # Check for common product page elements
            soup.find(class_=lambda c: c and any(x in str(c).lower() for x in [
                'product', 'item', 'price', 'buy', 'add-to-cart', 'purchase',
                'shop-item', 'product-detail', 'pdp', 'sku', 'stock'
            ])),
            
            # Check for price patterns
            bool(re.search(r'(\$|€|£|USD|EUR|GBP)?\s?\d+(\.\d{2})?', soup.get_text())),
            
            # Check for common product page button text
            bool(soup.find('button', text=re.compile(r'add to (cart|bag|basket)', re.I))),
            
            # Check for review sections
            bool(soup.find(class_=lambda c: c and any(x in str(c).lower() for x in [
                'review', 'rating', 'stars'
            ]))),
        ]
        
        # If at least 2 indicators are present, consider it a product page
        return sum(bool(i) for i in product_indicators) >= 2
    
    def _is_article_page(self, soup: BeautifulSoup) -> bool:
        """
        Determine if the page is an article based on heuristics.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            True if the page appears to be an article
        """
        # Check for article indicators
        article_indicators = [
            # Look for article tag
            bool(soup.find('article')),
            
            # Check for typical article classes
            bool(soup.find(class_=lambda c: c and any(x in str(c).lower() for x in [
                'article', 'post', 'blog', 'news', 'story', 'entry'
            ]))),
            
            # Check if there's a single h1 and multiple paragraphs
            bool(soup.find('h1') and len(soup.find_all('p')) > 5),
            
            # Check for author byline
            bool(soup.find(class_=lambda c: c and any(x in str(c).lower() for x in [
                'author', 'byline', 'writer', 'contributor'
            ]))),
            
            # Check for publication date
            bool(soup.find(class_=lambda c: c and any(x in str(c).lower() for x in [
                'date', 'time', 'published', 'pubdate', 'timestamp'
            ]))),
        ]
        
        # If at least 3 indicators are present, consider it an article
        return sum(bool(i) for i in article_indicators) >= 3
    
    def _is_listing_page(self, soup: BeautifulSoup) -> bool:
        """
        Determine if the page contains a list of items.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            True if the page appears to be a listing page
        """
        # Check for list indicators
        list_indicators = [
            # Check for HTML list elements with multiple items
            bool(soup.find('ul') and len(soup.find('ul', recursive=False).find_all('li', recursive=False)) >= 3),
            bool(soup.find('ol') and len(soup.find('ol', recursive=False).find_all('li', recursive=False)) >= 3),
            
            # Check for grid/list layout classes
            bool(soup.find(class_=lambda c: c and any(x in str(c).lower() for x in [
                'list', 'grid', 'catalog', 'results', 'search-results', 'listing'
            ]))),
            
            # Check for repeated elements with similar structure
            any(len(soup.find_all(class_=cls)) >= 3 for cls in 
                set(cls for tag in soup.find_all(class_=True) for cls in tag.get('class', []))),
            
            # Check for pagination
            bool(soup.find(class_=lambda c: c and any(x in str(c).lower() for x in [
                'pagination', 'pager', 'pages'
            ]))),
        ]
        
        # If at least 2 indicators are present, consider it a listing page
        return sum(bool(i) for i in list_indicators) >= 2
    
    def _is_table_page(self, soup: BeautifulSoup) -> bool:
        """
        Determine if the page contains significant table data.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            True if the page contains substantial table data
        """
        tables = soup.find_all('table')
        
        if not tables:
            return False
            
        # Check if there's at least one table with significant data
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) >= 3:  # At least a header and two data rows
                cells_in_first_row = len(rows[0].find_all(['th', 'td']))
                if cells_in_first_row >= 2:  # At least two columns
                    return True
                    
        return False
    
    def _find_next_page_link(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """
        Find the link to the next page.
        
        Args:
            soup: BeautifulSoup object of the page
            current_url: URL of the current page
            
        Returns:
            URL of the next page or None if not found
        """
        from urllib.parse import urljoin
        
        # Look for common next page indicators
        next_link = None
        
        # Method 1: Look for "next" link text
        for text in ['next', 'next page', 'next »', '»', '>', 'continue', 'more']:
            links = soup.find_all('a', text=re.compile(text, re.I))
            if links:
                next_link = links[0].get('href')
                break
        
        # Method 2: Look for common next page classes/IDs
        if not next_link:
            next_candidates = soup.find_all(['a', 'link'], attrs={
                'class': lambda c: c and any(x in str(c).lower() for x in [
                    'next', 'pagination-next', 'next-page', 'nextpage'
                ]),
                'id': lambda i: i and 'next' in i.lower(),
                'rel': 'next'
            })
            
            if next_candidates:
                next_link = next_candidates[0].get('href')
        
        # Method 3: Look in pagination for the current number + 1
        if not next_link:
            # Try to extract current page number from URL
            match = re.search(r'[?&]page=(\d+)', current_url)
            if match:
                current_page = int(match.group(1))
                next_page = current_page + 1
                next_url = re.sub(r'([?&]page=)(\d+)', f'\\1{next_page}', current_url)
                return next_url
        
        # Make the URL absolute if it's relative
        if next_link:
            return urljoin(current_url, next_link)
            
        return None
    
    def _analyze_page_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Analyze the page structure to identify common patterns.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Dictionary with page structure analysis
        """
        structure = {
            'elements': {},
            'classes': {},
            'semantic_structure': [],
            'depth': 0
        }
        
        # Count element types
        for tag in soup.find_all(True):
            tag_name = tag.name
            if tag_name not in structure['elements']:
                structure['elements'][tag_name] = 0
            structure['elements'][tag_name] += 1
            
            # Count classes
            for cls in tag.get('class', []):
                if cls not in structure['classes']:
                    structure['classes'][cls] = 0
                structure['classes'][cls] += 1
        
        # Analyze semantic structure
        body = soup.find('body')
        if body:
            structure['semantic_structure'] = self._get_semantic_path(body)
            structure['depth'] = self._get_max_depth(body)
            
        # Identify major content sections
        main_content = soup.find('main') or soup.find(id='main') or soup.find(class_='main')
        if main_content:
            structure['main_content_path'] = self._get_css_path(main_content)
            
        return structure
    
    def _discover_patterns(self, soup: BeautifulSoup, target_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discover patterns for extracting the target data from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            target_data: The expected data for extraction
            
        Returns:
            List of discovered patterns
        """
        patterns = []
        
        # Determine the data type
        if isinstance(target_data, list) and target_data:
            # It's a list of items (e.g., search results, product listings)
            return self._discover_list_patterns(soup, target_data)
            
        # Otherwise it's a single item
        if 'title' in target_data and 'price' in target_data:
            # Likely a product
            return self._discover_product_patterns(soup, target_data)
            
        elif 'title' in target_data and ('content' in target_data or 'text' in target_data):
            # Likely an article
            return self._discover_article_patterns(soup, target_data)
            
        # Generic pattern discovery for other data types
        for field, value in target_data.items():
            if not isinstance(value, str):
                continue
                
            # Try to find elements containing this exact text
            elements = []
            for element in soup.find_all(text=lambda t: value in t):
                parent = element.parent
                elements.append((parent, self._get_css_path(parent)))
                
            # If found, create a pattern for this field
            if elements:
                best_element, path = max(elements, key=lambda e: len(e[0].get_text(strip=True)))
                patterns.append({
                    'field': field,
                    'selector': path,
                    'attribute': 'text',
                    'manipulation': None
                })
                
        return patterns
    
    def _discover_list_patterns(self, soup: BeautifulSoup, examples: List[Dict]) -> List[Dict[str, Any]]:
        """
        Discover patterns for extracting list items.
        
        Args:
            soup: BeautifulSoup object of the page
            examples: List of example items
            
        Returns:
            List of patterns for extracting list items
        """
        # First, try to find a container for list items
        potential_containers = []
        
        # Look for lists with multiple items
        for container_tag in ['ul', 'ol', 'div', 'section']:
            containers = soup.find_all(container_tag)
            for container in containers:
                # For ul/ol, look for li children
                if container_tag in ['ul', 'ol']:
                    items = container.find_all('li', recursive=False)
                else:
                    # For div/section, look for elements with the same class
                    children = [c for c in container.children if isinstance(c, Tag)]
                    
                    # Skip if too few children
                    if len(children) < 3:
                        continue
                        
                    # Group by tag name
                    tag_counts = Counter(child.name for child in children)
                    most_common_tag, count = tag_counts.most_common(1)[0]
                    
                    # If there are several elements of the same type, they might be list items
                    if count >= 3:
                        items = container.find_all(most_common_tag, recursive=False)
                    else:
                        continue
                
                if len(items) >= 3:
                    potential_containers.append((container, items))
        
        # No potential containers found
        if not potential_containers:
            return []
            
        # For each potential container, try to match its items with the example data
        best_container = None
        best_items = None
        best_score = 0
        
        for container, items in potential_containers:
            # Check if number of items is similar
            if abs(len(items) - len(examples)) > min(len(items), len(examples)) * 0.5:
                continue
                
            # Calculate a similarity score based on text content
            score = 0
            for i, example in enumerate(examples):
                if i >= len(items):
                    break
                    
                item_text = items[i].get_text(strip=True)
                example_text = ' '.join(str(v) for v in example.values() if isinstance(v, str))
                
                # Simple similarity: check if example text appears in item text
                if example_text and example_text in item_text:
                    score += 1
                    
            if score > best_score:
                best_container = container
                best_items = items
                best_score = score
        
        # If we found a good match, generate patterns
        if best_container and best_score >= 1:
            container_path = self._get_css_path(best_container)
            item_tag = best_items[0].name
            
            # Create patterns for each field in the examples
            patterns = []
            base_pattern = {
                'container': container_path,
                'item_selector': f'{item_tag}',
                'fields': []
            }
            
            # For each field in the examples, try to find matching elements
            first_example = examples[0]
            first_item = best_items[0]
            
            for field, value in first_example.items():
                if not isinstance(value, str):
                    continue
                    
                # Try to find elements containing this text
                found = False
                for descendant in first_item.descendants:
                    if isinstance(descendant, Tag) and value in descendant.get_text(strip=True):
                        # Generate relative path from item to this element
                        relative_path = self._get_relative_path(first_item, descendant)
                        
                        base_pattern['fields'].append({
                            'name': field,
                            'selector': relative_path,
                            'attribute': 'text'
                        })
                        found = True
                        break
                        
                if not found and 'href' in field.lower():
                    # Special case for links
                    links = first_item.find_all('a', href=True)
                    if links:
                        relative_path = self._get_relative_path(first_item, links[0])
                        
                        base_pattern['fields'].append({
                            'name': field,
                            'selector': relative_path,
                            'attribute': 'href'
                        })
            
            patterns.append(base_pattern)
            return patterns
                
        return []
    
    def _discover_product_patterns(self, soup: BeautifulSoup, example: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discover patterns for extracting product data.
        
        Args:
            soup: BeautifulSoup object of the page
            example: Example product data
            
        Returns:
            List of patterns for extracting product data
        """
        patterns = []
        
        # Create a pattern for each field in the example
        for field, value in example.items():
            if not isinstance(value, str):
                continue
                
            # Try to find elements containing this text
            for element in soup.find_all(text=lambda t: value in t if t else False):
                parent = element.parent
                
                # For product data, we typically want to find the most specific container
                # that contains only the target content
                if parent.get_text(strip=True) == value:
                    patterns.append({
                        'field': field,
                        'selector': self._get_css_path(parent),
                        'attribute': 'text',
                        'manipulation': None
                    })
                    break
        
        # Special handling for images
        if 'images' in example and isinstance(example['images'], list):
            for img_dict in example['images']:
                if 'src' in img_dict:
                    src = img_dict['src']
                    img_element = soup.find('img', src=src)
                    if img_element:
                        patterns.append({
                            'field': 'image',
                            'selector': self._get_css_path(img_element),
                            'attribute': 'src',
                            'manipulation': None
                        })
                        break
        
        return patterns
    
    def _discover_article_patterns(self, soup: BeautifulSoup, example: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discover patterns for extracting article content.
        
        Args:
            soup: BeautifulSoup object of the page
            example: Example article data
            
        Returns:
            List of patterns for extracting article data
        """
        patterns = []
        
        # Handle title
        if 'title' in example:
            title_text = example['title']
            title_element = soup.find(text=lambda t: title_text in t if t else False)
            if title_element:
                parent = title_element.parent
                patterns.append({
                    'field': 'title',
                    'selector': self._get_css_path(parent),
                    'attribute': 'text',
                    'manipulation': None
                })
        
        # Handle author
        if 'author' in example:
            author_text = example['author']
            author_element = soup.find(text=lambda t: author_text in t if t else False)
            if author_element:
                parent = author_element.parent
                patterns.append({
                    'field': 'author',
                    'selector': self._get_css_path(parent),
                    'attribute': 'text',
                    'manipulation': None
                })
        
        # Handle date
        if 'date' in example:
            date_text = example['date']
            date_element = soup.find(text=lambda t: date_text in t if t else False)
            if date_element:
                parent = date_element.parent
                patterns.append({
                    'field': 'date',
                    'selector': self._get_css_path(parent),
                    'attribute': 'text',
                    'manipulation': None
                })
        
        # Handle content
        content_field = 'content' if 'content' in example else 'text' if 'text' in example else None
        if content_field:
            content_text = example[content_field]
            
            # For content, we need to find a container that holds all paragraphs
            article_container = soup.find('article')
            if not article_container:
                # Look for likely content containers
                for container in soup.find_all(['div', 'section']):
                    if container.get('class') and any(cls in str(container.get('class')) for cls in ['content', 'article', 'post']):
                        article_container = container
                        break
            
            if article_container:
                patterns.append({
                    'field': content_field,
                    'selector': self._get_css_path(article_container),
                    'attribute': 'innerHTML',
                    'manipulation': 'extract_paragraphs'
                })
        
        return patterns
    
    def _apply_patterns(self, soup: BeautifulSoup, patterns: List[Dict[str, Any]]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Apply extraction patterns to the page.
        
        Args:
            soup: BeautifulSoup object of the page
            patterns: List of extraction patterns
            
        Returns:
            Extracted data based on patterns
        """
        # Check if this is a list pattern
        if patterns and 'container' in patterns[0]:
            return self._apply_list_patterns(soup, patterns)
            
        # Otherwise, apply field patterns for a single item
        data = {}
        
        for pattern in patterns:
            field = pattern.get('field')
            selector = pattern.get('selector')
            attribute = pattern.get('attribute', 'text')
            manipulation = pattern.get('manipulation')
            
            try:
                # Find element using the selector
                element = soup.select_one(selector)
                if not element:
                    continue
                    
                # Extract the specified attribute
                if attribute == 'text':
                    value = element.get_text(strip=True)
                elif attribute == 'innerHTML':
                    value = str(element)
                else:
                    value = element.get(attribute)
                
                # Apply manipulation if specified
                if manipulation == 'extract_paragraphs':
                    paragraphs = element.find_all('p')
                    value = [p.get_text(strip=True) for p in paragraphs]
                
                data[field] = value
                
            except Exception as e:
                logger.warning(f"Error applying pattern {pattern}: {e}")
                
        return data
    
    def _apply_list_patterns(self, soup: BeautifulSoup, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply list patterns to extract multiple items.
        
        Args:
            soup: BeautifulSoup object of the page
            patterns: List of extraction patterns
            
        Returns:
            List of extracted items
        """
        results = []
        
        for pattern in patterns:
            container_selector = pattern.get('container')
            item_selector = pattern.get('item_selector')
            fields = pattern.get('fields', [])
            
            try:
                # Find container
                container = soup.select_one(container_selector)
                if not container:
                    continue
                    
                # Find all items
                items = container.select(item_selector)
                
                # Process each item
                for item in items:
                    item_data = {}
                    
                    # Extract each field
                    for field_def in fields:
                        field_name = field_def.get('name')
                        field_selector = field_def.get('selector')
                        attribute = field_def.get('attribute', 'text')
                        
                        try:
                            # Find element using the selector
                            element = item.select_one(field_selector) if field_selector else item
                            if not element:
                                continue
                                
                            # Extract the specified attribute
                            if attribute == 'text':
                                value = element.get_text(strip=True)
                            elif attribute == 'innerHTML':
                                value = str(element)
                            else:
                                value = element.get(attribute)
                                
                            item_data[field_name] = value
                            
                        except Exception as e:
                            logger.warning(f"Error extracting field {field_name}: {e}")
                    
                    # Add the item if we extracted any data
                    if item_data:
                        results.append(item_data)
                        
            except Exception as e:
                logger.warning(f"Error applying list pattern: {e}")
                
        return results
    
    def _enhance_with_ai(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> None:
        """
        Enhance extracted data with AI analysis.
        
        Args:
            data: Extracted data to enhance
            
        Returns:
            None (modifies data in place)
        """
        if not self.use_ai or not self.ai_analyzer:
            return
            
        if isinstance(data, dict):
            # Single item - apply AI analysis
            content = ''
            
            # Gather text content
            if 'description' in data:
                content += data['description'] + ' '
            if 'text' in data:
                content += data['text'] + ' '
            if 'content' in data and isinstance(data['content'], list):
                content += ' '.join(data['content'])
                
            if content:
                # Run AI analysis with memory monitoring
                with memory_manager.memory_safe_operation("ai_content_enhancement"):
                    analysis = self.ai_analyzer.analyze_content(
                        content, 
                        analysis_types=['classification', 'sentiment', 'keywords']
                    )
                    
                    # Add AI insights to the data
                    data['ai_insights'] = analysis
                    
        elif isinstance(data, list):
            # Multiple items - apply AI analysis to each item
            for item in data:
                self._enhance_with_ai(item)
    
    def _get_css_path(self, element: Tag) -> str:
        """
        Get the CSS path of an element.
        
        Args:
            element: BeautifulSoup Tag object
            
        Returns:
            CSS path as a string
        """
        path = []
        while element:
            siblings = element.find_previous_siblings(element.name)
            index = len(siblings) + 1
            path.append(f"{element.name}:nth-of-type({index})")
            element = element.parent
        return ' > '.join(reversed(path))
    
    def _get_relative_path(self, parent: Tag, element: Tag) -> str:
        """
        Get the relative CSS path from parent to element.
        
        Args:
            parent: Parent BeautifulSoup Tag object
            element: Target BeautifulSoup Tag object
            
        Returns:
            Relative CSS path as a string
        """
        path = []
        while element and element != parent:
            siblings = element.find_previous_siblings(element.name)
            index = len(siblings) + 1
            path.append(f"{element.name}:nth-of-type({index})")
            element = element.parent
        return ' > '.join(reversed(path))
    
    def _get_semantic_path(self, element: Tag) -> List[str]:
        """
        Get the semantic path of an element.
        
        Args:
            element: BeautifulSoup Tag object
            
        Returns:
            List of tag names representing the semantic path
        """
        path = []
        while element:
            path.append(element.name)
            element = element.parent
        return list(reversed(path))
    
    def _get_max_depth(self, element: Tag) -> int:
        """
        Get the maximum depth of the DOM tree starting from the given element.
        
        Args:
            element: BeautifulSoup Tag object
            
        Returns:
            Maximum depth as an integer
        """
        if not element.children:
            return 1
        return 1 + max(self._get_max_depth(child) for child in element.children if isinstance(child, Tag))