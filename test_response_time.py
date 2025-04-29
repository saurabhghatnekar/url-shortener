import requests
import json
import time
from datetime import datetime

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

def test_home_page():
    """Test the home page response time."""
    start = time.time()
    response = requests.get(f"{BASE_URL}/")
    client_time = (time.time() - start) * 1000  # Convert to milliseconds
    print_response_info(response, "Home Page")
    print(f"Client-measured time: {client_time:.2f}ms")

def test_shorten_url():
    """Test shortening a URL."""
    # First, we need to get an API key
    # For testing, we'll use a hardcoded API key if available
    # In a real scenario, you would authenticate and get a valid API key
    
    # Try to use a test API key (this may fail if the key doesn't exist)
    api_key = "test_api_key"  # Replace with a valid API key if needed
    
    # Prepare the URL data
    url_data = {
        "url": "https://example.com/test",
        "custom_code": f"test{int(time.time()) % 10000}",  # Generate a somewhat unique code
        "expiry_date": (datetime.utcnow().isoformat().split('.')[0])  # ISO format without microseconds
    }
    
    # Make the request
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/shorten",
        json=url_data,
        headers={"X-API-Key": api_key}
    )
    client_time = (time.time() - start) * 1000  # Convert to milliseconds
    
    print_response_info(response, "Shorten URL")
    print(f"Client-measured time: {client_time:.2f}ms")
    
    # If successful, return the short code for further testing
    if response.status_code == 200:
        return response.json().get("short_code")
    return None

def test_batch_shorten():
    """Test batch shortening URLs."""
    # Use a test API key
    api_key = "test_api_key"  # Replace with a valid API key if needed
    
    # Prepare batch data
    batch_data = {
        "urls": [
            {"url": "https://example.com/batch1"},
            {"url": "https://example.com/batch2", "custom_code": f"btc{int(time.time()) % 10000}"},
            {"url": "https://example.com/batch3", "password": "test123"}
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

def test_redirect():
    """Test URL redirection."""
    # First create a URL to redirect to
    short_code = test_shorten_url()
    
    if not short_code:
        print("Failed to create a URL for redirection test")
        return
    
    # Test the redirect
    start = time.time()
    response = requests.get(f"{BASE_URL}/redirect?code={short_code}", allow_redirects=False)
    client_time = (time.time() - start) * 1000  # Convert to milliseconds
    
    print_response_info(response, f"Redirect for code: {short_code}")
    print(f"Client-measured time: {client_time:.2f}ms")

def run_all_tests():
    """Run all tests."""
    print("Starting response time tests...")
    print(f"Testing against: {BASE_URL}")
    print("=" * 50)
    
    test_home_page()
    test_shorten_url()
    test_batch_shorten()
    test_redirect()
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    run_all_tests()
