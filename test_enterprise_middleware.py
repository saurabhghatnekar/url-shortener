import unittest
import os
import json
from datetime import datetime

# Set the testing environment variable
os.environ['TESTING'] = 'True'

# Import after setting the environment variable
from app import app, db, URL, User, APIKey, generate_api_key

class EnterpriseTierMiddlewareTestCase(unittest.TestCase):
    def setUp(self):
        # Set up the Flask test client
        app.config['TESTING'] = True
        self.app = app.test_client()
        
        # Create the database tables
        with app.app_context():
            db.create_all()
            
            # Create a hobby tier test user
            hobby_user = User(
                email='hobby@example.com',
                name='Hobby User',
                pricing_tier='hobby'
            )
            db.session.add(hobby_user)
            db.session.flush()
            
            # Store the hobby user ID for tests
            self.hobby_user_id = hobby_user.id
            
            # Create an API key for the hobby user
            hobby_api_key_value = generate_api_key()
            hobby_api_key = APIKey(user_id=self.hobby_user_id)
            hobby_api_key.key = hobby_api_key_value
            db.session.add(hobby_api_key)
            
            # Create an enterprise tier test user
            enterprise_user = User(
                email='enterprise@example.com',
                name='Enterprise User',
                pricing_tier='enterprise'
            )
            db.session.add(enterprise_user)
            db.session.flush()
            
            # Store the enterprise user ID for tests
            self.enterprise_user_id = enterprise_user.id
            
            # Create an API key for the enterprise user
            enterprise_api_key_value = generate_api_key()
            enterprise_api_key = APIKey(user_id=self.enterprise_user_id)
            enterprise_api_key.key = enterprise_api_key_value
            db.session.add(enterprise_api_key)
            
            db.session.commit()
            
            # Store the API keys for tests
            self.hobby_api_key = hobby_api_key_value
            self.enterprise_api_key = enterprise_api_key_value
            
            # Set up headers for both user types
            self.hobby_headers = {'X-API-Key': self.hobby_api_key}
            self.enterprise_headers = {'X-API-Key': self.enterprise_api_key}

    def tearDown(self):
        # Clean up the database
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_enterprise_tier_access_allowed(self):
        """Test that enterprise tier users can access enterprise-only endpoints."""
        # Create a batch of URLs
        batch_data = {
            'urls': [
                {'url': 'https://example.com/batch1'},
                {'url': 'https://example.com/batch2'}
            ]
        }
        
        # Use enterprise user headers
        response = self.app.post('/shorten/batch',
                               json=batch_data,
                               headers=self.enterprise_headers)
        
        # Should return 200 OK or 207 Multi-Status
        self.assertIn(response.status_code, [200, 207])
        
        # Parse the response
        data = response.get_json()
        
        # Check that the batch operation was processed
        self.assertIn('results', data)
        self.assertGreater(data['successful'], 0)

    def test_enterprise_tier_access_denied(self):
        """Test that hobby tier users cannot access enterprise-only endpoints."""
        # Create a batch of URLs
        batch_data = {
            'urls': [
                {'url': 'https://example.com/batch1'},
                {'url': 'https://example.com/batch2'}
            ]
        }
        
        # Use hobby user headers
        response = self.app.post('/shorten/batch',
                               json=batch_data,
                               headers=self.hobby_headers)
        
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        
        # Parse the response
        data = response.get_json()
        
        # Check the error message
        self.assertIn('error', data)
        self.assertEqual(data['current_tier'], 'hobby')
        self.assertEqual(data['required_tier'], 'enterprise')
        self.assertIn('Access denied', data['error'])

    def test_middleware_consistent_error_message(self):
        """Test that the middleware provides consistent error messages."""
        # Create a list of enterprise-only endpoints to test
        enterprise_endpoints = [
            '/shorten/batch'
            # Add more enterprise endpoints as they are created
        ]
        
        for endpoint in enterprise_endpoints:
            # Use hobby user headers
            response = self.app.post(endpoint,
                                   json={'test': 'data'},
                                   headers=self.hobby_headers)
            
            # Should return 403 Forbidden
            self.assertEqual(response.status_code, 403)
            
            # Parse the response
            data = response.get_json()
            
            # Check the error message format is consistent
            self.assertIn('error', data)
            self.assertEqual(data['current_tier'], 'hobby')
            self.assertEqual(data['required_tier'], 'enterprise')
            self.assertIn('Access denied', data['error'])

    def test_non_enterprise_routes_not_affected(self):
        """Test that non-enterprise routes are not affected by the middleware."""
        # Test a regular endpoint with hobby user
        response = self.app.post('/shorten',
                               json={'url': 'https://example.com'},
                               headers=self.hobby_headers)
        
        # Should return 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Parse the response
        data = response.get_json()
        
        # Check that the URL was created
        self.assertIn('short_code', data)
        self.assertIn('short_url', data)

if __name__ == '__main__':
    unittest.main()
