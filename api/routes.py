from flask import Flask, request, jsonify, Blueprint, current_app, g
import os
import time
from datetime import datetime
import logging

from scraping_project.general_webscraper import WebpageScraper
from scraping_project.recursive_scraper import RecursiveScraper
from scraping_project.hawaii_jefs_scraper import HawaiiJEFSScraper
from scraping_project.db_manager import DatabaseManager
from scraping_project.auth_manager import AuthManager
from scraping_project.config import Config

# Set up Blueprint for the API routes
api = Blueprint('api', __name__)

# Initialize database and authentication managers
db_manager = DatabaseManager()

# Helper function to require API key
def require_api_key(f):
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "API key required"}), 401
            
        # In a production environment, validate against stored API keys in database
        if api_key != current_app.config.get('API_KEY'):
            return jsonify({"error": "Invalid API key"}), 403
            
        return f(*args, **kwargs)
    
    return decorated_function

@api.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

@api.route('/scrape', methods=['POST'])
@require_api_key
def scrape():
    """API endpoint to scrape a URL."""
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
        
    url = data['url']
    follow_links = data.get('follow_links', False)
    compile_text = data.get('compile_text', False)
    max_pages = data.get('max_pages', 10)
    user_id = data.get('user_id')  # Optional user ID for attribution
    
    try:
        # Record the job start in the database
        job_id = db_manager.save_scraping_job(
            url=url,
            job_type="general_scrape",
            status="in_progress",
            follow_links=follow_links,
            max_pages=max_pages,
            user_id=user_id
        )
        
        # Start timing
        start_time = time.time()
        
        # Run the scrape
        scraper = WebpageScraper(output_dir=Config.SCRAPE_OUTPUT_DIR)
        result = scraper.save_webpage(
            url=url,
            follow_links=follow_links,
            compile_text=compile_text,
            max_pages=max_pages
        )
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Update job in database
        status = "success" if result.get("status") == "success" else "error"
        db_manager.update_scraping_job(
            job_id=job_id,
            status=status,
            duration=duration,
            metadata={
                "pages_count": len(result.get("data", {}).get("pages", [])),
                "message": result.get("message", "")
            }
        )
        
        # If successful, store individual pages
        if status == "success" and "data" in result and "pages" in result["data"]:
            for page in result["data"]["pages"]:
                db_manager.save_scraped_page(
                    job_id=job_id,
                    url=page.get("url", ""),
                    title=page.get("title", ""),
                    word_count=page.get("analysis", {}).get("content_analysis", {}).get("word_count", 0),
                    screenshot_path=page.get("screenshot_path"),
                    html_path=page.get("html_path"),
                    analysis_path=page.get("analysis_path"),
                    report_path=page.get("report_path")
                )
        
        # Add job_id to the result
        result["job_id"] = job_id
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error during API scrape: {e}")
        
        # Record the error in the database if job was created
        if 'job_id' in locals():
            db_manager.update_scraping_job(
                job_id=job_id,
                status="error",
                metadata={"error": str(e)}
            )
            
        return jsonify({"error": str(e)}), 500

@api.route('/recursive-scrape', methods=['POST'])
@require_api_key
def recursive_scrape():
    """API endpoint for recursive scraping with advanced options."""
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
        
    url = data['url']
    
    # Extract optional configuration from request
    config = {}
    for key in [
        'max_depth', 'max_pages_per_domain', 'max_total_pages', 'headless',
        'page_load_timeout', 'scroll_to_bottom', 'respect_robots_txt',
        'min_request_interval', 'random_delay', 'max_retries',
        'follow_url_patterns', 'exclude_url_patterns', 'required_params',
        'excluded_params', 'strip_url_params', 'min_content_length',
        'stay_on_domain', 'allowed_domains', 'excluded_domains'
    ]:
        if key in data:
            config[key] = data[key]
    
    try:
        # Record job in database
        job_id = db_manager.save_scraping_job(
            url=url,
            job_type="recursive_scrape",
            status="in_progress",
            metadata={"config": config}
        )
        
        # Start timing
        start_time = time.time()
        
        # Run the recursive scrape
        scraper = RecursiveScraper(output_dir=Config.SCRAPE_OUTPUT_DIR, config=config)
        result = scraper.start_crawl(url)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Update job in database
        status = "success" if result.get("status") == "success" else "error"
        db_manager.update_scraping_job(
            job_id=job_id,
            status=status,
            duration=duration,
            metadata={
                "pages_count":