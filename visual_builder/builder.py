"""
Visual Scraper Builder - Create scrapers using a visual interface.

This module provides the backend functionality for a visual scraper builder,
allowing users to create scrapers by selecting elements on a webpage.
"""

import os
import json
import uuid
import logging
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup

from scraping_project.resilient_browser import ResilientBrowser
from scraping_project.config import Config
from scraping_project.db_manager import DatabaseManager

# Set up logging
logger = logging.getLogger(__name__)
db_manager = DatabaseManager()

class VisualScraper:
    """
    Visual scraper for interactive scraper creation.
    
    This class provides functionality to:
    - Launch a browser for visual selection
    - Generate CSS/XPath selectors for selected elements
    - Test selectors on the page
    - Create and save scraper configurations
    - Preview data extraction
    """
    
    def __init__(self, headless: bool = False, output_dir: Optional[str] = None):
        """
        Initialize the visual scraper.
        
        Args:
            headless: Whether to run in headless mode (no GUI)
            output_dir: Directory for output files
        """
        self.headless = headless
        self.output_dir = output_dir or os.path.join(Config.SCRAPE_OUTPUT_DIR, "visual_builder")
        self.browser = None
        self.current_url = None
        self.selected_elements = {}  # field_name -> selector info
        self.active_session_id = None
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info("Visual Scraper initialized")
    
    def start_session(self, url: str) -> Dict[str, Any]:
        """
        Start a new visual scraper session.
        
        Args:
            url: URL to load for scraper building
            
        Returns:
            Session information dictionary
        """
        # Generate a unique session ID
        self.active_session_id = str(uuid.uuid4())
        
        # Initialize the browser
        self.browser = ResilientBrowser(headless=self.headless)
        self.browser.start()
        
        try:
            # Navigate to the URL
            self.browser.get(url)
            self.current_url = url
            
            # Wait for page to load
            WebDriverWait(self.browser.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Take a screenshot for reference
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = os.path.join(self.output_dir, f"{self.active_session_id}_{timestamp}.png")
            self.browser.driver.save_screenshot(screenshot_path)
            
            # Get page information
            title = self.browser.driver.title
            html = self.browser.driver.page_source
            
            # Inject custom JavaScript for element selection
            self._inject_selection_script()
            
            # Create session info
            session_info = {
                'session_id': self.active_session_id,
                'url': url,
                'title': title,
                'screenshot_path': screenshot_path,
                'timestamp': datetime.now().isoformat()
            }
            
            # Save session info
            self._save_session_info(session_info)
            
            logger.info(f"Started visual scraper session {self.active_session_id} for {url}")
            return session_info
            
        except Exception as e:
            logger.error(f"Error starting visual scraper session: {e}")
            if self.browser:
                self.browser.close()
                self.browser = None
            raise
    
    def close_session(self) -> None:
        """Close the current visual scraper session."""
        if self.browser:
            self.browser.close()
            self.browser = None
        
        self.current_url = None
        logger.info(f"Closed visual scraper session {self.active_session_id}")
    
    def select_element(self, field_name: str, selector_type: str, selector_value: str) -> Dict[str, Any]:
        """
        Record a selected element.
        
        Args:
            field_name: Name of the field this element represents
            selector_type: Type of selector (css, xpath)
            selector_value: Value of the selector
            
        Returns:
            Information about the selected element
        """
        if not self.browser or not self.active_session_id:
            raise ValueError("No active scraper session")
        
        # Validate selector
        elements = self._find_elements(selector_type, selector_value)
        
        if not elements:
            return {
                'status': 'error',
                'message': 'No elements found with this selector',
                'field_name': field_name,
                'selector_type': selector_type,
                'selector_value': selector_value
            }
        
        # Extract element information
        element_info = {
            'field_name': field_name,
            'selector_type': selector_type,
            'selector_value': selector_value,
            'element_count': len(elements),
            'sample_values': self._extract_sample_values(elements[:5])  # First 5 elements
        }
        
        # Store the element selection
        self.selected_elements[field_name] = element_info
        
        # Update the session info file
        self._update_session_elements()
        
        logger.info(f"Selected element for field '{field_name}': {selector_type}={selector_value}")
        return element_info
    
    def unselect_element(self, field_name: str) -> bool:
        """
        Remove a selected element.
        
        Args:
            field_name: Name of the field to remove
            
        Returns:
            True if the field was removed, False otherwise
        """
        if field_name in self.selected_elements:
            del self.selected_elements[field_name]
            self._update_session_elements()
            logger.info(f"Unselected element for field '{field_name}'")
            return True
        return False
    
    def test_selector(self, selector_type: str, selector_value: str) -> Dict[str, Any]:
        """
        Test a selector on the current page.
        
        Args:
            selector_type: Type of selector (css, xpath)
            selector_value: Value of the selector
            
        Returns:
            Information about the matched elements
        """
        if not self.browser:
            raise ValueError("No active scraper session")
        
        # Find elements
        elements = self._find_elements(selector_type, selector_value)
        
        # Extract information
        result = {
            'selector_type': selector_type,
            'selector_value': selector_value,
            'element_count': len(elements),
            'sample_values': self._extract_sample_values(elements[:5]) if elements else []
        }
        
        return result
    
    def generate_scraper(self, name: str, description: str = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a scraper configuration from the selected elements.
        
        Args:
            name: Name for the scraper
            description: Optional description
            user_id: Optional user ID for attribution
            
        Returns:
            Generated scraper configuration
        """
        if not self.active_session_id or not self.current_url:
            raise ValueError("No active scraper session")
        
        if not self.selected_elements:
            raise ValueError("No elements selected for scraping")
        
        # Create a unique ID for the scraper
        scraper_id = str(uuid.uuid4())
        
        # Build the scraper configuration
        config = {
            'id': scraper_id,
            'name': name,
            'description': description or f"Scraper for {self.current_url}",
            'created_at': datetime.now().isoformat(),
            'base_url': self.current_url,
            'fields': {}
        }
        
        # Add selected elements as fields
        for field_name, element_info in self.selected_elements.items():
            config['fields'][field_name] = {
                'selector_type': element_info['selector_type'],
                'selector_value': element_info['selector_value'],
                'multiple': element_info['element_count'] > 1  # Whether to extract multiple elements
            }
        
        # Save the configuration
        config_path = os.path.join(self.output_dir, f"scraper_{scraper_id}.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        # Save to database if available
        try:
            db_manager.save_visual_scraper(
                scraper_id=scraper_id,
                name=name,
                description=description,
                config=config,
                url=self.current_url,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Error saving scraper to database: {e}")
        
        logger.info(f"Generated scraper '{name}' (ID: {scraper_id})")
        
        return {
            'status': 'success',
            'scraper_id': scraper_id,
            'name': name,
            'config': config,
            'config_path': config_path
        }
    
    def preview_extraction(self) -> Dict[str, Any]:
        """
        Preview data extraction using the current element selections.
        
        Returns:
            Extracted data preview
        """
        if not self.browser or not self.selected_elements:
            raise ValueError("No active scraper session or no elements selected")
        
        # Extract data for each selected field
        preview_data = {}
        
        for field_name, element_info in self.selected_elements.items():
            selector_type = element_info['selector_type']
            selector_value = element_info['selector_value']
            
            elements = self._find_elements(selector_type, selector_value)
            
            if not elements:
                preview_data[field_name] = None
                continue
            
            # Extract values based on number of elements
            if len(elements) == 1:
                preview_data[field_name] = self._extract_element_value(elements[0])
            else:
                preview_data[field_name] = [self._extract_element_value(e) for e in elements]
        
        return {
            'status': 'success',
            'data': preview_data,
            'timestamp': datetime.now().isoformat()
        }
    
    def suggest_selectors(self, field_name: str, example_value: str) -> List[Dict[str, str]]:
        """
        Suggest selectors based on an example value.
        
        Args:
            field_name: Name of the field
            example_value: Example text value to look for
            
        Returns:
            List of suggested selectors
        """
        if not self.browser:
            raise ValueError("No active scraper session")
        
        # Get page source and parse with BeautifulSoup
        html = self.browser.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find elements containing the example text
        matching_elements = []
        
        for element in soup.find_all(string=lambda text: example_value in str(text) if text else False):
            parent = element.parent
            matching_elements.append(parent)
        
        # Generate selectors for matching elements
        suggestions = []
        
        for element in matching_elements:
            # Generate CSS selector
            css_selector = self._generate_css_selector(element)
            if css_selector:
                suggestions.append({
                    'selector_type': 'css',
                    'selector_value': css_selector
                })
            
            # Generate XPath
            xpath = self._generate_xpath(element)
            if xpath:
                suggestions.append({
                    'selector_type': 'xpath',
                    'selector_value': xpath
                })
        
        # Deduplicate suggestions
        unique_suggestions = []
        seen = set()
        
        for suggestion in suggestions:
            key = f"{suggestion['selector_type']}:{suggestion['selector_value']}"
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions
    
    def execute_scraper(self, scraper_id: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a previously saved scraper configuration.
        
        Args:
            scraper_id: ID of the scraper to execute
            url: Optional URL to scrape (defaults to the scraper's base URL)
            
        Returns:
            Extracted data
        """
        # Load the scraper configuration
        scraper = None
        
        try:
            scraper = db_manager.get_visual_scraper(scraper_id)
            if not scraper:
                # Try loading from file
                config_path = os.path.join(self.output_dir, f"scraper_{scraper_id}.json")
                with open(config_path, 'r', encoding='utf-8') as f:
                    scraper = json.load(f)
        except Exception as e:
            logger.error(f"Error loading scraper {scraper_id}: {e}")
            return {
                'status': 'error',
                'message': f"Scraper {scraper_id} not found: {str(e)}"
            }
        
        if not scraper:
            return {
                'status': 'error',
                'message': f"Scraper {scraper_id} not found"
            }
        
        # Get config (handle both database and file formats)
        if 'config' in scraper:
            config = scraper['config'] if isinstance(scraper['config'], dict) else json.loads(scraper['config'])
        else:
            config = scraper
        
        # Use provided URL or default to scraper's base URL
        target_url = url or config.get('base_url')
        
        if not target_url:
            return {
                'status': 'error',
                'message': "No URL specified for scraping"
            }
        
        # Initialize a new browser
        browser = ResilientBrowser(headless=True)
        
        try:
            browser.start()
            browser.get(target_url)
            
            # Wait for page to load
            WebDriverWait(browser.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extract data for each field
            extracted_data = {}
            fields = config.get('fields', {})
            
            for field_name, field_config in fields.items():
                selector_type = field_config.get('selector_type')
                selector_value = field_config.get('selector_value')
                multiple = field_config.get('multiple', False)
                
                # Find elements
                elements = []
                if selector_type == 'css':
                    elements = browser.driver.find_elements(By.CSS_SELECTOR, selector_value)
                elif selector_type == 'xpath':
                    elements = browser.driver.find_elements(By.XPATH, selector_value)
                
                # Extract values
                if multiple:
                    extracted_data[field_name] = [self._extract_element_value(e) for e in elements]
                elif elements:
                    extracted_data[field_name] = self._extract_element_value(elements[0])
                else:
                    extracted_data[field_name] = None
            
            # Get screenshot for reference
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = os.path.join(self.output_dir, f"result_{scraper_id}_{timestamp}.png")
            browser.driver.save_screenshot(screenshot_path)
            
            # Save result
            result_path = os.path.join(self.output_dir, f"result_{scraper_id}_{timestamp}.json")
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'scraper_id': scraper_id,
                    'url': target_url,
                    'extraction_time': datetime.now().isoformat(),
                    'data': extracted_data
                }, f, indent=2)
            
            # Record execution in database
            try:
                db_manager.save_visual_scraper_execution(
                    scraper_id=scraper_id,
                    url=target_url,
                    result_path=result_path,
                    screenshot_path=screenshot_path,
                    data=extracted_data
                )
            except Exception as e:
                logger.error(f"Error saving execution to database: {e}")
            
            return {
                'status': 'success',
                'scraper_id': scraper_id,
                'url': target_url,
                'data': extracted_data,
                'screenshot_path': screenshot_path,
                'result_path': result_path
            }
            
        except Exception as e:
            logger.error(f"Error executing scraper {scraper_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'scraper_id': scraper_id
            }
        finally:
            browser.close()
    
    def _inject_selection_script(self) -> None:
        """Inject custom JavaScript for interactive element selection."""
        script = """
        (function() {
            // Remove existing handlers
            document.removeEventListener('mousedown', window.__scrapy_mousedown);
            document.removeEventListener('click', window.__scrapy_click);
            
            // Add highlighting style
            let style = document.createElement('style');
            style.innerHTML = `
                .__scrapy_highlight {
                    outline: 2px solid red !important;
                    background-color: rgba(255, 0, 0, 0.1) !important;
                }
            `;
            document.head.appendChild(style);
            
            // Variables to track state
            let lastHighlighted = null;
            
            // Handle mouse movement for highlighting
            window.__scrapy_mouseover = function(e) {
                if (lastHighlighted) {
                    lastHighlighted.classList.remove('__scrapy_highlight');
                }
                let target = e.target;
                target.classList.add('__scrapy_highlight');
                lastHighlighted = target;
                e.stopPropagation();
            };
            
            // Handle mouse out
            window.__scrapy_mouseout = function(e) {
                let target = e.target;
                target.classList.remove('__scrapy_highlight');
            };
            
            // Handle mouse down to prevent default behavior
            window.__scrapy_mousedown = function(e) {
                e.preventDefault();
                e.stopPropagation();
            };
            
            // Handle click to select element
            window.__scrapy_click = function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                let target = e.target;
                
                // Get element info
                let tagName = target.tagName.toLowerCase();
                let classList = Array.from(target.classList).join(' ');
                let id = target.id;
                let attributes = {};
                
                for (let attr of target.attributes) {
                    attributes[attr.name] = attr.value;
                }
                
                // Get basic XPath
                let xpath = getXPath(target);
                
                // Get CSS selector
                let cssSelector = getCssSelector(target);
                
                // Send info back to Python
                window.__scrapy_selected_element = {
                    tagName: tagName,
                    classList: classList,
                    id: id,
                    attributes: attributes,
                    xpath: xpath,
                    cssSelector: cssSelector,
                    textContent: target.textContent.trim(),
                    innerHTML: target.innerHTML
                };
                
                // Dispatch custom event
                let event = new CustomEvent('__scrapy_element_selected', {
                    detail: window.__scrapy_selected_element
                });
                document.dispatchEvent(event);
                
                return false;
            };
            
            // Helper to get XPath
            function getXPath(element) {
                if (element.id) {
                    return `//*[@id="${element.id}"]`;
                }
                
                if (element === document.body) {
                    return '/html/body';
                }
                
                let path = '';
                while (element && element.nodeType === Node.ELEMENT_NODE) {
                    let siblings = Array.from(element.parentNode.children).filter(c => c.tagName === element.tagName);
                    
                    if (siblings.length > 1) {
                        let index = siblings.indexOf(element) + 1;
                        path = '/' + element.tagName.toLowerCase() + '[' + index + ']' + path;
                    } else {
                        path = '/' + element.tagName.toLowerCase() + path;
                    }
                    
                    element = element.parentNode;
                }
                
                return '/' + path;
            }
            
            // Helper to get CSS selector
            function getCssSelector(element) {
                if (element.id) {
                    return '#' + element.id;
                }
                
                if (element === document.body) {
                    return 'body';
                }
                
                let path = [];
                while (element && element.nodeType === Node.ELEMENT_NODE) {
                    let selector = element.tagName.toLowerCase();
                    
                    if (element.id) {
                        selector += '#' + element.id;
                        path.unshift(selector);
                        break;
                    } else {
                        let sibling = element;
                        let index = 1;
                        
                        while (sibling = sibling.previousElementSibling) {
                            if (sibling.tagName === element.tagName) {
                                index++;
                            }
                        }
                        
                        if (index > 1) {
                            selector += ':nth-of-type(' + index + ')';
                        }
                    }
                    
                    path.unshift(selector);
                    element = element.parentNode;
                }
                
                return path.join(' > ');
            }
            
            // Add event listeners
            document.addEventListener('mouseover', window.__scrapy_mouseover);
            document.addEventListener('mouseout', window.__scrapy_mouseout);
            document.addEventListener('mousedown', window.__scrapy_mousedown);
            document.addEventListener('click', window.__scrapy_click);
            
            console.log('Scrapy Visual Builder selection mode activated');
        })();
        """
        
        try:
            self.browser.driver.execute_script(script)
            logger.info("Injected element selection script into page")
        except Exception as e:
            logger.error(f"Error injecting selection script: {e}")
    
    def _find_elements(self, selector_type: str, selector_value: str) -> List[webdriver.remote.webelement.WebElement]:
        """Find elements using the specified selector."""
        elements = []
        
        try:
            if selector_type == 'css':
                elements = self.browser.driver.find_elements(By.CSS_SELECTOR, selector_value)
            elif selector_type == 'xpath':
                elements = self.browser.driver.find_elements(By.XPATH, selector_value)
            else:
                raise ValueError(f"Unsupported selector type: {selector_type}")
        except Exception as e:
            logger.warning(f"Error finding elements with {selector_type}={selector_value}: {e}")
        
        return elements
    
    def _extract_sample_values(self, elements: List[webdriver.remote.webelement.WebElement]) -> List[Dict[str, str]]:
        """Extract sample values from elements for preview."""
        samples = []
        
        for element in elements:
            value = self._extract_element_value(element)
            samples.append({
                'text': value['text'] if isinstance(value, dict) else str(value),
                'tag': element.tag_name,
                'html': element.get_attribute('outerHTML')[:200]  # Limit HTML length
            })
        
        return samples
    
    def _extract_element_value(self, element: webdriver.remote.webelement.WebElement) -> Union[str, Dict[str, str]]:
        """Extract the most appropriate value from an element."""
        tag = element.tag_name.lower()
        
        # Handle specific tags
        if tag == 'img':
            return {
                'src': element.get_attribute('src'),
                'alt': element.get_attribute('alt'),
                'text': element.get_attribute('alt') or ''
            }
            
        elif tag == 'a':
            return {
                'href': element.get_attribute('href'),
                'text': element.text.strip()
            }
            
        elif tag == 'input':
            input_type = element.get_attribute('type')
            if input_type in ['text', 'hidden', 'password', 'email', 'tel', 'number']:
                return element.get_attribute('value')
            elif input_type in ['checkbox', 'radio']:
                return element.is_selected()
                
        # Default to text content for most elements
        return element.text.strip() or element.get_attribute('textContent').strip()
    
    def _save_session_info(self, session_info: Dict[str, Any]) -> None:
        """Save the session information to a file."""
        session_path = os.path.join(self.output_dir, f"session_{self.active_session_id}.json")
        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump({
                **session_info,
                'elements': {}  # No elements selected yet
            }, f, indent=2)
    
    def _update_session_elements(self) -> None:
        """Update the session file with the current selected elements."""
        if not self.active_session_id:
            return
            
        session_path = os.path.join(self.output_dir, f"session_{self.active_session_id}.json")
        
        try:
            # Read existing session data
            with open(session_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Update elements
            session_data['elements'] = self.selected_elements
            session_data['updated_at'] = datetime.now().isoformat()
            
            # Write updated data
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating session file: {e}")
    
    def _generate_css_selector(self, element) -> Optional[str]:
        """Generate a CSS selector for a BeautifulSoup element."""
        try:
            if element.get('id'):
                return f"#{element['id']}"
            
            if element.get('class'):
                classes = '.'.join(element['class'])
                return f"{element.name}.{classes}"
            
            # Generate a selector with parent relationship
            selectors = [element.name]
            parent = element.parent
            
            # Go up to 3 levels of parents
            for _ in range(3):
                if not parent or parent.name == 'body':
                    break
                
                if parent.get('id'):
                    selectors.insert(0, f"#{parent['id']}")
                    break
                elif parent.get('class'):
                    classes = '.'.join(parent['class'])
                    selectors.insert(0, f"{parent.name}.{classes}")
                else:
                    selectors.insert(0, parent.name)
                
                parent = parent.parent
            
            return ' > '.join(selectors)
            
        except Exception as e:
            logger.warning(f"Error generating CSS selector: {e}")
            return None
    
    def _generate_xpath(self, element) -> Optional[str]:
        """Generate an XPath for a BeautifulSoup element."""
        try:
            if element.get('id'):
                return f"//*[@id='{element['id']}']"
            
            # Build XPath with tag names and positions
            parts = []
            current = element
            
            while current and current.name != 'html':
                siblings = [s for s in current.parent.find_all(current.name, recursive=False)]
                if len(siblings) > 1:
                    pos = siblings.index(current) + 1
                    parts.insert(0, f"{current.name}[{pos}]")
                else:
                    parts.insert(0, current.name)
                
                current = current.parent
            
            return '//' + '/'.join(parts)
            
        except Exception as e:
            logger.warning(f"Error generating XPath: {e}")
            return None
