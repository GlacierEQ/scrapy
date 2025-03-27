"""
Resilient browser wrapper for web scrapers that can recover from common
Selenium/browser errors and provides enhanced stability features.
"""

import os
import time
import logging
import random
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException, TimeoutException, StaleElementReferenceException,
    ElementClickInterceptedException, NoSuchElementException, SessionNotCreatedException
)

from .error_handler import retry, error_context, handle_selenium_errors

logger = logging.getLogger(__name__)

class ResilientBrowser:
    """
    A resilient Selenium browser wrapper that can recover from common errors.
    
    Features:
    - Automatic retry of failed operations
    - Recovery from common browser errors
    - Session persistence and restoration
    - Rate limiting and anti-bot detection measures
    - Detailed error logging with screenshots
    """
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 10,
        browser_width: int = 1920,
        browser_height: int = 1080,
        user_agent: Optional[str] = None,
        proxy: Optional[str] = None,
        persistent_session: bool = False,
        session_dir: Optional[str] = None
    ):
        """
        Initialize the resilient browser.
        
        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for operations in seconds
            browser_width: Browser window width
            browser_height: Browser window height
            user_agent: Custom user agent string
            proxy: Proxy server in format 'host:port'
            persistent_session: Whether to save/restore session cookies
            session_dir: Directory to store session data
        """
        self.headless = headless
        self.timeout = timeout
        self.browser_width = browser_width
        self.browser_height = browser_height
        self.user_agent = user_agent
        self.proxy = proxy
        self.persistent_session = persistent_session
        
        if persistent_session:
            self.session_dir = session_dir or os.path.join(os.path.dirname(__file__), "browser_sessions")
            os.makedirs(self.session_dir, exist_ok=True)
        
        self.driver = None
        self.wait = None
        self.session_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    def __enter__(self):
        """Context manager enter."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def start(self):
        """Start the browser."""
        if self.driver:
            return
            
        with error_context("browser_start"):
            options = self._configure_options()
            service = Service()
            
            try:
                self.driver = webdriver.Chrome(options=options, service=service)
                self.driver.set_window_size(self.browser_width, self.browser_height)
                self.wait = WebDriverWait(self.driver, self.timeout)
                
                # Restore session if available and enabled
                if self.persistent_session:
                    self._restore_session()
                    
                logger.info("Browser started successfully")
                    
            except SessionNotCreatedException as e:
                logger.error(f"Failed to create browser session: {e}")
                raise
            except WebDriverException as e:
                logger.error(f"WebDriver error during startup: {e}")
                raise
    
    def close(self):
        """Safely close the browser."""
        if not self.driver:
            return
            
        try:
            # Save session if enabled
            if self.persistent_session:
                self._save_session()
                
            self.driver.quit()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
        finally:
            self.driver = None
            self.wait = None
    
    def restart(self):
        """Restart the browser session."""
        logger.info("Restarting browser")
        self.close()
        time.sleep(2)  # Allow time for cleanup
        self.start()
    
    @retry(max_tries=3, delay=2, exceptions=(WebDriverException,))
    def get(self, url: str) -> bool:
        """
        Navigate to a URL with retry capability.
        
        Args:
            url: URL to navigate to
            
        Returns:
            True if navigation was successful
        """
        if not self.driver:
            self.start()
            
        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            return True
        except TimeoutException:
            logger.warning(f"Timeout navigating to {url}")
            return False
        except WebDriverException as e:
            logger.error(f"Error navigating to {url}: {e}")
            # Try to recover by restarting
            self.restart()
            self.driver.get(url)
            return True
    
    @retry(max_tries=2, exceptions=(StaleElementReferenceException, TimeoutException))
    def wait_for(self, by: By, value: str, timeout: Optional[int] = None) -> Any:
        """
        Wait for an element to be present.
        
        Args:
            by: Selenium By locator
            value: Locator value
            timeout: Optional custom timeout
            
        Returns:
            The found element
        """
        if not self.driver:
            raise RuntimeError("Browser not started")
            
        wait = WebDriverWait(self.driver, timeout or self.timeout)
        return wait.until(EC.presence_of_element_located((by, value)))
    
    @retry(max_tries=3, exceptions=(ElementClickInterceptedException, StaleElementReferenceException))
    def safe_click(self, element) -> bool:
        """
        Safely click an element with retries and scroll-into-view.
        
        Args:
            element: Element to click
            
        Returns:
            True if click was successful
        """
        if not self.driver:
            raise RuntimeError("Browser not started")
        
        try:
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)  # Allow time for scrolling
            
            # Try regular click first
            element.click()
            return True
        except ElementClickInterceptedException:
            # Try JavaScript click as fallback
            self.driver.execute_script("arguments[0].click();", element)
            return True
    
    def take_error_screenshot(self, error_name: str) -> str:
        """
        Take a screenshot when an error occurs.
        
        Args:
            error_name: Name of the error for the filename
            
        Returns:
            Path to the screenshot file
        """
        if not self.driver:
            return ""
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "error_screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            
            filename = f"error_{error_name}_{timestamp}.png"
            filepath = os.path.join(screenshot_dir, filename)
            
            self.driver.save_screenshot(filepath)
            logger.info(f"Error screenshot saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to take error screenshot: {e}")
            return ""
    
    def _configure_options(self) -> Options:
        """Configure Chrome options."""
        options = Options()
        
        if self.headless:
            options.add_argument('--headless')
            
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'--window-size={self.browser_width},{self.browser_height}')
        
        if self.user_agent:
            options.add_argument(f'--user-agent={self.user_agent}')
        
        if self.proxy:
            options.add_argument(f'--proxy-server={self.proxy}')
        
        # Add additional privacy and performance options
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--blink-settings=imagesEnabled=true')  # Enable images
        
        # Disable automation flags to avoid detection
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        return options
    
    def _save_session(self):
        """Save current session cookies and local storage."""
        if not self.driver:
            return
            
        try:
            session_path = os.path.join(self.session_dir, f"session_{self.session_id}.json")
            
            session_data = {
                'cookies': self.driver.get_cookies(),
                'local_storage': dict(self._execute_script("return Object.entries(localStorage);")),
                'session_storage': dict(self._execute_script("return Object.entries(sessionStorage);"))
            }
            
            with open(session_path, 'w') as f:
                json.dump(session_data, f)
                
            logger.debug(f"Session saved to {session_path}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def _restore_session(self):
        """Restore previous session cookies and storage."""
        if not self.driver:
            return
            
        try:
            # Find the most recent session file
            session_files = [f for f in os.listdir(self.session_dir) if f.startswith("session_")]
            if not session_files:
                return
                
            latest_session = max(session_files)
            session_path = os.path.join(self.session_dir, latest_session)
            
            with open(session_path, 'r') as f:
                session_data = json.load(f)
            
            # Restore cookies
            for cookie in session_data.get('cookies', []):
                self.driver.add_cookie(cookie)
            
            # Restore local storage
            for key, value in session_data.get('local_storage', {}).items():
                self._execute_script(f"localStorage.setItem('{key}', '{value}');")
            
            # Restore session storage
            for key, value in session_data.get('session_storage', {}).items():
                self._execute_script(f"sessionStorage.setItem('{key}', '{value}');")
                
            logger.debug(f"Session restored from {session_path}")
        except Exception as e:
            logger.error(f"Failed to restore session: {e}")
    
    def _execute_script(self, script: str) -> Any:
        """Safely execute JavaScript."""
        if not self.driver:
            return None
            
        try:
            return self.driver.execute_script(script)
        except Exception as e:
            logger.error(f"Error executing script: {e}")
            return None

    def add_randomness(self, min_delay: float = 0.5, max_delay: float = 2.0):
        """
        Add random delays and mouse movements to avoid bot detection.
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        if not self.driver:
            return
            
        try:
            # Add random delay
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
            
            # Add random mouse movement
            if not self.headless:
                viewport_width = self.driver.execute_script("return window.innerWidth;")
                viewport_height = self.driver.execute_script("return window.innerHeight;")
                
                x = random.randint(0, viewport_width)
                y = random.randint(0, viewport_height)
                
                self.driver.execute_script(f"""
                    var event = new MouseEvent('mousemove', {{
                        'view': window,
                        'bubbles': true,
                        'cancelable': true,
                        'clientX': {x},
                        'clientY': {y}
                    }});
                    document.dispatchEvent(event);
                """)
        except Exception as e:
            logger.debug(f"Error adding randomness: {e}")
