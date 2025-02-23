from flask import Flask, render_template, request, jsonify, send_from_directory
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hawaii_jefs_scraper import scrape_hawaii_jefs
from general_webscraper import WebpageScraper

app = Flask(__name__)

# Configure the output directory for the general scraper
SCRAPE_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scraped_pages')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            return jsonify({"success": False, "message": "Username and password are required"}), 400
        
        result = scrape_hawaii_jefs(username, password)
        
        if result["status"] == "success":
            return jsonify({
                "success": True,
                "message": "Scraping completed successfully!",
                "data": result["data"]
            })
        else:
            return jsonify({
                "success": False,
                "message": result["message"]
            }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        }), 500

@app.route('/scrape_general', methods=['POST'])
def scrape_general():
    try:
        url = request.form['url']
        
        if not url:
            return jsonify({"success": False, "message": "URL is required"}), 400
        
        scraper = WebpageScraper(output_dir=SCRAPE_OUTPUT_DIR)
        result = scraper.save_webpage(url)
        
        if result["status"] == "success":
            return jsonify({
                "success": True,
                "message": "Webpage captured successfully!",
                "data": {
                    "screenshot_path": result["data"]["screenshot_path"],
                    "html_path": result["data"]["html_path"],
                    "timestamp": result["data"]["timestamp"]
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": result["message"]
            }), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        }), 500

@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    """Serve screenshot files"""
    return send_from_directory(SCRAPE_OUTPUT_DIR, filename)

if __name__ == "__main__":
    os.makedirs(SCRAPE_OUTPUT_DIR, exist_ok=True)
    app.run(debug=True)
