from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import request, redirect, url_for, session, flash, g
import jwt
import datetime
import logging
from typing import Callable, Dict, Any, Optional

class AuthManager:
    """
    Authentication manager for handling user authentication and authorization.
    """
    
    def __init__(self, db_manager, secret_key):
        """Initialize with a database manager and secret key."""
        self.db_manager = db_manager
        self.secret_key = secret_key
        self.logger = logging.getLogger(__name__)
        
    def register_user(self, username: str, password: str, email: str = None, 
                     is_admin: bool = False) -> int:
        """Register a new user."""
        # Check if user already exists
        existing_user = self.db_manager.get_user_by_username(username)
        if existing_user:
            raise ValueError("Username already exists")
        
        # Hash the password
        password_hash = generate_password_hash(password)
        
        # Add user to database
        user_id = self.db_manager.add_user(
            username=username, 
            password_hash=password_hash,
            email=email,
            is_admin=is_admin
        )
        
        self.logger.info(f"Registered new user: {username}")
        return user_id
    
    def authenticate_user(self, username: str, password: str) -> Dict:
        """Authenticate a user and return user info if successful."""
        user = self.db_manager.get_user_by_username(username)
        
        if not user or not check_password_hash(user['password_hash'], password):
            self.logger.warning(f"Failed login attempt for username: {username}")
            return None
        
        # Update last login time
        self.db_manager.update_user_last_login(user['id'])
        
        # Return user info without password hash
        user_info = {k: v for k, v in user.items() if k != 'password_hash'}
        self.logger.info(f"User authenticated: {username}")
        return user_info
    
    def generate_token(self, user_id: int, username: str, 
                      expiry_minutes: int = 60) -> str:
        """Generate JWT token for authenticated user."""
        expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=expiry_minutes)
        
        payload = {
            'exp': expiry,
            'iat': datetime.datetime.utcnow(),
            'sub': user_id,
            'username': username
        }
        
        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm='HS256'
        )
        
        return token
    
    def verify_token(self, token: str) -> Dict:
        """Verify the JWT token and return user data if valid."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return {
                'user_id': payload['sub'],
                'username': payload['username'],
                'exp': payload['exp']
            }
        except jwt.ExpiredSignatureError:
            self.logger.warning("Expired token")
            return None
        except jwt.InvalidTokenError:
            self.logger.warning("Invalid token")
            return None
    
    def login_required(self, f: Callable) -> Callable:
        """Decorator to require login for a route."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            
            # Check for token in headers
            if 'Authorization' in request.headers:
                auth_header = request.headers['Authorization']
                if auth_header.startswith('Bearer '):
                    token = auth_header.split('Bearer ')[1]
            
            # Check for token in session
            if not token and 'token' in session:
                token = session['token']
                
            # Check for token in cookies
            if not token and 'token' in request.cookies:
                token = request.cookies.get('token')
            
            if not token:
                flash('Login required')
                return redirect(url_for('login', next=request.url))
            
            user_data = self.verify_token(token)
            if not user_data:
                flash('Invalid or expired token. Please log in again.')
                return redirect(url_for('login', next=request.url))
            
            # Add user data to Flask's g object for use in the route
            g.user = user_data
            
            return f(*args, **kwargs)
        return decorated_function
    
    def admin_required(self, f: Callable) -> Callable:
        """Decorator to require admin rights for a route."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # First check if logged in
            token = None
            
            if 'Authorization' in request.headers:
                auth_header = request.headers['Authorization']
                if auth_header.startswith('Bearer '):
                    token = auth_header.split('Bearer ')[1]
            
            if not token and 'token' in session:
                token = session['token']
                
            if not token and 'token' in request.cookies:
                token = request.cookies.get('token')
            
            if not token:
                flash('Login required')
                return redirect(url_for('login', next=request.url))
            
            user_data = self.verify_token(token)
            if not user_data:
                flash('Invalid or expired token. Please log in again.')
                return redirect(url_for('login', next=request.url))
            
            # Check if user is admin
            user = self.db_manager.get_user_by_username(user_data['username'])
            if not user or not user.get('is_admin'):
                flash('Admin rights required')
                return redirect(url_for('dashboard'))
            
            # Add user data to Flask's g object for use in the route
            g.user = user_data
            
            return f(*args, **kwargs)
        return decorated_function
