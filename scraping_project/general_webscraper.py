from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from datetime import datetime

class WebpageScraper:
    def __init__(self, output_dir="scraped_pages"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def setup_driver(self):
        """Set up Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        return webdriver.Chrome(options=chrome_options)

    def save_webpage(self, url):
        """
        Save a webpage's screenshot and HTML content
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        page_dir = os.path.join(self.output_dir, timestamp)
        
        try:
            # Create directory for this capture
            os.makedirs(page_dir)
            
            # Initialize webdriver
            driver = self.setup_driver()
            
            try:
                # Load the page
                driver.get(url)
                
                # Set window size for screenshot
                driver.set_window_size(1920, 1080)
                
                # Take screenshot
                screenshot_path = os.path.join(page_dir, "screenshot.png")
                driver.save_screenshot(screenshot_path)
                
                # Save HTML content
                html_path = os.path.join(page_dir, "page.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                
                return {
                    "status": "success",
                    "message": "Webpage saved successfully",
                    "data": {
                        "directory": page_dir,
                        "screenshot_path": screenshot_path,
                        "html_path": html_path,
                        "timestamp": timestamp
                    }
                }
                
            finally:
                driver.quit()
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"An error occurred: {str(e)}"
            }

if __name__ == "__main__":
    scraper = WebpageScraper()
    url = input("Enter the URL of the webpage to scrape: ")
    result = scraper.save_webpage(url)
    print(result)
