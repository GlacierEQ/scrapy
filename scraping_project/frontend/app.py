from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
import sys
import os
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hawaii_jefs_scraper import scrape_hawaii_jefs
from general_webscraper import WebpageScraper
from image_generator import ImageGenerator
from config import Config

app = Flask(__name__, static_folder='static')

# Configure the output directory for the general scraper
SCRAPE_OUTPUT_DIR = Config.SCRAPE_OUTPUT_DIR

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

@app.route('/api/settings', methods=['GET', 'POST'])
def settings_api():
    if request.method == 'POST':
        try:
            settings_data = request.get_json()
            for key, value in settings_data.items():
                if hasattr(Config, key):
                    if isinstance(getattr(Config, key), int):
                        try:
                            value = int(value)
                        except (TypeError, ValueError):
                            return jsonify({
                                "success": False,
                                "message": f"Invalid value for {key}: must be an integer"
                            }), 400
                    setattr(Config, key, value)
            
            Config.save_to_file(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'local_config.py'))
            return jsonify({"success": True, "message": "Settings saved successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Error saving settings: {str(e)}"}), 500
    
    # GET request - return current settings
    try:
        settings = {
            key: getattr(Config, key) 
            for key in dir(Config) 
            if not key.startswith('__') and not callable(getattr(Config, key))
        }
        return jsonify({"success": True, "data": settings})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error loading settings: {str(e)}"}), 500

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return jsonify({"success": False, "message": "Username and password are required"}), 400
        
        # Add timestamp to track scraping duration
        start_time = time.time()
        result = scrape_hawaii_jefs(username, password)
        duration = round(time.time() - start_time, 2)
        
        if result["status"] == "success":
            # Add metadata to the result
            result["data"]["metadata"] = {
                "timestamp": datetime.now().isoformat(),
                "duration": f"{duration} seconds",
                "source": "Hawaii JEFS"
            }
            
            return jsonify({
                "success": True,
                "message": f"Scraping completed in {duration} seconds!",
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
        url = request.form.get('url')
        follow_links = request.form.get('followLinks') == 'true'
        compile_text = request.form.get('compileText') == 'true'
        
        if not url:
            return jsonify({"success": False, "message": "URL is required"}), 400
        
        # Add timestamp to track scraping duration
        start_time = time.time()
        
        # Initialize scraper with current settings
        scraper = WebpageScraper(output_dir=SCRAPE_OUTPUT_DIR)
        result = scraper.save_webpage(
            url=url,
            follow_links=follow_links,
            compile_text=compile_text,
            max_pages=Config.MAX_PAGES
        )
        
        duration = round(time.time() - start_time, 2)
        
        if result["status"] == "success":
            # Add metadata
            result["data"]["metadata"] = {
                "timestamp": datetime.now().isoformat(),
                "duration": f"{duration} seconds",
                "url": url,
                "settings": {
                    "follow_links": follow_links,
                    "compile_text": compile_text,
                    "max_pages": Config.MAX_PAGES
                }
            }
            
            # Process paths to be relative
            for page in result["data"]["pages"]:
                # Add timestamp to each page
                page["timestamp"] = datetime.now().isoformat()
                
                for key in ["screenshot_path", "html_path", "analysis_path", "report_path"]:
                    if key in page:
                        page[key] = os.path.relpath(page[key], SCRAPE_OUTPUT_DIR)
            
            if result["data"].get("compiled_report"):
                result["data"]["compiled_report"] = os.path.relpath(
                    result["data"]["compiled_report"],
                    SCRAPE_OUTPUT_DIR
                )
            
            # Generate images if enabled
            if Config.ENABLE_IMAGE_GENERATION:
                try:
                    generator = ImageGenerator()
                    for page in result["data"]["pages"]:
                        if page.get("analysis"):
                            # Generate image based on page content
                            keywords = page["analysis"]["text_statistics"]["most_common_words"]
                            prompt = f"Webpage visualization: {', '.join(list(keywords.keys())[:5])}"
                            image_path = generator.generate_from_text(prompt)
                            if image_path:
                                page["generated_image"] = os.path.relpath(image_path, SCRAPE_OUTPUT_DIR)
                except Exception as e:
                    print(f"Image generation error: {e}")
            
            return jsonify({
                "success": True,
                "message": f"Analysis completed in {duration} seconds!",
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

@app.route('/download/<path:filename>')
def download_file(filename):
    """Download any file from the output directory"""
    try:
        return send_file(
            os.path.join(SCRAPE_OUTPUT_DIR, filename),
            as_attachment=True
        )
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error downloading file: {str(e)}"
        }), 404

@app.route('/view/<path:filename>')
def view_file(filename):
    """View any file from the output directory"""
    try:
        return send_from_directory(SCRAPE_OUTPUT_DIR, filename)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error viewing file: {str(e)}"
        }), 404

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "success": False,
        "message": "Resource not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "Internal server error"
    }), 500

if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs(SCRAPE_OUTPUT_DIR, exist_ok=True)
    os.makedirs(Config.IMAGE_OUTPUT_DIR, exist_ok=True)
    
    # Create static directories if they don't exist
    os.makedirs(os.path.join(app.static_folder, 'css'), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, 'js'), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, 'img'), exist_ok=True)
    
    app.run(debug=True)
