from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def scrape_hawaii_jefs(username, password):
    """
    Scrape data from Hawaii JEFS with improved error handling and explicit waits.
    Returns a dictionary containing the scraped data and status information.
    """
    driver = None
    try:
        # Setup Chrome in headless mode for production
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 10)  # Wait up to 10 seconds
        
        # Navigate to the login page
        driver.get('https://jefs.courts.hawaii.gov/')
        
        # Wait for and find login elements
        username_field = wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        password_field = wait.until(EC.presence_of_element_located((By.NAME, 'password')))
        
        # Input credentials
        username_field.send_keys(username)
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)
        
        # Wait for login to complete and verify
        try:
            # Wait for either success element or error message
            success_element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'case-class')))
            
            # Extract case data
            case_data = success_element.text
            
            # Return successful result with data
            return {
                "status": "success",
                "data": {
                    "case_info": case_data,
                    # Add more data fields as needed
                }
            }
            
        except TimeoutException:
            # Check for error messages
            try:
                error_element = driver.find_element(By.CLASS_NAME, 'error-message')
                return {
                    "status": "error",
                    "message": "Login failed: " + error_element.text
                }
            except NoSuchElementException:
                return {
                    "status": "error",
                    "message": "Login failed: Unable to verify login success"
                }
                
    except TimeoutException as e:
        return {
            "status": "error",
            "message": "Connection timeout: The server is not responding"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}"
        }
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    result = scrape_hawaii_jefs('your_username', 'your_password')
    print(result)
