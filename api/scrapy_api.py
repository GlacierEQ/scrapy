"""
Unified Scrapy API - A standardized interface for all scraping operations.

This module provides a comprehensive API for web scraping operations, bringing together
all the capabilities from different scraper implementations into one unified interface.
"""

import os
import logging
import json
import time
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, Blueprint, g
import jwt

from scraping_project.general_webscraper import WebpageScraper
from scraping_project.adaptive_scraper import AdaptiveScraper
from scraping_project.recursive_scraper import RecursiveScraper
from scraping_project.db_manager import DatabaseManager
from scraping_project.config import Config
from scraping_project.memory_manager import get_memory_manager
from visual_builder.builder import VisualScraper
from scraping_project.distributed.task_manager import get_task_manager

# Set up logging
logger = logging.getLogger(__name__)

# Initialize components
db_manager = DatabaseManager()
memory_manager = get_memory_manager()
task_manager = get_task_manager()

# Create Blueprint for API routes
api_bp = Blueprint('api', __name__)

# Secret key for JWT tokens - should be stored securely in production
JWT_SECRET = os.environ.get('JWT_SECRET', 'scrapy_super_secret_key_replace_in_production')

# Set default scraper configurations
DEFAULT_OUTPUT_DIR = Config.SCRAPE_OUTPUT_DIR
MAX_MEMORY_USAGE = 80.0  # Maximum memory usage in percentage

# Authentication and Authorization middleware functions

def generate_api_key() -> str:
    """Generate a unique API key."""
    return str(uuid.uuid4())

def generate_token(api_key: str, expiration: int = 3600) -> str:
    """
    Generate a JWT token for API authentication.
    
    Args:
        api_key: API key to encode in the token
        expiration: Token expiration time in seconds
        
    Returns:
        JWT token as a string
    """
    payload = {
        'api_key': api_key,
        'exp': datetime.utcnow().timestamp() + expiration,
        'iat': datetime.utcnow().timestamp()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify a JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Decoded token payload
        
    Raises:
        jwt.InvalidTokenError: If the token is invalid
    """
    return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])

def require_auth(f):
    """Decorator to require authentication for API endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required', 'code': 'auth_required'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            payload = verify_token(token)
            g.user = payload  # Store user info in Flask's g object
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired', 'code': 'token_expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token', 'code': 'invalid_token'}), 401
        
        # Verify the API key in the database
        api_key = payload.get('api_key')
        if not api_key or not db_manager.validate_api_key(api_key):
            return jsonify({'error': 'Invalid API key', 'code': 'invalid_api_key'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

def require_admin(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user.get('is_admin', False):
            return jsonify({'error': 'Admin privileges required', 'code': 'admin_required'}), 403
        return f(*args, **kwargs)
    
    return decorated

def rate_limit(max_calls: int, period: int = 60):
    """
    Decorator to add rate limiting to API endpoints.
    
    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Time period in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'user'):
                return jsonify({'error': 'Authentication required', 'code': 'auth_required'}), 401
            
            api_key = g.user.get('api_key')
            
            # Check rate limit
            if not db_manager.check_rate_limit(api_key, max_calls, period):
                return jsonify({
                    'error': f'Rate limit exceeded: {max_calls} calls per {period} seconds',
                    'code': 'rate_limit_exceeded'
                }), 429
            
            # Record this API call
            db_manager.record_api_call(api_key)
            
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator

# API Status and Health Endpoints

@api_bp.route('/status', methods=['GET'])
def status():
    """Get API status information."""
    return jsonify({
        'status': 'online',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'system_health': {
            'memory_usage': memory_manager.get_memory_usage(),
            'active_tasks': len(task_manager.get_active_tasks()),
            'queued_tasks': task_manager.get_worker_stats().get('queued_tasks', 0)
        }
    })

@api_bp.route('/health', methods=['GET'])
def health():
    """Basic health check endpoint."""
    return jsonify({'status': 'ok'})

# Authentication Endpoints

@api_bp.route('/auth/generate-key', methods=['POST'])
@require_admin
def generate_key():
    """Generate a new API key (admin only)."""
    data = request.json or {}
    
    user_id = data.get('user_id')
    name = data.get('name', 'API Key')
    permissions = data.get('permissions', ['scrape:standard'])
    
    if not user_id:
        return jsonify({'error': 'user_id is required', 'code': 'missing_user_id'}), 400
    
    # Generate new API key
    api_key = generate_api_key()
    
    # Save to database
    db_manager.create_api_key(
        api_key=api_key,
        user_id=user_id,
        name=name,
        permissions=permissions
    )
    
    return jsonify({
        'api_key': api_key,
        'name': name,
        'permissions': permissions,
        'created_at': datetime.utcnow().isoformat()
    })

@api_bp.route('/auth/token', methods=['POST'])
def get_token():
    """Get a JWT token using API key."""
    data = request.json or {}
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({'error': 'API key is required', 'code': 'missing_api_key'}), 400
    
    # Validate API key
    if not db_manager.validate_api_key(api_key):
        return jsonify({'error': 'Invalid API key', 'code': 'invalid_api_key'}), 403
    
    # Get token expiration from request or use default
    expiration = data.get('expiration', 3600)  # Default 1 hour
    
    # Generate token
    token = generate_token(api_key, expiration)
    
    # Record token generation
    db_manager.record_token_generation(api_key)
    
    return jsonify({
        'access_token': token,
        'token_type': 'Bearer',
        'expires_in': expiration
    })

@api_bp.route('/auth/verify', methods=['GET'])
@require_auth
def verify_auth():
    """Verify authentication credentials."""
    api_key = g.user.get('api_key')
    user_info = db_manager.get_user_by_api_key(api_key)
    
    return jsonify({
        'authenticated': True,
        'user_id': user_info.get('id'),
        'permissions': user_info.get('permissions', [])
    })

# Scraping Endpoints

@api_bp.route('/scrape/simple', methods=['POST'])
@require_auth
@rate_limit(max_calls=20, period=60)
def simple_scrape():
    """
    Perform a simple one-page scrape.
    
    Request body:
    {
        "url": "https://example.com",
        "compile_text": true,
        "screenshot": true,
        "save_html": true,
        "user_agent": "Chrome/98.0",
        "timeout": 30
    }
    """
    data = request.json or {}
    
    # Required parameters
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required', 'code': 'missing_url'}), 400
    
    # Optional parameters
    compile_text = data.get('compile_text', True)
    screenshot = data.get('screenshot', True)
    save_html = data.get('save_html', True)
    user_agent = data.get('user_agent')
    timeout = data.get('timeout', 30)
    
    try:
        # Record task in database
        task_id = db_manager.save_scraping_job(
            url=url,
            job_type='simple_scrape',
            status='in_progress',
            user_id=g.user.get('user_id'),
            metadata={'compile_text': compile_text, 'screenshot': screenshot}
        )
        
        # Set up scraper
        scraper = WebpageScraper(output_dir=DEFAULT_OUTPUT_DIR)
        
        # Set any custom options
        if user_agent:
            scraper.browser.set_user_agent(user_agent)
        
        if timeout:
            scraper.browser.set_timeout(timeout)
        
        # Perform scrape
        result = scraper.save_webpage(
            url=url,
            follow_links=False,
            compile_text=compile_text,
            save_screenshot=screenshot,
            save_html=save_html
        )
        
        # Update task status
        status = 'success' if result.get('status') == 'success' else 'error'
        db_manager.update_scraping_job(
            job_id=task_id,
            status=status,
            metadata={'result': result}
        )
        
        # Add task ID to result
        result['task_id'] = task_id
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in simple scrape: {str(e)}")
        # Update task status if task was created
        if 'task_id' in locals():
            db_manager.update_scraping_job(
                job_id=task_id,
                status='error',
                metadata={'error': str(e)}
            )
        
        return jsonify({
            'status': 'error',
            'error': str(e),
            'code': 'scraping_error'
        }), 500

@api_bp.route('/scrape/recursive', methods=['POST'])
@require_auth
@rate_limit(max_calls=5, period=60)
def recursive_scrape():
    """
    Perform a recursive scrape, starting from a URL and following links.
    
    Request body:
    {
        "url": "https://example.com",
        "max_depth": 2,
        "max_pages": 50,
        "same_domain": true,
        "include_patterns": ["*/blog/*"],
        "exclude_patterns": ["*/author/*"],
        "async": true
    }
    """
    data = request.json or {}
    
    # Required parameters
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required', 'code': 'missing_url'}), 400
    
    # Optional parameters
    max_depth = data.get('max_depth', 2)
    max_pages = data.get('max_pages', 50)
    same_domain = data.get('same_domain', True)
    include_patterns = data.get('include_patterns', [])
    exclude_patterns = data.get('exclude_patterns', [])
    async_task = data.get('async', True)
    
    # Advanced configuration
    config = {
        'max_depth': max_depth,
        'max_pages': max_pages,
        'stay_on_domain': same_domain,
        'follow_url_patterns': include_patterns,
        'exclude_url_patterns': exclude_patterns
    }
    
    # Add any other configuration options
    for key in [
        'respect_robots_txt', 'min_request_interval', 'random_delay', 
        'max_retries', 'allowed_domains', 'excluded_domains'
    ]:
        if key in data:
            config[key] = data[key]
    
    try:
        # Record task in database
        task_id = db_manager.save_scraping_job(
            url=url,
            job_type='recursive_scrape',
            status='in_progress',
            user_id=g.user.get('user_id'),
            metadata={'config': config, 'async': async_task}
        )
        
        if async_task:
            # Submit as an asynchronous task
            job = task_manager.submit_recursive_scrape_task(
                url=url,
                config=config
            )
            
            return jsonify({
                'status': 'accepted',
                'task_id': task_id,
                'job_id': job,
                'message': 'Recursive scrape job submitted successfully',
                'check_url': f'/api/tasks/{task_id}'
            })
        else:
            # Run synchronously
            scraper = RecursiveScraper(output_dir=DEFAULT_OUTPUT_DIR, config=config)
            result = scraper.start_crawl(url)
            
            # Update task status
            status = 'success' if result.get('status') == 'success' else 'error'
            db_manager.update_scraping_job(
                job_id=task_id,
                status=status,
                metadata={'result': result}
            )
            
            # Add task ID to result
            result['task_id'] = task_id
            
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in recursive scrape: {str(e)}")
        # Update task status if task was created
        if 'task_id' in locals():
            db_manager.update_scraping_job(
                job_id=task_id,
                status='error',
                metadata={'error': str(e)}
            )
        
        return jsonify({
            'status': 'error',
            'error': str(e),
            'code': 'scraping_error'
        }), 500

@api_bp.route('/scrape/adaptive', methods=['POST'])
@require_auth
@rate_limit(max_calls=10, period=60)
def adaptive_scrape():
    """
    Perform an adaptive scrape that automatically detects page structure.
    
    Request body:
    {
        "url": "https://example.com",
        "data_type": "auto",
        "use_ai": false,
        "async": true
    }
    """
    data = request.json or {}
    
    # Required parameters
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required', 'code': 'missing_url'}), 400
    
    # Optional parameters
    data_type = data.get('data_type', 'auto')  # auto, product, article, list, table
    use_ai = data.get('use_ai', False)
    async_task = data.get('async', True)
    
    try:
        # Record task in database
        task_id = db_manager.save_scraping_job(
            url=url,
            job_type='adaptive_scrape',
            status='in_progress',
            user_id=g.user.get('user_id'),
            metadata={'data_type': data_type, 'use_ai': use_ai, 'async': async_task}
        )
        
        if async_task:
            # Submit as an asynchronous task
            job = task_manager.submit_adaptive_scrape_task(
                url=url,
                data_type=data_type,
                use_ai=use_ai
            )
            
            return jsonify({
                'status': 'accepted',
                'task_id': task_id,
                'job_id': job,
                'message': 'Adaptive scrape job submitted successfully',
                'check_url': f'/api/tasks/{task_id}'
            })
        else:
            # Run synchronously
            scraper = AdaptiveScraper(output_dir=DEFAULT_OUTPUT_DIR, use_ai=use_ai)
            result = scraper.extract_data(url, data_type=data_type)
            
            # Update task status
            status = 'success' if result.get('status') == 'success' else 'error'
            db_manager.update_scraping_job(
                job_id=task_id,
                status=status,
                metadata={'result': result}
            )
            
            # Add task ID to result
            result['task_id'] = task_id
            
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in adaptive scrape: {str(e)}")
        # Update task status if task was created
        if 'task_id' in locals():
            db_manager.update_scraping_job(
                job_id=task_id,
                status='error',
                metadata={'error': str(e)}
            )
        
        return jsonify({
            'status': 'error',
            'error': str(e),
            'code': 'scraping_error'
        }), 500

@api_bp.route('/visual-builder/start', methods=['POST'])
@require_auth
@rate_limit(max_calls=5, period=60)
def start_visual_builder():
    """
    Start a visual scraper builder session.
    
    Request body:
    {
        "url": "https://example.com",
        "headless": false
    }
    """
    data = request.json or {}
    
    # Required parameters
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required', 'code': 'missing_url'}), 400
    
    # Optional parameters
    headless = data.get('headless', False)
    
    try:
        # Create visual scraper
        visual_scraper = VisualScraper(
            headless=headless,
            output_dir=os.path.join(DEFAULT_OUTPUT_DIR, "visual_builder")
        )
        
        # Start session
        session_info = visual_scraper.start_session(url)
        
        # Record in database
        db_manager.save_visual_builder_session(
            session_id=session_info['session_id'],
            url=url,
            user_id=g.user.get('user_id'),
            metadata={
                'title': session_info.get('title', ''),
                'screenshot_path': session_info.get('screenshot_path', '')
            }
        )
        
        return jsonify({
            'status': 'success',
            'session_id': session_info['session_id'],
            'url': url,
            'title': session_info.get('title', ''),
            'screenshot_url': f"/static/screenshots/{os.path.basename(session_info.get('screenshot_path', ''))}"
        })
    
    except Exception as e:
        logger.error(f"Error starting visual builder session: {str(e)}")
        
        return jsonify({
            'status': 'error',
            'error': str(e),
            'code': 'session_start_error'
        }), 500

# Task Management Endpoints

@api_bp.route('/tasks', methods=['GET'])
@require_auth
def list_tasks():
    """
    List all tasks for the current user.
    
    Query parameters:
    - status: Filter by status (in_progress, success, error)
    - type: Filter by job type
    - limit: Maximum number of tasks to return
    - offset: Pagination offset
    """
    # Get filter parameters
    status = request.args.get('status')
    job_type = request.args.get('type')
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    
    # Get user ID
    user_id = g.user.get('user_id')
    
    # Retrieve tasks
    tasks = db_manager.get_user_tasks(
        user_id=user_id,
        status=status,
        job_type=job_type,
        limit=limit,
        offset=offset
    )
    
    # Count total
    total = db_manager.count_user_tasks(
        user_id=user_id,
        status=status,
        job_type=job_type
    )
    
    return jsonify({
        'tasks': tasks,
        'total': total,
        'limit': limit,
        'offset': offset
    })

@api_bp.route('/tasks/<task_id>', methods=['GET'])
@require_auth
def get_task(task_id):
    """Get details of a specific task."""
    # Get user ID
    user_id = g.user.get('user_id')
    
    # Retrieve task
    task = db_manager.get_task_details(task_id, user_id)
    
    if not task:
        return jsonify({'error': 'Task not found', 'code': 'task_not_found'}), 404
    
    return jsonify(task)

@api_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
@require_auth
def cancel_task(task_id):
    """Cancel a running task."""
    # Get user ID
    user_id = g.user.get('user_id')
    
    # Check if task exists and belongs to user
    task = db_manager.get_task_details(task_id, user_id)
    
    if not task:
        return jsonify({'error': 'Task not found', 'code': 'task_not_found'}), 404
    
    # Can only cancel in-progress tasks
    if task.get('status') != 'in_progress':
        return jsonify({'error': 'Task is not in progress', 'code': 'task_not_in_progress'}), 400
    
    # Try to cancel task
    if task.get('job_id'):
        cancelled = task_manager.cancel_task(task.get('job_id'))
    else:
        cancelled = False
    
    if cancelled:
        # Update task status
        db_manager.update_scraping_job(
            job_id=task_id,
            status='cancelled',
            metadata={'cancelled_at': datetime.utcnow().isoformat()}
        )
        
        return jsonify({
            'status': 'success',
            'task_id': task_id,
            'message': 'Task cancelled successfully'
        })
    else:
        return jsonify({
            'status': 'error',
            'error': 'Failed to cancel task',
            'code': 'cancel_failed'
        }), 500

# Results and Data Management Endpoints

@api_bp.route('/results/<task_id>', methods=['GET'])
@require_auth
def get_results(task_id):
    """Get the results of a completed task."""
    # Get user ID
    user_id = g.user.get('user_id')
    
    # Check if task exists and belongs to user
    task = db_manager.get_task_details(task_id, user_id)
    
    if not task:
        return jsonify({'error': 'Task not found', 'code': 'task_not_found'}), 404
    
    # Check if task is completed
    if task.get('status') != 'success':
        return jsonify({'error': 'Task is not completed', 'code': 'task_not_completed'}), 400
    
    # Get results
    results = db_manager.get_task_results(task_id)
    
    return jsonify({
        'task_id': task_id,
        'status': 'success',
        'results': results
    })

@api_bp.route('/download/<task_id>', methods=['GET'])
@require_auth
def download_results(task_id):
    """
    Download task results in different formats.
    
    Query parameters:
    - format: Format to download (json, csv, html)
    """
    # Get format parameter
    format_type = request.args.get('format', 'json')
    
    # Get user ID
    user_id = g.user.get('user_id')
    
    # Check if task exists and belongs to user
    task = db_manager.get_task_details(task_id, user_id)
    
    if not task:
        return jsonify({'error': 'Task not found', 'code': 'task_not_found'}), 404
    
    # Generate download URL
    try:
        download_url = db_manager.generate_download_url(task_id, format_type)
        
        return jsonify({
            'task_id': task_id,
            'format': format_type,
            'download_url': download_url,
            'expires_in': 3600  # URL expires in 1 hour
        })
    except Exception as e:
        logger.error(f"Error generating download URL: {str(e)}")
        
        return jsonify({
            'status': 'error',
            'error': str(e),
            'code': 'download_error'
        }), 500

# Initialize the application
def init_app(app):
    """Initialize the Flask application with API routes and configuration."""
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found', 'code': 'not_found'}), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'error': 'Method not allowed', 'code': 'method_not_allowed'}), 405
    
    @app.errorhandler(500)
    def server_error(error):
        return jsonify({'error': 'Internal server error', 'code': 'server_error'}), 500
    
    return app

# Create application instance
def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configure app
    app.config.update(
        JSON_SORT_KEYS=False,
        PROPAGATE_EXCEPTIONS=True
    )
    
    # Initialize with API routes
    return init_app(app)

# Run the application directly when script is executed
if __name__ == '__main__':
    app = create_app()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=8000)
