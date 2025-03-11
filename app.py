from flask import Flask, request, redirect, jsonify, Response, render_template, copy_current_request_context
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
from cryptography.fernet import Fernet
import base64

import os

app = Flask(__name__)
app.template_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))

# Check if we're in a testing environment
if os.environ.get('TESTING') == 'True':
    # Use SQLite in-memory database for testing
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
else:
    # Use environment variable for database URI if available, otherwise use the PostgreSQL URI
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        'postgresql://neondb_owner:npg_8LqUgf2eYSid@ep-billowing-sunset-a5goac87-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require'
    )
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Enable CORS for SSE
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
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
    encrypted_key = db.Column(db.LargeBinary, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

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
        return f'<APIKey for user {self.user_id}>'
    
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
        url_data (dict): Dictionary containing URL data (url, custom_code, expiry_date, timeout_seconds)
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
    
    # Create the URL object
    new_url = URL(
        short_code=short_code, 
        original_url=original_url, 
        user_id=user_id,
        expiry_date=expiry_date,
        timeout_seconds=timeout_seconds
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
        'timeout_seconds': url.timeout_seconds
    }

def get_user_from_api_key(api_key):
    """Get user from API key."""
    if not api_key:
        return None
    
    # Since we can't directly query by the decrypted key, we need to fetch all non-deleted keys
    # and check each one
    api_keys = APIKey.query.filter_by(is_deleted=False).all()
    for key_record in api_keys:
        try:
            if key_record.key == api_key:
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
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    user = get_user_from_api_key(api_key)
    
    if not user:
        return jsonify({'error': 'Invalid or missing API key'}), 401
    
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
    """Shorten multiple URLs in a single request."""
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    user = get_user_from_api_key(api_key)
    
    if not user:
        return jsonify({'error': 'Invalid or missing API key'}), 401
    
    # Check if the user has the enterprise tier
    if user.pricing_tier != 'enterprise':
        return jsonify({
            'error': 'Access denied. Batch URL shortening is only available for enterprise tier users.',
            'current_tier': user.pricing_tier,
            'required_tier': 'enterprise'
        }), 403
    
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
                'timeout_seconds': new_url.timeout_seconds
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
    """Redirect to the original URL based on the short code."""
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
        
    # Increment click count and update last access time
    url.click_count = (url.click_count or 0) + 1
    url.last_accessed_at = datetime.utcnow()
    db.session.commit()
    return redirect(url.original_url)

@app.route('/delete', methods=['DELETE'])
def delete_short_code():
    """Delete a short code from the database."""
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    user = get_user_from_api_key(api_key)
    
    if not user:
        return jsonify({'error': 'Invalid or missing API key'}), 401
        
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
    """Edit the original URL for a given short code."""
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    user = get_user_from_api_key(api_key)
    
    if not user:
        return jsonify({'error': 'Invalid or missing API key'}), 401
        
    short_code = request.json.get('code')
    new_url = request.json.get('url')

    if not short_code or not new_url:
        return jsonify({'error': 'Short code and new URL are required'}), 400

    url_entry = URL.query.filter_by(short_code=short_code).first()

    if not url_entry:
        return jsonify({'error': 'Short code not found'}), 404
        
    # Check if the user is the owner of the URL
    if url_entry.user_id != user.id:
        return jsonify({'error': 'You do not have permission to edit this URL'}), 403

    url_entry.original_url = new_url
    db.session.commit()
    return jsonify({'message': 'URL updated successfully'}), 200

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

@app.route('/users/<int:user_id>/update-tier', methods=['PUT'])
def update_user_tier(user_id):
    """Update a user's pricing tier."""
    # Get the API key from the request headers
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'API key is required'}), 401
    
    # Get the user from the API key
    admin_user = get_user_from_api_key(api_key)
    if not admin_user:
        return jsonify({'error': 'Invalid API key'}), 401
    
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

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5002)
