#!/usr/bin/env python3
import requests
import json
import sys
import random
import string

def generate_random_email():
    """Generate a random email for testing."""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{random_str}@example.com"

def create_user(email=None, name=None):
    """Create a new user and get their API key."""
    if not email:
        email = generate_random_email()
    
    if not name:
        name = f"User {email.split('@')[0]}"
    
    url = "http://localhost:5002/users"
    headers = {"Content-Type": "application/json"}
    data = {"email": email, "name": name}
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses
        
        result = response.json()
        print("User created successfully!")
        print(f"User ID: {result['user']['id']}")
        print(f"Email: {result['user']['email']}")
        print(f"Name: {result['user']['name']}")
        print(f"API Key: {result['user']['api_key']}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error creating user: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return None

if __name__ == "__main__":
    # If email is provided as command line argument, use it
    email = sys.argv[1] if len(sys.argv) > 1 else None
    name = sys.argv[2] if len(sys.argv) > 2 else None
    
    create_user(email, name)
