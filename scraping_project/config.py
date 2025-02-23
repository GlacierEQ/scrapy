import os

class Config:
    # Base directory
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Output directories
    SCRAPE_OUTPUT_DIR = os.path.join(BASE_DIR, 'scraped_pages')
    IMAGE_OUTPUT_DIR = os.path.join(BASE_DIR, 'generated_images')
    
    # Web Scraping Settings
    MAX_PAGES = 10  # Maximum number of pages to scrape when following links
    PAGE_LOAD_TIMEOUT = 10  # Seconds to wait for page load
    FOLLOW_EXTERNAL_LINKS = False  # Whether to follow links to external domains
    
    # Browser Settings
    BROWSER_WIDTH = 1920
    BROWSER_HEIGHT = 1080
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    # Text Processing Settings
    EXTRACT_COMMENTS = False  # Whether to include HTML comments in text extraction
    MIN_TEXT_LENGTH = 50  # Minimum length of text blocks to extract
    EXCLUDED_TAGS = ['script', 'style', 'meta', 'link']  # HTML tags to exclude from text extraction
    
    # Image Generation Settings
    ENABLE_IMAGE_GENERATION = True
    IMAGE_MODEL = "stable-diffusion-v1-5"  # Model to use for image generation
    IMAGE_SIZE = (512, 512)  # Size of generated images
    NUM_IMAGES_PER_PAGE = 1  # Number of images to generate per page
    IMAGE_STYLE = "modern, professional, minimalist"  # Default style for generated images
    
    # API Keys (should be moved to environment variables in production)
    STABILITY_API_KEY = ""  # Add your Stability AI API key here
    
    @classmethod
    def load_from_file(cls, filepath):
        """Load settings from a configuration file"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                config_data = eval(f.read())
                for key, value in config_data.items():
                    if hasattr(cls, key):
                        setattr(cls, key, value)
    
    @classmethod
    def save_to_file(cls, filepath):
        """Save current settings to a configuration file"""
        config_data = {
            key: value for key, value in cls.__dict__.items()
            if not key.startswith('__') and not callable(value)
        }
        with open(filepath, 'w') as f:
            f.write(repr(config_data))

# Create necessary directories
os.makedirs(Config.SCRAPE_OUTPUT_DIR, exist_ok=True)
os.makedirs(Config.IMAGE_OUTPUT_DIR, exist_ok=True)

# Try to load local config if it exists
local_config = os.path.join(os.path.dirname(__file__), 'local_config.py')
if os.path.exists(local_config):
    Config.load_from_file(local_config)
