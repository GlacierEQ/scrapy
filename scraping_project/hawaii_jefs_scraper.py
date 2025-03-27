import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class HawaiiJEFSScraper:
    """
    Specialized scraper for Hawaii Judiciary Electronic Filing System (JEFS)
    
    This scraper handles authentication, navigation of the JEFS system,
    and extraction of case information and documents.
    """
    
    BASE_URL = "https://jimspss1.courts.state.hi.us/JEFS"
    LOGIN_URL = f"{BASE_URL}/user/login.html"
    
    def __init__(self, output_dir: str, headless: bool = True):
        """Initialize the JEFS scraper."""
        self.output_dir = output_dir
        self.headless = headless
        self.logger = logging.getLogger(__name__)
        
    def scrape(self, username: str, password: str, case_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main method to scrape JEFS system.
        
        Args:
            username: JEFS username
            password: JEFS password
            case_id: Optional specific case ID to scrape
            
        Returns:
            Dictionary with scraping results
        """
        # Setup Chrome options
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Create output directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_dir = os.path.join(self.output_dir, f"jefs_scrape_{timestamp}")
        os.makedirs(base_dir, exist_ok=True)
        
        # Initialize result structure
        result = {
            "status": "success",
            "message": "",
            "data": {
                "cases": [],
                "total_cases": 0,
                "total_documents": 0,
                "timestamp": timestamp
            }
        }
        
        driver = None
        try:
            self.logger.info("Starting JEFS scraper")
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 20)  # JEFS can be slow, use longer timeout
            
            # Login to JEFS
            self._login(driver, wait, username, password)
            
            # If a specific case_id is provided, scrape just that case
            if case_id:
                self.logger.info(f"Scraping specific case: {case_id}")
                case_data = self._scrape_single_case(driver, wait, case_id, base_dir)
                result["data"]["cases"].append(case_data)
                result["data"]["total_cases"] = 1
                result["data"]["total_documents"] = len(case_data.get("documents", []))
            else:
                # Scrape all available cases
                self.logger.info("Scraping all available cases")
                cases, total_docs = self._scrape_all_cases(driver, wait, base_dir)
                result["data"]["cases"] = cases
                result["data"]["total_cases"] = len(cases)
                result["data"]["total_documents"] = total_docs
            
            result["message"] = f"Successfully scraped {result['data']['total_cases']} cases with {result['data']['total_documents']} documents"
            return result
            
        except Exception as e:
            self.logger.error(f"Error during JEFS scraping: {str(e)}")
            result["status"] = "error"
            result["message"] = str(e)
            return result
        finally:
            if driver:
                driver.quit()
    
    def _login(self, driver: webdriver.Chrome, wait: WebDriverWait, username: str, password: str) -> None:
        """Login to JEFS system."""
        try:
            self.logger.info(f"Logging in as {username}")
            driver.get(self.LOGIN_URL)
            
            # Wait for login form
            wait.until(EC.presence_of_element_located((By.ID, "userId")))
            
            # Enter credentials
            driver.find_element(By.ID, "userId").send_keys(username)
            driver.find_element(By.ID, "password").send_keys(password)
            driver.find_element(By.NAME, "submit").click()
            
            # Wait for successful login (dashboard page)
            wait.until(EC.presence_of_element_located((By.ID, "dashboardForm")))
            self.logger.info("Login successful")
            
        except TimeoutException:
            # Check if there's an error message
            try:
                error_msg = driver.find_element(By.CLASS_NAME, "error-message").text
                raise Exception(f"Login failed: {error_msg}")
            except NoSuchElementException:
                raise Exception("Login failed: Timeout waiting for login to complete")
    
    def _scrape_all_cases(self, driver: webdriver.Chrome, wait: WebDriverWait, base_dir: str) -> tuple:
        """Scrape all available cases."""
        cases = []
        total_documents = 0
        
        # Navigate to case search
        driver.find_element(By.LINK_TEXT, "Case Search").click()
        wait.until(EC.presence_of_element_located((By.ID, "caseSearchForm")))
        
        # Search for all cases (no filter)
        driver.find_element(By.NAME, "search").click()
        wait.until(EC.presence_of_element_located((By.ID, "searchResultsTable")))
        
        # Process pagination
        has_next_page = True
        page = 1
        
        while has_next_page:
            self.logger.info(f"Processing case list page {page}")
            
            # Get all case links on current page
            case_links = driver.find_elements(By.XPATH, "//table[@id='searchResultsTable']//a[contains(@href, 'caseId')]")
            case_ids = [link.text.strip() for link in case_links]
            
            # Process each case
            for case_id in case_ids:
                # Navigate back to case search results if needed
                if driver.current_url != self.case_search_url:
                    driver.get(self.case_search_url)
                    wait.until(EC.presence_of_element_located((By.ID, "searchResultsTable")))
                    
                # Find and click the specific case link
                case_link = driver.find_element(By.XPATH, f"//a[contains(text(), '{case_id}')]")
                case_link.click()
                
                # Scrape the case
                case_dir = os.path.join(base_dir, f"case_{case_id.replace('-', '_')}")
                os.makedirs(case_dir, exist_ok=True)
                
                case_data = self._scrape_case_details(driver, wait, case_dir)
                cases.append(case_data)
                total_documents += len(case_data.get("documents", []))
                
                # Go back to search results
                driver.back()
                wait.until(EC.presence_of_element_located((By.ID, "searchResultsTable")))
            
            # Check for next page and navigate if present
            try:
                next_button = driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
                if "disabled" not in next_button.get_attribute("class"):
                    next_button.click()
                    wait.until(EC.presence_of_element_located((By.ID, "searchResultsTable")))
                    page += 1
                else:
                    has_next_page = False
            except NoSuchElementException:
                has_next_page = False
        
        return cases, total_documents
    
    def _scrape_single_case(self, driver: webdriver.Chrome, wait: WebDriverWait, case_id: str, base_dir: str) -> Dict[str, Any]:
        """Scrape a specific case by ID."""
        # Navigate to case search
        driver.find_element(By.LINK_TEXT, "Case Search").click()
        wait.until(EC.presence_of_element_located((By.ID, "caseSearchForm")))
        
        # Enter the case ID
        driver.find_element(By.ID, "caseId").send_keys(case_id)
        driver.find_element(By.NAME, "search").click()
        
        try:
            wait.until(EC.presence_of_element_located((By.ID, "searchResultsTable")))
            
            # Click on the case link
            case_link = driver.find_element(By.XPATH, f"//a[contains(text(), '{case_id}')]")
            case_link.click()
            
            # Scrape the case
            case_dir = os.path.join(base_dir, f"case_{case_id.replace('-', '_')}")
            os.makedirs(case_dir, exist_ok=True)
            
            return self._scrape_case_details(driver, wait, case_dir)
            
        except TimeoutException:
            raise Exception(f"Case '{case_id}' not found or access denied")
    
    def _scrape_case_details(self, driver: webdriver.Chrome, wait: WebDriverWait, case_dir: str) -> Dict[str, Any]:
        """Scrape details, documents, and events for a case."""
        wait.until(EC.presence_of_element_located((By.ID, "caseDetailForm")))
        
        # Take screenshot of case details
        screenshot_path = os.path.join(case_dir, "case_details.png")
        driver.save_screenshot(screenshot_path)
        
        # Extract case metadata
        case_data = {
            "case_id": driver.find_element(By.XPATH, "//span[contains(@id, 'caseId')]").text,
            "case_title": driver.find_element(By.XPATH, "//span[contains(@id, 'caseTitle')]").text,
            "filing_date": driver.find_element(By.XPATH, "//span[contains(@id, 'filingDate')]").text,
            "case_type": driver.find_element(By.XPATH, "//span[contains(@id, 'caseType')]").text,
            "court": driver.find_element(By.XPATH, "//span[contains(@id, 'court')]").text,
            "status": driver.find_element(By.XPATH, "//span[contains(@id, 'status')]").text,
            "screenshot": screenshot_path,
            "parties": [],
            "events": [],
            "documents": []
        }
        
        # Extract parties
        try:
            party_table = driver.find_element(By.ID, "partiesTable")
            for row in party_table.find_elements(By.TAG_NAME, "tr")[1:]:  # Skip header
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    case_data["parties"].append({
                        "name": cols[0].text,
                        "type": cols[1].text
                    })
        except NoSuchElementException:
            self.logger.warning("No parties table found")
        
        # Navigate to documents tab
        docs_tab = driver.find_element(By.XPATH, "//a[contains(@href, 'documents')]")
        docs_tab.click()
        wait.until(EC.presence_of_element_located((By.ID, "documentsTable")))
        
        # Take screenshot of documents
        screenshot_path = os.path.join(case_dir, "documents.png")
        driver.save_screenshot(screenshot_path)
        
        # Extract documents
        try:
            docs_table = driver.find_element(By.ID, "documentsTable")
            for row in docs_table.find_elements(By.TAG_NAME, "tr")[1:]:  # Skip header
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 4:
                    doc_id = cols[0].text
                    filing_date = cols[1].text
                    description = cols[2].text
                    
                    document = {
                        "document_id": doc_id,
                        "filing_date": filing_date,
                        "description": description
                    }
                    
                    # Try to download the document if download link exists
                    try:
                        download_link = cols[3].find_element(By.TAG_NAME, "a")
                        download_link.click()
                        
                        # Wait for download dialog and handle it
                        wait.until(EC.presence_of_element_located((By.ID, "downloadDialog")))
                        
                        # Save dialog screenshot
                        dialog_screenshot = os.path.join(case_dir, f"download_dialog_{doc_id}.png")
                        driver.save_screenshot(dialog_screenshot)
                        
                        # Accept terms
                        try:
                            agree_checkbox = driver.find_element(By.ID, "agreeCheckbox")
                            if not agree_checkbox.is_selected():
                                agree_checkbox.click()
                            
                            # Click download button
                            driver.find_element(By.ID, "downloadButton").click()
                            
                            # Wait for download to start
                            time.sleep(2)  # Simple wait for download to begin
                            
                            document["downloaded"] = True
                            document["download_timestamp"] = datetime.now().isoformat()
                        except:
                            document["downloaded"] = False
                            document["download_error"] = "Could not accept terms or click download"
                        
                        # Close download dialog
                        try:
                            close_button = driver.find_element(By.XPATH, "//button[contains(@onclick, 'closeDownloadDialog')]")
                            close_button.click()
                            wait.until(EC.invisibility_of_element_located((By.ID, "downloadDialog")))
                        except:
                            self.logger.warning(f"Could not close download dialog for document {doc_id}")
                            
                    except NoSuchElementException:
                        document["downloaded"] = False
                        document["download_error"] = "No download link available"
                    
                    case_data["documents"].append(document)
        except NoSuchElementException:
            self.logger.warning("No documents table found")
        
        # Navigate to docket tab
        docket_tab = driver.find_element(By.XPATH, "//a[contains(@href, 'docket')]")
        docket_tab.click()
        wait.until(EC.presence_of_element_located((By.ID, "docketTable")))
        
        # Take screenshot of docket events
        screenshot_path = os.path.join(case_dir, "docket.png")
        driver.save_screenshot(screenshot_path)
        
        # Extract docket events
        try:
            docket_table = driver.find_element(By.ID, "docketTable")
            for row in docket_table.find_elements(By.TAG_NAME, "tr")[1:]:  # Skip header
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 3:
                    case_data["events"].append({
                        "date": cols[0].text,
                        "description": cols[1].text,
                        "filed_by": cols[2].text
                    })
        except NoSuchElementException:
            self.logger.warning("No docket table found")
        
        return case_data

# For direct execution
def scrape_hawaii_jefs(username: str, password: str, case_id: Optional[str] = None, output_dir: str = "output") -> Dict[str, Any]:
    """Convenience function for direct scraping."""
    scraper = HawaiiJEFSScraper(output_dir=output_dir)
    return scraper.scrape(username, password, case_id)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Hawaii JEFS Scraper")
    parser.add_argument("username", help="JEFS username")
    parser.add_argument("password", help="JEFS password")
    parser.add_argument("--case", help="Optional specific case ID to scrape")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument("--visible", action="store_true", help="Show browser window during scraping")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    scraper = HawaiiJEFSScraper(output_dir=args.output, headless=not args.visible)
    result = scraper.scrape(args.username, args.password, args.case)
    
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    print(f"Cases: {result['data']['total_cases']}")
    print(f"Documents: {result['data']['total_documents']}")
