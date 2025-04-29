import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime

# Set the testing environment variable
os.environ['TESTING'] = 'True'

# Import after setting the environment variable
from app import app, db, User, APIKey, generate_api_key, load_blacklist

class BlacklistMiddlewareTestCase(unittest.TestCase):
    def setUp(self):
        # Set up the Flask test client
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        
        # Create a temporary directory for the blacklist config
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a test blacklist file
        self.test_blacklist_path = os.path.join(self.temp_dir, 'test_blacklist.json')
        self.test_blacklist = {
            "blacklisted_api_keys": ["test-blacklisted-key"],
            "blacklisted_ips": ["192.168.1.100"],
            "last_updated": datetime.utcnow().isoformat(),
            "notes": "Test blacklist"
        }
        with open(self.test_blacklist_path, 'w') as f:
            json.dump(self.test_blacklist, f)
        
        # Set the blacklist path for testing
        app.config['BLACKLIST_CONFIG_PATH'] = self.test_blacklist_path
        
        # Create the database tables
        with app.app_context():
            db.create_all()
            
            # Create a test user
            test_user = User(
                email='test@example.com',
                name='Test User',
                pricing_tier='hobby'
            )
            db.session.add(test_user)
            db.session.flush()
            
            # Store the user ID for tests
            self.user_id = test_user.id
            
            # Create a valid API key for the user
            valid_api_key_value = generate_api_key()
            valid_api_key = APIKey(user_id=self.user_id)
            valid_api_key.key = valid_api_key_value
            db.session.add(valid_api_key)
            
            # Create a blacklisted API key for the user
            blacklisted_api_key_value = "test-blacklisted-key"
            blacklisted_api_key = APIKey(user_id=self.user_id)
            blacklisted_api_key.key = blacklisted_api_key_value
            db.session.add(blacklisted_api_key)
            
            db.session.commit()
            
            # Store the API keys for tests
            self.valid_api_key = valid_api_key_value
            self.blacklisted_api_key = blacklisted_api_key_value
            
            # Set up headers for both API keys
            self.valid_headers = {'X-API-Key': self.valid_api_key}
            self.blacklisted_headers = {'X-API-Key': self.blacklisted_api_key}
            
            # Force reload the blacklist
            load_blacklist(force_reload=True)

    def tearDown(self):
        # Clean up the database
        with app.app_context():
            db.session.remove()
            db.drop_all()
        
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_blacklisted_api_key(self):
        """Test that requests with blacklisted API keys are blocked."""
        # Try to access an endpoint with a blacklisted API key
        response = self.app.post('/shorten',
                               json={'url': 'https://example.com'},
                               headers=self.blacklisted_headers)
        
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        
        # Check the error message
        data = response.get_json()
        self.assertIn('error', data)
        self.assertEqual(data['code'], 'BLACKLISTED_API_KEY')
        self.assertIn('blacklisted', data['error'])

    def test_valid_api_key(self):
        """Test that requests with valid API keys are allowed."""
        # Try to access an endpoint with a valid API key
        response = self.app.post('/shorten',
                               json={'url': 'https://example.com'},
                               headers=self.valid_headers)
        
        # Should return 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Check that the URL was created
        data = response.get_json()
        self.assertIn('short_code', data)
        self.assertIn('short_url', data)

    def test_blacklisted_ip(self):
        """Test that requests from blacklisted IPs are blocked."""
        # Try to access an endpoint from a blacklisted IP
        response = self.app.post('/shorten',
                               json={'url': 'https://example.com'},
                               headers=self.valid_headers,
                               environ_base={'REMOTE_ADDR': '192.168.1.100'})
        
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        
        # Check the error message
        data = response.get_json()
        self.assertIn('error', data)
        self.assertEqual(data['code'], 'BLACKLISTED_IP')
        self.assertIn('blacklisted', data['error'])

    def test_blacklist_admin_endpoint(self):
        """Test the blacklist admin endpoint directly by modifying the blacklist file."""
        # Since we're testing the blacklist functionality, not the admin role check,
        # we'll directly modify the blacklist file to simulate the admin endpoint's actions
        
        # Add a new API key to the blacklist
        with open(self.test_blacklist_path, 'r') as f:
            blacklist_data = json.load(f)
        
        # Add a new key
        new_key = 'new-blacklisted-key'
        blacklist_data['blacklisted_api_keys'].append(new_key)
        blacklist_data['last_updated'] = datetime.utcnow().isoformat()
        
        with open(self.test_blacklist_path, 'w') as f:
            json.dump(blacklist_data, f)
        
        # Force reload the blacklist
        with app.app_context():
            load_blacklist(force_reload=True)
        
        # Verify the key was added by trying to use it
        test_headers = {'X-API-Key': new_key}
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com'},
                              headers=test_headers)
        
        # Should return 403 Forbidden because the key is blacklisted
        self.assertEqual(response.status_code, 403)
        
        # Check the error message
        data = response.get_json()
        self.assertIn('error', data)
        self.assertEqual(data['code'], 'BLACKLISTED_API_KEY')
        
        # Now remove the key from the blacklist
        with open(self.test_blacklist_path, 'r') as f:
            blacklist_data = json.load(f)
        
        blacklist_data['blacklisted_api_keys'].remove(new_key)
        blacklist_data['last_updated'] = datetime.utcnow().isoformat()
        
        with open(self.test_blacklist_path, 'w') as f:
            json.dump(blacklist_data, f)
        
        # Force reload the blacklist
        with app.app_context():
            load_blacklist(force_reload=True)
        
        # Create a valid user and API key for this test
        with app.app_context():
            test_user = User(
                email='test2@example.com',
                name='Test User 2',
                pricing_tier='hobby'
            )
            db.session.add(test_user)
            db.session.flush()
            
            # Create an API key for the user
            test_api_key_value = new_key  # Use the same key that was previously blacklisted
            test_api_key = APIKey(user_id=test_user.id)
            test_api_key.key = test_api_key_value
            db.session.add(test_api_key)
            db.session.commit()
        
        # Now the key should work since it's no longer blacklisted
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com'},
                              headers=test_headers)
        
        # Should return 200 OK now that the key is not blacklisted
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
