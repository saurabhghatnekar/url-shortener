#!/usr/bin/env python3
import requests
import json
import sys

def shorten_url(api_key, url_to_shorten):
    """Test the API key by shortening a URL."""
    url = "http://localhost:5002/shorten"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    data = {"url": url_to_shorten}
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        
        result = response.json()
        print("URL shortened successfully!")
        print(f"Original URL: {result['original_url']}")
        print(f"Short Code: {result['short_code']}")
        print(f"Short URL: {result['short_url']}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error shortening URL: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_api_key.py <api_key> <url_to_shorten>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    url_to_shorten = sys.argv[2]
    
    shorten_url(api_key, url_to_shorten)
