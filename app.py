from flask import Flask, request, redirect, jsonify, Response, render_template, copy_current_request_context, g
import string
import random
import re
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from urllib.parse import urlparse
from queue import Queue
import json
from threading import Event, Thread
from time import sleep
import logging
from logging.handlers import RotatingFileHandler
import os.path
from cryptography.fernet import Fernet
import base64

import os

# Initialize Flask app
app = Flask(__name__)
app.template_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))

# Check if we should force SQLite usage
if os.environ.get('USE_SQLITE') == 'True':
    # Force SQLite for local development
    sqlite_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'url_shortener.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
    print(f"Using SQLite database at: {sqlite_path}")
# Otherwise use the DATABASE_URL if provided
elif os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    print(f"Using database from DATABASE_URL")
# Default to SQLite
else:
    # Use SQLite for local development
    sqlite_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'url_shortener.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
    print(f"Using default SQLite database at: {sqlite_path}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TESTING'] = os.environ.get('TESTING', 'False') == 'True'

# Configure main application logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure request logger
request_logger = logging.getLogger('request_logger')
request_logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Set up file handler for request logs
request_log_file = os.path.join(logs_dir, 'request_logs.log')
request_file_handler = RotatingFileHandler(request_log_file, maxBytes=10485760, backupCount=10)  # 10MB per file, keep 10 files
request_file_handler.setLevel(logging.INFO)

# Create a formatter for the logs
request_formatter = logging.Formatter('%(asctime)s - %(message)s')
request_file_handler.setFormatter(request_formatter)

# Add the handler to the logger
request_logger.addHandler(request_file_handler)

db = SQLAlchemy(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# List of routes to log
LOGGED_ROUTES = [
    '/shorten',       # Log the URL shortening endpoint
    '/redirect',      # Log the URL redirection endpoint
    '/edit',          # Log the URL editing endpoint
    '/delete',        # Log the URL deletion endpoint
    '/shorten/batch'  # Log the batch URL shortening endpoint
]

# Function to check if the current route should be logged
def should_log_route(path):
    # Check if the path starts with any of the routes in LOGGED_ROUTES
    for route in LOGGED_ROUTES:
        if path.startswith(route):
            return True
    return False

# List of routes that require API key authentication
API_KEY_REQUIRED_ROUTES = {
    '/shorten',
    '/shorten/batch',
    '/delete',
    '/edit',
    '/user/urls',
    '/user/tier/update'
}

# List of methods that require authentication for the above routes
AUTH_REQUIRED_METHODS = {'POST', 'PUT', 'DELETE', 'PATCH'}

# Routes that are exempt from API key validation even if they match the prefixes above
AUTH_EXEMPT_ROUTES = {
    '/shorten/docs',  # Documentation routes
    '/api/health'     # Health check routes
}

# List of routes that require enterprise tier
ENTERPRISE_TIER_ROUTES = {
    '/shorten/batch',  # Batch URL shortening
    '/analytics/advanced',  # Advanced analytics (future feature)
    '/api/v2'  # Future API endpoints
}

# Function to check if the current route requires API key validation
def requires_api_key(path, method):
    # Skip API key validation for exempt routes
    for exempt_route in AUTH_EXEMPT_ROUTES:
        if path.startswith(exempt_route):
            return False
    
    # Check if the path requires authentication
    for protected_route in API_KEY_REQUIRED_ROUTES:
        if path.startswith(protected_route):
            # For these routes, only certain methods require authentication
            if method in AUTH_REQUIRED_METHODS:
                return True
    
    return False

# Function to check if the current route requires enterprise tier
def requires_enterprise_tier(path):
    # Check if the path requires enterprise tier
    for enterprise_route in ENTERPRISE_TIER_ROUTES:
        if path.startswith(enterprise_route):
            return True
    return False

# Path to the blacklist configuration file
BLACKLIST_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'blacklist.json')

# Cache for blacklisted API keys and IPs
blacklist_cache = {
    'api_keys': set(),
    'ips': set(),
    'last_loaded': None
}

# Allow tests to override the blacklist path
def get_blacklist_path():
    """Get the path to the blacklist configuration file.
    
    This function allows tests to override the blacklist path by setting
    app.config['BLACKLIST_CONFIG_PATH'].
    """
    if app.config.get('BLACKLIST_CONFIG_PATH'):
        return app.config.get('BLACKLIST_CONFIG_PATH')
    return BLACKLIST_CONFIG_PATH

# Function to load the blacklist from the configuration file
def load_blacklist(force_reload=False):
    """Load the blacklist from the configuration file.
    
    Args:
        force_reload (bool): If True, reload the blacklist even if it was recently loaded.
        
    Returns:
        dict: A dictionary containing blacklisted API keys and IPs.
    """
    global blacklist_cache
    
    # Check if we need to reload the blacklist
    current_time = datetime.utcnow()
    if not force_reload and blacklist_cache['last_loaded'] and \
       (current_time - blacklist_cache['last_loaded']).total_seconds() < 60:
        # Use cached blacklist if it was loaded less than 60 seconds ago
        return blacklist_cache
    
    try:
        # Get the blacklist path (allows for testing override)
        blacklist_path = get_blacklist_path()
        
        # Create the config directory if it doesn't exist
        os.makedirs(os.path.dirname(blacklist_path), exist_ok=True)
        
        # Create the blacklist file with default values if it doesn't exist
        if not os.path.exists(blacklist_path):
            default_blacklist = {
                "blacklisted_api_keys": [],
                "blacklisted_ips": [],
                "last_updated": datetime.utcnow().isoformat(),
                "notes": "This file contains blacklisted API keys and IPs. Add entries to block abusive users."
            }
            with open(blacklist_path, 'w') as f:
                json.dump(default_blacklist, f, indent=2)
        
        # Load the blacklist from the file
        with open(blacklist_path, 'r') as f:
            blacklist_data = json.load(f)
        
        # Update the cache
        blacklist_cache['api_keys'] = set(blacklist_data.get('blacklisted_api_keys', []))
        blacklist_cache['ips'] = set(blacklist_data.get('blacklisted_ips', []))
        blacklist_cache['last_loaded'] = current_time
        
        app.logger.info(f"Loaded blacklist with {len(blacklist_cache['api_keys'])} API keys and {len(blacklist_cache['ips'])} IPs")
        return blacklist_cache
    except Exception as e:
        app.logger.error(f"Error loading blacklist: {str(e)}")
        # Return the current cache if there's an error
        return blacklist_cache

    # Blacklist middleware
    @app.before_request
    def check_blacklist():
        """Check if the request's API key or IP is blacklisted."""
        # Skip for OPTIONS requests (pre-flight CORS requests)
        if request.method == 'OPTIONS':
            return None
        
        # Load the blacklist
        blacklist = load_blacklist()
        
        # Check if the API key is blacklisted
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key in blacklist['api_keys']:
            app.logger.warning(f"Blocked request with blacklisted API key: {api_key[:5]}...")
            return jsonify({
                'error': 'Your API key has been blacklisted. Please contact support for assistance.',
                'code': 'BLACKLISTED_API_KEY'
            }), 403
        
        # Check if the IP is blacklisted
        if request.headers.getlist("X-Forwarded-For"):
            ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip = request.remote_addr
        
        if ip in blacklist['ips']:
            app.logger.warning(f"Blocked request from blacklisted IP: {ip}")
            return jsonify({
                'error': 'Your IP address has been blacklisted. Please contact support for assistance.',
                'code': 'BLACKLISTED_IP'
            }), 403

# Response time middleware
@app.before_request
def start_timer():
    """Store the start time of the request."""
    g.start_time = datetime.utcnow()

@app.after_request
def add_response_time(response):
    """Calculate response time and add it to response headers."""
    # Check if we have a start time
    if hasattr(g, 'start_time'):
        # Calculate response time in milliseconds
        response_time = (datetime.utcnow() - g.start_time).total_seconds() * 1000
        # Add response time to headers (rounded to 2 decimal places)
        response.headers['X-Response-Time'] = f"{response_time:.2f}ms"
        # Log response time for monitoring
        app.logger.debug(f"Response time: {response_time:.2f}ms for {request.method} {request.path}")
    return response

# API key validation middleware
@app.before_request
def validate_api_key():
    # Skip for OPTIONS requests (pre-flight CORS requests)
    if request.method == 'OPTIONS':
        return None
    
    # Extract path from URL
    parsed_url = urlparse(request.url)
    path = parsed_url.path
    
    # Check if this route requires API key validation
    if requires_api_key(path, request.method):
        # Get API key from request headers
        api_key = request.headers.get('X-API-Key')
        
        # Get user from API key
        user = get_user_from_api_key(api_key)
        
        # If no valid user found, return error response
        if not user:
            return jsonify({'error': 'Invalid or missing API key'}), 401
        
        # Store user in Flask's g object for the route handler to use
        g.user = user

# Enterprise tier authorization middleware
@app.before_request
def validate_enterprise_tier():
    # Skip if no user is authenticated yet
    if not hasattr(g, 'user'):
        return None
    
    # Extract path from URL
    parsed_url = urlparse(request.url)
    path = parsed_url.path
    
    # Check if this route requires enterprise tier
    if requires_enterprise_tier(path):
        user = g.user
        
        # Check if the user has the enterprise tier
        if user.pricing_tier != 'enterprise':
            return jsonify({
                'error': 'Access denied. This feature is only available for enterprise tier users.',
                'current_tier': user.pricing_tier,
                'required_tier': 'enterprise'
            }), 403

# Request logging middleware
@app.before_request
def log_request_info():
    # Get the start time for the request
    g.start_time = datetime.utcnow()
    
    # Extract path from URL
    parsed_url = urlparse(request.url)
    path = parsed_url.path
    
    # Only log specific routes
    if should_log_route(path):
        # Get client IP address
        if request.headers.getlist("X-Forwarded-For"):
            # If behind a proxy, get the real IP
            ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip = request.remote_addr
        
        # Log the request details to file
        request_logger.info(
            f"IP: {ip} | "
            f"Method: {request.method} | "
            f"URL: {request.url} | "
            f"Path: {path} | "
            f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
        )
        
        # Mark this request for logging in the database
        g.should_log = True
    else:
        # Don't log this request
        g.should_log = False

# Enable CORS for SSE
@app.after_request
def after_request(response):
    # Add CORS headers
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    
    # Only log if we have a start time and this request should be logged
    if hasattr(g, 'start_time') and hasattr(g, 'should_log') and g.should_log:
        # Calculate response time
        response_time = datetime.utcnow() - g.start_time
        response_time_seconds = response_time.total_seconds()
        
        # Log to file
        request_logger.info(f"Response time: {response_time_seconds:.3f}s | Status: {response.status_code}")
        
        # Get client IP address
        if request.headers.getlist("X-Forwarded-For"):
            ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip = request.remote_addr
        
        # Extract path from URL
        parsed_url = urlparse(request.url)
        path = parsed_url.path
        
        try:
            # Create database log entry
            log_entry = RequestLog(
                timestamp=g.start_time,
                method=request.method,
                url=request.url,
                path=path,
                user_agent=request.headers.get('User-Agent'),
                ip_address=ip,
                status_code=response.status_code,
                response_time=response_time_seconds
            )
            
            # Add to session and commit
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # If there's an error saving to the database, log it but don't break the request
            logger.error(f"Error saving request log to database: {str(e)}")
            db.session.rollback()
    
    return response

# Queue for SSE events
url_events = Queue()

# Use a fixed key for encryption to match the one used in the migration
# In production, this should be stored securely and loaded from environment variables
SECRET_KEY = os.environ.get('ENCRYPTION_KEY', b'cThIIoDvpK8fCZSZlOveI7eVQYBRDYHWUUZCraMJwT4=')
cipher_suite = Fernet(SECRET_KEY)

def encrypt_api_key(key):
    """Encrypt an API key."""
    return cipher_suite.encrypt(key.encode())

def decrypt_api_key(encrypted_key):
    """Decrypt an API key."""
    return cipher_suite.decrypt(encrypted_key).decode()

def generate_api_key(length=32):
    """Generate a random API key."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pricing_tier = db.Column(db.String, default='hobby', nullable=False)  # 'hobby' or 'enterprise'
    role = db.Column(db.String, default='user', nullable=False)  # 'user', 'admin', etc.

    def __repr__(self):
        return f'<User {self.email}>'

class URL(db.Model):
    __tablename__ = 'urls'  # Explicitly set the table name
    
    short_code = db.Column(db.String(6), primary_key=True)
    original_url = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    click_count = db.Column(db.Integer, default=0)
    last_accessed_at = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)  # New field for URL expiration
    timeout_seconds = db.Column(db.Integer, nullable=True)  # New field for URL timeout in seconds
    password = db.Column(db.String, nullable=True)  # New field for password protection
    
    # Define the relationship with the User model
    user = db.relationship('User', backref=db.backref('urls', lazy=True))
    
    @property
    def is_expired(self):
        """Check if the URL has expired."""
        if self.expiry_date is None:
            return False
        return datetime.utcnow() > self.expiry_date
        
    @property
    def is_timed_out(self):
        """Check if the URL has timed out based on the last access time."""
        if self.timeout_seconds is None or self.last_accessed_at is None:
            return False
        # Calculate the time difference between now and last access
        time_diff = (datetime.utcnow() - self.last_accessed_at).total_seconds()
        return time_diff > self.timeout_seconds

    def __repr__(self):
        return f'<URL {self.short_code}>'

class APIKey(db.Model):
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    encrypted_key = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Define the relationship with the User model
    user = db.relationship('User', backref=db.backref('api_keys', lazy=True))
    
    @property
    def key(self):
        """Decrypt and return the API key."""
        return decrypt_api_key(self.encrypted_key)
    
    @key.setter
    def key(self, value):
        """Encrypt and store the API key."""
        self.encrypted_key = encrypt_api_key(value)
    
    def __repr__(self):
        return f'<APIKey {self.id}>'

class RequestLog(db.Model):
    __tablename__ = 'request_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    method = db.Column(db.String(10), nullable=False)  # GET, POST, PUT, DELETE, etc.
    url = db.Column(db.String(2048), nullable=False)   # Full URL including query parameters
    path = db.Column(db.String(1024), nullable=False)  # URL path without query parameters
    user_agent = db.Column(db.String(1024), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6 address
    status_code = db.Column(db.Integer, nullable=True)  # HTTP status code of the response
    response_time = db.Column(db.Float, nullable=True)  # Response time in seconds
    
    def __repr__(self):
        return f'<RequestLog {self.id} - {self.method} {self.path}>'

def init_db():
    """Initialize the database with sample data."""
    # Create tables if they don't exist
    db.create_all()
    
    # Create sample users if they don't exist
    try:
        if User.query.count() == 0:
            # Create hobby tier users
            hobby_users = [
                User(email='user1@example.com', name='User One', pricing_tier='hobby'),
                User(email='user2@example.com', name='User Two', pricing_tier='hobby'),
                User(email='user3@example.com', name='User Three', pricing_tier='hobby')
            ]
            db.session.add_all(hobby_users)
            
            # Create an enterprise tier user
            enterprise_user = User(email='enterprise@example.com', name='Enterprise User', pricing_tier='enterprise')
            db.session.add(enterprise_user)
            
            db.session.commit()
            
            # Create API keys for all users
            for user in User.query.all():
                api_key = APIKey(user_id=user.id)
                api_key.key = generate_api_key()  # This will trigger the encryption via the setter
                db.session.add(api_key)
                app.logger.info(f'Created API key for user: {user.email} (tier: {user.pricing_tier}) with API key: {api_key.key}')
            db.session.commit()
    except Exception as e:
        app.logger.error(f"Error initializing database: {str(e)}")
        db.session.rollback()

# Initialize the database when running the app directly
if __name__ == '__main__':
    with app.app_context():
        init_db()
        
        # Log the API keys for the client
        for user in User.query.all():
            app.logger.info(f'Created user: {user.email}')

def generate_short_code(length=6):
    """Generate a random short code for URLs."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def validate_and_create_url(url_data, user_id):
    """Validate URL data and create a URL object.
    
    Args:
        url_data (dict): Dictionary containing URL data (url, custom_code, expiry_date, timeout_seconds, password)
        user_id (int): User ID to associate with the URL
        
    Returns:
        tuple: (URL object, error_response)
            If successful, URL object is returned and error_response is None
            If error, URL object is None and error_response is a tuple (error_message, status_code)
    """
    # Extract and validate original URL
    original_url = url_data.get('url')
    if not original_url or not original_url.strip():
        return None, ({'error': 'URL cannot be empty'}, 400)
    
    # Validate the URL format
    parsed_url = urlparse(original_url)
    if not parsed_url.scheme or not parsed_url.netloc:
        return None, ({'error': 'Invalid URL format'}, 400)
    
    # Process optional expiry date
    expiry_date_str = url_data.get('expiry_date')
    expiry_date = None
    if expiry_date_str:
        try:
            # Parse ISO format date string (e.g., '2025-12-31T23:59:59')
            expiry_date = datetime.fromisoformat(expiry_date_str)
            
            # Check if expiry date is in the past
            if expiry_date <= datetime.utcnow():
                return None, ({'error': 'Expiry date must be in the future'}, 400)
        except ValueError:
            return None, ({'error': 'Invalid expiry date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}, 400)
    
    # Process optional timeout
    timeout_seconds = url_data.get('timeout_seconds')
    if timeout_seconds is not None:
        try:
            timeout_seconds = int(timeout_seconds)
            if timeout_seconds <= 0:
                return None, ({'error': 'Timeout must be a positive integer'}, 400)
        except ValueError:
            return None, ({'error': 'Timeout must be a valid integer'}, 400)
    
    # Process optional custom code
    custom_code = url_data.get('custom_code')
    if custom_code:
        # Validate custom code format (alphanumeric and hyphens only)
        if not re.match(r'^[a-zA-Z0-9-]{1,6}$', custom_code):
            return None, ({'error': 'Custom code must be 1-6 alphanumeric characters or hyphens'}, 400)
            
        # Check if the custom code already exists
        if URL.query.filter_by(short_code=custom_code).first():
            return None, ({'error': 'Custom code already in use'}, 409)  # 409 Conflict
            
        short_code = custom_code
    else:
        # Generate a new short code for every URL, even if it already exists
        short_code = generate_short_code()
        while URL.query.filter_by(short_code=short_code).first():
            short_code = generate_short_code()
    
    # Process optional password
    password = url_data.get('password')
    
    # Create the URL object
    new_url = URL(
        short_code=short_code, 
        original_url=original_url, 
        user_id=user_id,
        expiry_date=expiry_date,
        timeout_seconds=timeout_seconds,
        password=password
    )
    
    return new_url, None

def format_url_response(url):
    """Format a URL object into a response dictionary.
    
    Args:
        url (URL): URL object to format
        
    Returns:
        dict: Formatted response dictionary
    """
    return {
        'short_code': url.short_code,
        'original_url': url.original_url,
        'short_url': f'http://localhost:5002/redirect?code={url.short_code}',
        'expiry_date': url.expiry_date.isoformat() if url.expiry_date else None,
        'timeout_seconds': url.timeout_seconds,
        'is_password_protected': bool(url.password),
        # Don't return the actual password in the response for security reasons
    }

def get_user_from_api_key(api_key):
    """Get user from API key."""
    if not api_key:
        return None
    
    # Since we can't directly query by the decrypted key, we need to fetch all active keys
    # and check each one
    api_keys = APIKey.query.filter_by(is_active=True).all()
    for key_record in api_keys:
        try:
            if key_record.key == api_key:
                # Update last_used_at timestamp
                key_record.last_used_at = datetime.utcnow()
                db.session.commit()
                return key_record.user
        except Exception as e:
            # If decryption fails for any reason, skip this key
            app.logger.error(f"Error decrypting key: {str(e)}")
            continue
    
    return None

@app.route('/analytics')
def analytics_page():
    """Serve the analytics dashboard."""
    logger.info(f'Template folder: {app.template_folder}')
    try:
        return render_template('analytics.html')
    except Exception as e:
        logger.error(f'Error rendering template: {str(e)}')
        return jsonify({'error': 'Failed to load analytics page'}), 500

@app.route('/shorten', methods=['POST'])
def shorten_url():
    """Shorten a given URL and return the short code."""
    # User is already validated and available in g.user thanks to the middleware
    user = g.user
    
    # Use the refactored validation and creation function
    new_url, error = validate_and_create_url(request.json, user.id)
    if error:
        return jsonify(error[0]), error[1]
    
    try:
        db.session.add(new_url)
        db.session.commit()

        # Add event to queue for SSE
        event_data = {
            'short_code': new_url.short_code,
            'original_url': new_url.original_url,
            'created_at': new_url.created_at.isoformat()
        }
        url_events.put(event_data)
        app.logger.info(f'Added event to queue: {event_data}')
    except Exception as e:
        app.logger.error(f'Error in shorten_url: {str(e)}')
        db.session.rollback()
        raise

    # Format the response using the helper function
    response_data = format_url_response(new_url)
    return jsonify(response_data)


@app.route('/shorten/batch', methods=['POST'])
def shorten_urls_batch():
    """Shorten multiple URLs in a single request.
    
    This endpoint allows enterprise tier users to create multiple short URLs in a single request.
    It accepts a list of URL objects, each with the same parameters as the single URL endpoint.
    
    Enterprise tier authorization is handled by the validate_enterprise_tier middleware.
    """
    # User is already validated and available in g.user thanks to the middleware
    # Enterprise tier validation is also handled by middleware
    user = g.user
    
    # Get the list of URL data from the request
    urls_data = request.json.get('urls')
    if not urls_data or not isinstance(urls_data, list):
        return jsonify({'error': 'Request must include a list of URLs under the "urls" key'}), 400
    
    if len(urls_data) > 100:  # Limit batch size to prevent abuse
        return jsonify({'error': 'Batch size cannot exceed 100 URLs'}), 400
    
    # Process each URL in the batch
    results = []
    successful_urls = []
    
    for url_data in urls_data:
        # Validate and create the URL
        new_url, error = validate_and_create_url(url_data, user.id)
        
        if error:
            # Add the error to the results
            results.append({
                'original_url': url_data.get('url', 'Invalid URL'),
                'success': False,
                'error': error[0]['error'],
                'status_code': error[1]
            })
        else:
            # Add the URL to the list of successful URLs
            successful_urls.append(new_url)
            
            # Add a success result
            results.append({
                'original_url': new_url.original_url,
                'success': True,
                'short_code': new_url.short_code,
                'short_url': f'http://localhost:5002/redirect?code={new_url.short_code}',
                'expiry_date': new_url.expiry_date.isoformat() if new_url.expiry_date else None,
                'timeout_seconds': new_url.timeout_seconds,
                'is_password_protected': bool(new_url.password)
            })
    
    # Commit all successful URLs to the database
    if successful_urls:
        try:
            db.session.add_all(successful_urls)
            db.session.commit()
            
            # Add events to queue for SSE
            for url in successful_urls:
                event_data = {
                    'short_code': url.short_code,
                    'original_url': url.original_url,
                    'created_at': url.created_at.isoformat()
                }
                url_events.put(event_data)
                
        except Exception as e:
            app.logger.error(f'Error in shorten_urls_batch: {str(e)}')
            db.session.rollback()
            # Mark all URLs as failed due to database error
            for i, result in enumerate(results):
                if result['success']:
                    results[i] = {
                        'original_url': result['original_url'],
                        'success': False,
                        'error': 'Database error occurred while saving URLs',
                        'status_code': 500
                    }
    
    # Return the results
    response_data = {
        'total': len(urls_data),
        'successful': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'results': results
    }
    
    # Determine the appropriate status code
    # 200 if all succeeded, 207 if partial success, 400 if all failed
    status_code = 200
    if response_data['failed'] > 0:
        if response_data['successful'] > 0:
            status_code = 207  # Multi-Status
        else:
            status_code = 400  # Bad Request
    
    return jsonify(response_data), status_code

@app.route('/redirect', methods=['GET'])
def redirect_to_url():
    """Redirect to the original URL based on the short code.
    
    If the URL is password-protected, the request must include the correct password
    as a query parameter to access the original URL.
    """
    short_code = request.args.get('code')
    if not short_code:
        return jsonify({'error': 'Short code is required'}), 400

    url = URL.query.filter_by(short_code=short_code).first()

    if not url or url.is_deleted:
        return jsonify({'error': 'URL not found'}), 404
        
    # Check if the URL has expired
    if url.is_expired:
        return jsonify({'error': 'URL has expired'}), 410  # 410 Gone is appropriate for expired content
        
    # Check if the URL has timed out
    if url.is_timed_out:
        return jsonify({'error': 'URL has timed out due to inactivity'}), 410  # 410 Gone is also appropriate for timed out content
    
    # Check if the URL is password-protected
    if url.password:
        # Get password from request
        provided_password = request.args.get('password')
        
        # If no password provided or password is incorrect
        if not provided_password or provided_password != url.password:
            return jsonify({
                'error': 'This URL is password-protected', 
                'requires_password': True
            }), 401
        
    # Increment click count and update last access time
    url.click_count = (url.click_count or 0) + 1
    url.last_accessed_at = datetime.utcnow()
    db.session.commit()
    return redirect(url.original_url)

@app.route('/delete', methods=['POST'])
def delete_short_code():
    """Delete a short code from the database."""
    # User is already validated and available in g.user thanks to the middleware
    user = g.user
        
    short_code = request.args.get('code')
    if not short_code:
        return jsonify({'error': 'Short code is required'}), 400

    url = URL.query.filter_by(short_code=short_code).first()

    if not url:
        return jsonify({'error': 'Short code not found'}), 404
        
    # Check if the user is the owner of the URL
    if url.user_id != user.id:
        return jsonify({'error': 'You do not have permission to delete this URL'}), 403

    url.is_deleted = True
    url.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Short code deleted successfully'}), 200

@app.route('/edit', methods=['PUT'])
def edit_short_code():
    """Edit a short code's properties including URL, expiry date, and timeout.
    
    This endpoint allows users to:
    1. Update the destination URL
    2. Set or update the expiry date (can be set to a past date to make the URL inactive)
    3. Clear the expiry date (to reactivate an inactive URL)
    4. Set or update the timeout seconds
    """
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    user = get_user_from_api_key(api_key)
    
    if not user:
        return jsonify({'error': 'Invalid or missing API key'}), 401
        
    short_code = request.json.get('code')
    if not short_code:
        return jsonify({'error': 'Short code is required'}), 400

    url_entry = URL.query.filter_by(short_code=short_code).first()

    if not url_entry:
        return jsonify({'error': 'Short code not found'}), 404
        
    # Check if the user is the owner of the URL
    if url_entry.user_id != user.id:
        return jsonify({'error': 'You do not have permission to edit this URL'}), 403

    # Update URL if provided
    new_url = request.json.get('url')
    if new_url:
        url_entry.original_url = new_url
    
    # Handle expiry date
    if 'expiry_date' in request.json:
        expiry_date_str = request.json.get('expiry_date')
        
        # If null/None is provided, clear the expiry date (reactivate the URL)
        if expiry_date_str is None:
            url_entry.expiry_date = None
        else:
            try:
                # Parse ISO format date string
                url_entry.expiry_date = datetime.fromisoformat(expiry_date_str)
            except ValueError:
                return jsonify({'error': 'Invalid expiry date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
    
    # Handle timeout seconds
    if 'timeout_seconds' in request.json:
        timeout_seconds = request.json.get('timeout_seconds')
        
        # If null/None is provided, clear the timeout
        if timeout_seconds is None:
            url_entry.timeout_seconds = None
        else:
            try:
                timeout_seconds = int(timeout_seconds)
                if timeout_seconds <= 0:
                    return jsonify({'error': 'Timeout must be a positive integer'}), 400
                url_entry.timeout_seconds = timeout_seconds
            except ValueError:
                return jsonify({'error': 'Timeout must be a valid integer'}), 400
                
    # Handle password
    if 'password' in request.json:
        password = request.json.get('password')
        # If null/None is provided, remove the password protection
        url_entry.password = password
    
    db.session.commit()
    
    # Prepare response with current URL status
    response_data = {
        'message': 'URL updated successfully',
        'short_code': url_entry.short_code,
        'original_url': url_entry.original_url,
        'expiry_date': url_entry.expiry_date.isoformat() if url_entry.expiry_date else None,
        'timeout_seconds': url_entry.timeout_seconds,
        'is_active': not url_entry.is_expired,
        'is_password_protected': bool(url_entry.password),
        'short_url': f'http://localhost:5002/redirect?code={url_entry.short_code}'
    }
    
    return jsonify(response_data), 200

@app.route('/analytics/stream')
def stream_urls():
    """Stream URL creation events using Server-Sent Events."""
    @copy_current_request_context
    def event_stream():
        client_queue = Queue()
        
        def queue_worker():
            while True:
                try:
                    # Get event from the main queue and put it in client queue
                    event = url_events.get()
                    client_queue.put(event)
                except Exception as e:
                    logger.error(f'Queue worker error: {str(e)}')
                    break
        
        # Start worker thread for this client
        worker = Thread(target=queue_worker)
        worker.daemon = True
        worker.start()
        
        try:
            while True:
                # Send heartbeat every 15 seconds
                for _ in range(15):
                    try:
                        # Check for new events
                        event_data = client_queue.get_nowait()
                        logger.info(f'Sending event to client: {event_data}')
                        yield f'data: {json.dumps(event_data)}\n\n'
                    except Exception:
                        sleep(1)
                        
                yield ': heartbeat\n\n'
        except GeneratorExit:
            logger.info('Client disconnected')
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*'
        }
    )

@app.route('/users', methods=['POST'])
def create_user():
    """Create a new user and generate an API key."""
    # Get data from request
    data = request.json
    if not data or not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400
    
    email = data.get('email')
    name = data.get('name', '')
    
    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'User with this email already exists'}), 409
    
    try:
        # Create new user
        new_user = User(email=email, name=name)
        db.session.add(new_user)
        db.session.flush()  # Flush to get the user ID
        
        # Generate API key
        api_key = APIKey(user_id=new_user.id)
        api_key.key = generate_api_key()
        db.session.add(api_key)
        
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': {
                'id': new_user.id,
                'email': new_user.email,
                'name': new_user.name,
                'api_key': api_key.key
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error creating user: {str(e)}')
        return jsonify({'error': 'Failed to create user'}), 500

@app.route('/analytics/latest')
def get_latest_urls():
    """Get the last 10 shortened URLs."""
    try:
        latest_urls = URL.query.filter_by(is_deleted=False).order_by(URL.created_at.desc()).limit(10).all()
        app.logger.info(f'Found {len(latest_urls)} URLs')
        
        result = [
            {
                'short_code': url.short_code,
                'original_url': url.original_url,
                'created_at': url.created_at.isoformat() if url.created_at else None
            } for url in latest_urls
        ]
        
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error fetching latest URLs: {str(e)}')
        return jsonify({'error': 'Failed to fetch latest URLs'}), 500

@app.route('/analytics/popular')
def get_popular_urls():
    """Get the top 10 most clicked URLs, breaking ties by last access time."""
    try:
        popular_urls = URL.query.filter_by(is_deleted=False).order_by(
            URL.click_count.desc(),
            URL.last_accessed_at.desc().nullslast()
        ).limit(10).all()

        return jsonify([
            {
                'short_code': url.short_code,
                'original_url': url.original_url,
                'click_count': url.click_count or 0,
                'last_accessed_at': url.last_accessed_at.isoformat() if url.last_accessed_at else None,
                'created_at': url.created_at.isoformat() if url.created_at else None
            } for url in popular_urls
        ])
    except Exception as e:
        logger.error(f'Error fetching popular URLs: {str(e)}')
        return jsonify({'error': 'Failed to fetch popular URLs'}), 500

@app.route('/analytics/most-shortened')
def get_most_shortened_urls():
    """Get the top 10 most shortened URLs."""
    try:
        # Use SQLAlchemy to group by original_url and count occurrences
        most_shortened = db.session.query(
            URL.original_url,
            db.func.count(URL.short_code).label('shortening_count')
        ).filter_by(is_deleted=False).group_by(
            URL.original_url
        ).order_by(
            db.desc('shortening_count')
        ).limit(10).all()

        return jsonify([
            {
                'original_url': url[0],
                'shortening_count': url[1],
                # Get all short codes for this URL
                'short_codes': [
                    code[0] for code in db.session.query(URL.short_code)
                    .filter(URL.original_url == url[0])
                    .filter_by(is_deleted=False)
                    .all()
                ]
            } for url in most_shortened
        ])
    except Exception as e:
        logger.error(f'Error fetching most shortened URLs: {str(e)}')
        return jsonify({'error': 'Failed to fetch most shortened URLs'}), 500

# Keep the connection open during requests
@app.teardown_appcontext
def close_connection(exception):
    pass

@app.route('/user/tier/update', methods=['POST'])
def update_user_tier():
    """Update a user's pricing tier."""
    # User is already validated and available in g.user thanks to the middleware
    admin_user = g.user
    
    # Additional check for enterprise tier
    if admin_user.pricing_tier != 'enterprise':
        return jsonify({'error': 'Unauthorized. This endpoint requires an enterprise API key.'}), 403
    
    # Get the request data
    data = request.get_json()
    
    # Validate the request data
    if not data or 'pricing_tier' not in data:
        return jsonify({'error': 'Pricing tier is required'}), 400
    
    pricing_tier = data['pricing_tier']
    
    # Validate the pricing tier
    if pricing_tier not in ['hobby', 'enterprise']:
        return jsonify({'error': 'Invalid pricing tier. Must be either "hobby" or "enterprise".'}), 400
    
    # Get the user to update
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Update the user's pricing tier
    user.pricing_tier = pricing_tier
    db.session.commit()
    
    return jsonify({
        'user_id': user.id,
        'email': user.email,
        'pricing_tier': user.pricing_tier,
        'message': f'User pricing tier updated to {pricing_tier}'
    })

@app.route('/user/urls', methods=['GET'])
def get_user_urls():
    """Get all URLs for the authenticated user.
    
    This endpoint returns a list of all URLs created by the authenticated user,
    including all details such as short code, original URL, creation date,
    click count, expiry date, etc.
    
    Returns:
        Response: JSON response with the list of URLs
    """
    # User is already validated and available in g.user thanks to the middleware
    user = g.user
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    
    # Limit per_page to a reasonable value to prevent abuse
    if per_page > 1000:
        per_page = 1000
    
    # Get filter parameters
    is_active = request.args.get('is_active', None)
    is_deleted = request.args.get('is_deleted', None)
    is_password_protected = request.args.get('is_password_protected', None)
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')
    
    # Build the query
    query = URL.query.filter_by(user_id=user.id)
    
    # Apply filters if provided
    if is_active is not None:
        is_active = is_active.lower() == 'true'
        if is_active:
            # Active URLs: not expired and not deleted
            query = query.filter(
                (URL.expiry_date.is_(None) | (URL.expiry_date > datetime.utcnow())),
                URL.is_deleted == False
            )
        else:
            # Inactive URLs: expired or deleted
            query = query.filter(
                db.or_(
                    URL.is_deleted == True,
                    db.and_(URL.expiry_date.isnot(None), URL.expiry_date <= datetime.utcnow())
                )
            )
    
    if is_deleted is not None:
        is_deleted = is_deleted.lower() == 'true'
        query = query.filter(URL.is_deleted == is_deleted)
    
    if is_password_protected is not None:
        is_password_protected = is_password_protected.lower() == 'true'
        if is_password_protected:
            query = query.filter(URL.password.isnot(None))
        else:
            query = query.filter(URL.password.is_(None))
    
    # Apply sorting
    valid_sort_fields = {
        'created_at': URL.created_at,
        'last_accessed_at': URL.last_accessed_at,
        'click_count': URL.click_count,
        'short_code': URL.short_code,
        'original_url': URL.original_url
    }
    
    if sort_by in valid_sort_fields:
        sort_field = valid_sort_fields[sort_by]
        if sort_order.lower() == 'asc':
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())
    else:
        # Default sort by creation date, newest first
        query = query.order_by(URL.created_at.desc())
    
    # Paginate the results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    urls = pagination.items
    
    # Format the response
    results = []
    for url in urls:
        url_data = {
            'short_code': url.short_code,
            'original_url': url.original_url,
            'short_url': f'http://localhost:5002/redirect?code={url.short_code}',
            'created_at': url.created_at.isoformat(),
            'click_count': url.click_count,
            'last_accessed_at': url.last_accessed_at.isoformat() if url.last_accessed_at else None,
            'is_deleted': url.is_deleted,
            'deleted_at': url.deleted_at.isoformat() if url.deleted_at else None,
            'expiry_date': url.expiry_date.isoformat() if url.expiry_date else None,
            'timeout_seconds': url.timeout_seconds,
            'is_password_protected': bool(url.password),
            'is_active': not url.is_deleted and (url.expiry_date is None or url.expiry_date > datetime.utcnow())
        }
        results.append(url_data)
    
    # Add pagination metadata
    response = {
        'urls': results,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages,
            'total_items': pagination.total
        },
        'filters': {
            'is_active': is_active,
            'is_deleted': is_deleted,
            'is_password_protected': is_password_protected,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    }
    
    return jsonify(response)

@app.route('/admin/logs', methods=['GET'])
def view_request_logs():
    """View request logs with optional filtering.
    
    Query parameters:
    - path: Filter logs by path
    - method: Filter logs by HTTP method
    - status_code: Filter logs by status code
    - ip: Filter logs by IP address
    - start_date: Filter logs after this date (format: YYYY-MM-DD)
    - end_date: Filter logs before this date (format: YYYY-MM-DD)
    - limit: Maximum number of logs to return (default: 100)
    - format: Response format ('json' or 'html', default: 'html')
    """
    # Get query parameters for filtering
    path_filter = request.args.get('path')
    method_filter = request.args.get('method')
    status_filter = request.args.get('status_code')
    ip_filter = request.args.get('ip')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 100, type=int)
    format_type = request.args.get('format', 'html')
    
    # Read log file
    logs = []
    try:
        log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'request_logs.log')
        with open(log_file_path, 'r') as f:
            for line in f:
                try:
                    # Parse log line
                    if ' - IP: ' in line:
                        # This is a request line
                        timestamp_str = line.split(' - ', 1)[0]
                        details = line.split(' - ', 1)[1].strip()
                        
                        # Extract information using regex
                        ip_match = re.search(r'IP: ([\d\.]+)', details)
                        method_match = re.search(r'Method: (\w+)', details)
                        url_match = re.search(r'URL: ([^\|]+)', details)
                        path_match = re.search(r'Path: ([^\|]+)', details)
                        user_agent_match = re.search(r'User-Agent: ([^\|]+)', details)
                        
                        if ip_match and method_match and url_match:
                            log_entry = {
                                'timestamp': timestamp_str,
                                'ip': ip_match.group(1).strip(),
                                'method': method_match.group(1).strip(),
                                'url': url_match.group(1).strip(),
                                'path': path_match.group(1).strip() if path_match else '',
                                'user_agent': user_agent_match.group(1).strip() if user_agent_match else '',
                                'status_code': None,
                                'response_time': None
                            }
                            logs.append(log_entry)
                    elif ' - Response time: ' in line:
                        # This is a response line, update the previous request
                        if logs:
                            timestamp_str = line.split(' - ', 1)[0]
                            details = line.split(' - ', 1)[1].strip()
                            
                            response_time_match = re.search(r'Response time: ([\d\.]+)s', details)
                            status_match = re.search(r'Status: (\d+)', details)
                            
                            if response_time_match and status_match and logs:
                                logs[-1]['response_time'] = float(response_time_match.group(1))
                                logs[-1]['status_code'] = int(status_match.group(1))
                except Exception as e:
                    logger.error(f"Error parsing log line: {str(e)}")
                    continue
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        return jsonify({'error': 'Error reading log file'}), 500
    
    # Apply filters
    filtered_logs = logs
    
    if path_filter:
        filtered_logs = [log for log in filtered_logs if path_filter in log['path']]
    
    if method_filter:
        filtered_logs = [log for log in filtered_logs if log['method'].upper() == method_filter.upper()]
    
    if status_filter:
        status_code = int(status_filter)
        filtered_logs = [log for log in filtered_logs if log['status_code'] == status_code]
    
    if ip_filter:
        filtered_logs = [log for log in filtered_logs if ip_filter in log['ip']]
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            filtered_logs = [log for log in filtered_logs if datetime.strptime(log['timestamp'].split(',')[0], '%Y-%m-%d %H:%M:%S') >= start_datetime]
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            filtered_logs = [log for log in filtered_logs if datetime.strptime(log['timestamp'].split(',')[0], '%Y-%m-%d %H:%M:%S') <= end_datetime]
        except ValueError:
            pass
    
    # Sort logs by timestamp (newest first)
    filtered_logs.reverse()
    
    # Limit the number of logs
    filtered_logs = filtered_logs[:limit]
    
    # Return response in requested format
    if format_type == 'json':
        return jsonify({
            'logs': filtered_logs,
            'total': len(filtered_logs),
            'filters': {
                'path': path_filter,
                'method': method_filter,
                'status_code': status_filter,
                'ip': ip_filter,
                'start_date': start_date,
                'end_date': end_date
            }
        })
    else:
        # HTML format
        return render_template('logs.html', 
                              logs=filtered_logs, 
                              total=len(filtered_logs),
                              filters={
                                  'path': path_filter,
                                  'method': method_filter,
                                  'status_code': status_filter,
                                  'ip': ip_filter,
                                  'start_date': start_date,
                                  'end_date': end_date
                              })

@app.route('/admin/blacklist', methods=['GET', 'POST'])
def manage_blacklist():
    """View and manage the blacklist."""
    # Check if the user is an admin
    if not hasattr(g, 'user') or g.user.role != 'admin':
        return jsonify({'error': 'Access denied. Admin privileges required.'}), 403
    
    if request.method == 'POST':
        try:
            # Get the blacklist path
            blacklist_path = get_blacklist_path()
            
            # Load the current blacklist
            with open(blacklist_path, 'r') as f:
                blacklist_data = json.load(f)
            
            # Update the blacklist based on the form data
            action = request.form.get('action')
            item_type = request.form.get('type')
            value = request.form.get('value')
            
            if not action or not item_type or not value:
                return jsonify({'error': 'Missing required fields'}), 400
            
            if item_type not in ['api_key', 'ip']:
                return jsonify({'error': 'Invalid item type'}), 400
            
            if action == 'add':
                # Add the item to the blacklist
                if item_type == 'api_key':
                    if value not in blacklist_data['blacklisted_api_keys']:
                        blacklist_data['blacklisted_api_keys'].append(value)
                else:  # ip
                    if value not in blacklist_data['blacklisted_ips']:
                        blacklist_data['blacklisted_ips'].append(value)
            elif action == 'remove':
                # Remove the item from the blacklist
                if item_type == 'api_key':
                    if value in blacklist_data['blacklisted_api_keys']:
                        blacklist_data['blacklisted_api_keys'].remove(value)
                else:  # ip
                    if value in blacklist_data['blacklisted_ips']:
                        blacklist_data['blacklisted_ips'].remove(value)
            else:
                return jsonify({'error': 'Invalid action'}), 400
            
            # Update the last_updated timestamp
            blacklist_data['last_updated'] = datetime.utcnow().isoformat()
            
            # Save the updated blacklist
            with open(blacklist_path, 'w') as f:
                json.dump(blacklist_data, f, indent=2)
            
            # Force reload the blacklist
            load_blacklist(force_reload=True)
            
            return jsonify({'success': True, 'message': f'{item_type} {action}ed successfully'}), 200
        except Exception as e:
            app.logger.error(f"Error updating blacklist: {str(e)}")
            return jsonify({'error': f'Error updating blacklist: {str(e)}'}), 500
    else:  # GET request
        try:
            # Get the blacklist path
            blacklist_path = get_blacklist_path()
            
            # Load the blacklist
            with open(blacklist_path, 'r') as f:
                blacklist_data = json.load(f)
            
            # Render the blacklist management page
            return render_template('blacklist.html', 
                                 blacklist=blacklist_data,
                                 last_updated=blacklist_data.get('last_updated', 'Unknown'))
        except Exception as e:
            app.logger.error(f"Error loading blacklist: {str(e)}")
            return jsonify({'error': f'Error loading blacklist: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5002)
