import os
import time
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any, Optional

# Import resilient browser and error handling utilities
from .resilient_browser import ResilientBrowser
from .error_handler import error_context, retry, log_error_to_file, ScrapyError

# Import analyzer
from .data_analyzer import DataAnalyzer

class WebpageScraper:
    def __init__(self, output_dir: str, headless: bool = True):
        self.output_dir = output_dir
        self.headless = headless
        self.data_analyzer = DataAnalyzer()
        self.logger = logging.getLogger(__name__)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def save_webpage(self, url: str, follow_links: bool = False, compile_text: bool = False, max_pages: int = 10) -> Dict[str, Any]:
        browser = None
        result_data = {
            "pages": [],
            "status": "success"
        }
        
        try:
            # Create directories for output
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_dir = os.path.join(self.output_dir, f"scrape_{timestamp}")
            os.makedirs(base_dir, exist_ok=True)
            
            # Initialize browser with resilient wrapper
            browser = ResilientBrowser(
                headless=self.headless,
                timeout=30,  # Increased timeout for reliability
                browser_width=1920,
                browser_height=1080
            )
            browser.start()
            
            # Process the main URL
            with error_context(f"process_main_url_{url}", reraise=False):
                self._process_page(browser, url, 0, base_dir, result_data)
            
            # Follow links if requested
            if follow_links and result_data["pages"]:
                self._follow_links(browser, url, base_dir, result_data, max_pages)
            
            # Compile text analysis if requested
            if compile_text and result_data["pages"]:
                self._compile_text_analysis(base_dir, result_data)
                
            return {
                "status": "success",
                "message": f"Scraping completed successfully. Processed {len(result_data['pages'])} pages.",
                "data": result_data
            }
            
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
            
            # Take error screenshot if browser is available
            if browser and browser.driver:
                error_screenshot = browser.take_error_screenshot("scraper_error")
                error_log = log_error_to_file(e)
                
                return {
                    "status": "error",
                    "message": str(e),
                    "error_details": {
                        "screenshot": error_screenshot,
                        "error_log": error_log
                    }
                }
            
            return {"status": "error", "message": str(e)}
            
        finally:
            # Always ensure browser is closed properly
            if browser:
                browser.close()
    
    def _process_page(self, browser: ResilientBrowser, url: str, depth: int, base_dir: str, result_data: Dict) -> None:
        """Process a single page."""
        self.logger.info(f"Processing {url} (depth: {depth})")
        
        # Create page-specific directory
        page_dir = os.path.join(base_dir, f"page_{len(result_data['pages']) + 1}")
        os.makedirs(page_dir, exist_ok=True)
        
        # Navigate to URL with resilient browser
        if not browser.get(url):
            self.logger.warning(f"Failed to load {url}, skipping page")
            return
            
        # Try to wait for page content to load
        try:
            browser.wait_for(By.TAG_NAME, "body")
        except Exception as e:
            self.logger.warning(f"Timeout waiting for page content on {url}: {e}")
        
        # Save screenshot with error handling
        screenshot_path = os.path.join(page_dir, "screenshot.png")
        try:
            browser.driver.save_screenshot(screenshot_path)
        except Exception as e:
            self.logger.warning(f"Failed to save screenshot: {e}")
            screenshot_path = None
        
        # Get page content
        try:
            html_content = browser.driver.page_source
            html_path = os.path.join(page_dir, "page.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            self.logger.error(f"Failed to save HTML: {e}")
            html_path = None
            html_content = ""
        
        # Extract links with error handling
        links = []
        try:
            link_elements = browser.driver.find_elements(By.TAG_NAME, "a")
            for element in link_elements:
                try:
                    href = element.get_attribute("href")
                    if href:
                        links.append({
                            "text": element.text.strip() or "[No Text]",
                            "url": href
                        })
                except StaleElementReferenceException:
                    # Element might have changed, just skip it
                    continue
                except Exception as e:
                    self.logger.debug(f"Error extracting link: {e}")
        except Exception as e:
            self.logger.warning(f"Error finding links: {e}")
        
        # Extract text content
        try:
            text_content = browser.driver.find_element(By.TAG_NAME, "body").text
        except Exception as e:
            self.logger.warning(f"Error extracting text: {e}")
            text_content = ""
        
        # Analyze content with error handling
        try:
            analysis = self.data_analyzer.analyze_webpage(html_content)
            
            # Save analysis report
            report_path = os.path.join(page_dir, "analysis.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(self.data_analyzer.generate_report(analysis))
        except Exception as e:
            self.logger.error(f"Error analyzing content: {e}")
            analysis = {"error": str(e)}
            report_path = None
        
        # Add page data to results
        page_data = {
            "url": url,
            "depth": depth,
            "timestamp": datetime.now().isoformat(),
            "title": analysis.get("metadata", {}).get("title", ""),
            "screenshot_path": screenshot_path,
            "html_path": html_path,
            "report_path": report_path,
            "links": links,
            "links_count": len(links),
            "text": text_content,
            "analysis": analysis
        }
        
        result_data["pages"].append(page_data)
        self.logger.info(f"Successfully processed {url}")

    # ...existing code for _follow_links and _compile_text_analysis...
