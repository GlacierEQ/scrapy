import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from urllib.parse import urljoin, urlparse

# Import from the same directory
from data_analyzer import DataAnalyzer

class WebpageScraper:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.data_analyzer = DataAnalyzer()
        
    def save_webpage(self, url, follow_links=False, compile_text=False, max_pages=10):
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 10)
            
            # Create directories for output
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_dir = os.path.join(self.output_dir, f"scrape_{timestamp}")
            os.makedirs(base_dir, exist_ok=True)
            
            # Initialize result data
            result_data = {
                "pages": [],
                "status": "success"
            }
            
            # Process the main URL
            self._process_page(driver, wait, url, base_dir, result_data)
            
            # Follow links if requested
            if follow_links and len(result_data["pages"]) < max_pages:
                processed_urls = {url}
                base_domain = urlparse(url).netloc
                
                for page in result_data["pages"]:
                    if len(result_data["pages"]) >= max_pages:
                        break
                        
                    for link in page.get("links", []):
                        if len(result_data["pages"]) >= max_pages:
                            break
                            
                        link_url = link.get("url")
                        if (link_url and link_url not in processed_urls and 
                            urlparse(link_url).netloc == base_domain):
                            processed_urls.add(link_url)
                            self._process_page(driver, wait, link_url, base_dir, result_data)
            
            # Compile text analysis if requested
            if compile_text and result_data["pages"]:
                compiled_text = ""
                for page in result_data["pages"]:
                    if page.get("text"):
                        compiled_text += f"\n\n=== {page['url']} ===\n\n"
                        compiled_text += page["text"]
                
                if compiled_text:
                    compiled_report_path = os.path.join(base_dir, "compiled_analysis.txt")
                    with open(compiled_report_path, 'w', encoding='utf-8') as f:
                        f.write(compiled_text)
                    result_data["compiled_report"] = compiled_report_path
            
            driver.quit()
            return {"status": "success", "message": "Scraping completed successfully", "data": result_data}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _process_page(self, driver, wait, url, base_dir, result_data):
        try:
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Create page-specific directory
            page_dir = os.path.join(base_dir, f"page_{len(result_data['pages']) + 1}")
            os.makedirs(page_dir, exist_ok=True)
            
            # Save screenshot
            screenshot_path = os.path.join(page_dir, "screenshot.png")
            driver.save_screenshot(screenshot_path)
            
            # Get page content
            html_content = driver.page_source
            html_path = os.path.join(page_dir, "page.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Extract links
            links = []
            for element in driver.find_elements(By.TAG_NAME, "a"):
                href = element.get_attribute("href")
                if href:
                    links.append({
                        "text": element.text.strip(),
                        "url": href
                    })
            
            # Extract text content
            text_content = driver.find_element(By.TAG_NAME, "body").text
            
            # Analyze content
            analysis = self.data_analyzer.analyze_content(text_content, html_content)
            
            # Save analysis report
            report_path = os.path.join(page_dir, "analysis.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\n\n")
                f.write("=== Content Analysis ===\n")
                f.write(f"Word Count: {analysis['content_analysis']['word_count']}\n")
                f.write(f"Images: {analysis['content_analysis']['images']}\n")
                f.write(f"Links: {len(links)}\n\n")
                
                f.write("=== Most Common Words ===\n")
                for word, count in analysis['text_statistics']['most_common_words'].items():
                    f.write(f"{word}: {count}\n")
            
            # Add page data to results
            page_data = {
                "url": url,
                "screenshot_path": screenshot_path,
                "html_path": html_path,
                "report_path": report_path,
                "links": links,
                "text": text_content,
                "analysis": analysis
            }
            
            result_data["pages"].append(page_data)
            
        except TimeoutException:
            print(f"Timeout while loading {url}")
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
