import os
import requests
import json
import time
from datetime import datetime, timedelta

# Set environment variables to use SQLite
os.environ['USE_SQLITE'] = 'True'

# Import app after setting environment variables
from app import app, db, User, APIKey, URL, generate_api_key

# Base URL of the application
BASE_URL = "http://localhost:5002"

def print_response_info(response, description):
    """Print response information including headers and timing."""
    print(f"\n=== {description} ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response Time Header: {response.headers.get('X-Response-Time', 'Not available')}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'Not available')}")
    
    # Print the response body for JSON responses
    if 'application/json' in response.headers.get('Content-Type', ''):
        try:
            print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Response Body: {response.text[:100]}...")
    else:
        print(f"Response Body: {response.text[:100]}...")
    
    print("=" * 50)

def setup_database():
    """Set up the database with test users and API keys."""
    with app.app_context():
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
        
        # Create a hobby tier user
        hobby_user = User(
            email='hobby@example.com',
            name='Hobby User',
            pricing_tier='hobby',
            role='user'
        )
        db.session.add(hobby_user)
        
        # Create an enterprise tier user
        enterprise_user = User(
            email='enterprise@example.com',
            name='Enterprise User',
            pricing_tier='enterprise',
            role='admin'
        )
        db.session.add(enterprise_user)
        db.session.flush()
        
        # Create API keys for both users
        hobby_api_key = APIKey(user_id=hobby_user.id)
        hobby_api_key.key = "hobby_test_key"
        hobby_api_key.is_active = True
        hobby_api_key.created_at = datetime.utcnow()
        db.session.add(hobby_api_key)
        
        enterprise_api_key = APIKey(user_id=enterprise_user.id)
        enterprise_api_key.key = "enterprise_test_key"
        enterprise_api_key.is_active = True
        enterprise_api_key.created_at = datetime.utcnow()
        db.session.add(enterprise_api_key)
        
        db.session.commit()
        
        print("Database initialized with test users and API keys:")
        print(f"Hobby User API Key: hobby_test_key")
        print(f"Enterprise User API Key: enterprise_test_key")

def test_home_page():
    """Test the home page response time."""
    start = time.time()
    response = requests.get(f"{BASE_URL}/")
    client_time = (time.time() - start) * 1000  # Convert to milliseconds
    print_response_info(response, "Home Page")
    print(f"Client-measured time: {client_time:.2f}ms")

def test_shorten_url(api_key, with_password=False):
    """Test shortening a URL."""
    # Prepare the URL data
    url_data = {
        "url": "https://example.com/test",
        "custom_code": f"test{int(time.time()) % 10000}",  # Generate a somewhat unique code
        "expiry_date": (datetime.utcnow() + timedelta(days=7)).isoformat().split('.')[0]  # ISO format without microseconds
    }
    
    # Add password if requested (testing password protection feature)
    if with_password:
        url_data["password"] = f"secure_{int(time.time())}"  # Dynamic password
    
    # Make the request
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/shorten",
        json=url_data,
        headers={"X-API-Key": api_key}
    )
    client_time = (time.time() - start) * 1000  # Convert to milliseconds
    
    description = "Shorten URL with Password" if with_password else "Shorten URL"
    print_response_info(response, description)
    print(f"Client-measured time: {client_time:.2f}ms")
    
    # If successful, return the short code for further testing
    if response.status_code == 200:
        return response.json().get("short_code")
    return None

def test_batch_shorten(api_key):
    """Test batch shortening URLs."""
    # Prepare batch data with various URL configurations
    batch_data = {
        "urls": [
            {"url": "https://example.com/batch1"},
            {"url": "https://example.com/batch2", "custom_code": f"btc{int(time.time()) % 10000}"},
            {"url": "https://example.com/batch3", "password": f"secure_{int(time.time())}_{hash(datetime.utcnow())}"} # Dynamic password
        ]
    }
    
    # Make the request
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/shorten/batch",
        json=batch_data,
        headers={"X-API-Key": api_key}
    )
    client_time = (time.time() - start) * 1000  # Convert to milliseconds
    
    print_response_info(response, "Batch Shorten URLs")
    print(f"Client-measured time: {client_time:.2f}ms")

def test_redirect(short_code, password=None):
    """Test URL redirection."""
    # Prepare the request
    params = {"code": short_code}
    data = {}
    if password:
        data = {"password": password}
    
    # Test the redirect
    start = time.time()
    response = requests.get(
        f"{BASE_URL}/redirect",
        params=params,
        data=data,
        allow_redirects=False
    )
    client_time = (time.time() - start) * 1000  # Convert to milliseconds
    
    description = f"Redirect for code: {short_code}" + (" with password" if password else "")
    print_response_info(response, description)
    print(f"Client-measured time: {client_time:.2f}ms")

def run_all_tests():
    """Run all tests."""
    print("Starting response time tests...")
    print(f"Testing against: {BASE_URL}")
    print("=" * 50)
    
    # Set up the database with test data
    setup_database()
    
    # Test basic page load
    test_home_page()
    
    # Test URL shortening with hobby user
    print("\n--- Testing with Hobby User ---")
    hobby_short_code = test_shorten_url("hobby_test_key")
    
    # Test URL shortening with password
    password_short_code = test_shorten_url("hobby_test_key", with_password=True)
    
    # Test URL redirection
    if hobby_short_code:
        test_redirect(hobby_short_code)
    
    # Test password-protected URL redirection
    if password_short_code:
        # First without password (should fail)
        test_redirect(password_short_code)
        # Then with password (should succeed)
        test_redirect(password_short_code, f"secure_{int(time.time())}")
    
    # Test with enterprise user
    print("\n--- Testing with Enterprise User ---")
    test_shorten_url("enterprise_test_key")
    
    # Test batch shortening (enterprise only feature)
    test_batch_shorten("enterprise_test_key")
    
    # Try batch shortening with hobby user (should be denied)
    test_batch_shorten("hobby_test_key")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    run_all_tests()
