import unittest
import tempfile
import os
import random
import string
from datetime import datetime, timedelta

# Set the testing environment variable
os.environ['TESTING'] = 'True'

# Import after setting the environment variable
from app import app, db, URL, User, APIKey, generate_api_key, encrypt_api_key, decrypt_api_key

class URLShortenerTestCase(unittest.TestCase):
    def setUp(self):
        # Set up the Flask test client
        app.config['TESTING'] = True
        self.app = app.test_client()
        
        # Create the database tables
        with app.app_context():
            db.create_all()
            
            # Create a hobby tier test user (default user)
            hobby_user = User(
                email='test@example.com',
                name='Test User',
                pricing_tier='hobby'  # Explicitly set to hobby tier
            )
            db.session.add(hobby_user)
            db.session.flush()  # Flush to get the user ID
            
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
                pricing_tier='enterprise'  # Set to enterprise tier
            )
            db.session.add(enterprise_user)
            db.session.flush()  # Flush to get the user ID
            
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
            
            # For backward compatibility with existing tests
            self.test_user_id = self.hobby_user_id
            self.api_key = self.hobby_api_key
            self.headers = self.hobby_headers

    def tearDown(self):
        # Clean up the database
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_multiple_codes_for_same_url(self):
        original_url = 'https://example.com/'

        # First request
        response1 = self.app.post('/shorten', json={'url': original_url}, headers=self.headers)
        data1 = response1.get_json()
        short_code1 = data1['short_code']

        # Second request
        response2 = self.app.post('/shorten', json={'url': original_url}, headers=self.headers)
        data2 = response2.get_json()
        short_code2 = data2['short_code']

        # Assert that different short codes are returned
        self.assertNotEqual(short_code1, short_code2)

        # Check most-shortened analytics
        response = self.app.get('/analytics/most-shortened', headers=self.headers)
        data = response.get_json()
        
        # Verify the URL appears in most-shortened with count 2
        self.assertEqual(data[0]['original_url'], original_url)
        self.assertEqual(data[0]['shortening_count'], 2)
        self.assertIn(short_code1, data[0]['short_codes'])
        self.assertIn(short_code2, data[0]['short_codes'])

    def test_non_existent_short_code(self):
        # Attempt to fetch a non-existent short code
        response = self.app.get('/redirect?code=nonexistent')
        
        # Assert that the response status code is 404
        self.assertEqual(response.status_code, 404)

        # Assert that the error message is correct
        data = response.get_json()
        self.assertEqual(data['error'], 'URL not found')

    def test_delete_short_code(self):
        # Create a short URL to delete
        original_url = 'https://example.com/delete'
        response = self.app.post('/shorten', json={'url': original_url}, headers=self.headers)
        data = response.get_json()
        short_code = data['short_code']

        # Delete the short code
        delete_response = self.app.delete(f'/delete?code={short_code}', headers=self.headers)
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.get_json()['message'], 'Short code deleted successfully')

        # Verify that the short code is soft deleted (still exists in DB but marked as deleted)
        with app.app_context():
            url = URL.query.filter_by(short_code=short_code).first()
            self.assertIsNotNone(url)
            self.assertTrue(url.is_deleted)
            self.assertIsNotNone(url.deleted_at)

        # Verify that the short code can't be accessed
        redirect_response = self.app.get(f'/redirect?code={short_code}')
        self.assertEqual(redirect_response.status_code, 404)

    def test_delete_non_existent_short_code(self):
        # Attempt to delete a non-existent short code
        response = self.app.delete('/delete?code=nonexistent', headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['error'], 'Short code not found')

    def test_invalid_url_format(self):
        # Attempt to shorten an invalid URL
        response = self.app.post('/shorten', json={'url': 'invalid-url'}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'Invalid URL format')

    def test_missing_url_parameter(self):
        # Attempt to shorten with missing URL parameter
        response = self.app.post('/shorten', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'URL cannot be empty')

    def test_empty_url(self):
        # Test empty URL string
        response = self.app.post('/shorten', json={'url': ''}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'URL cannot be empty')

        # Test URL with only whitespace
        response = self.app.post('/shorten', json={'url': '   \n\t  '}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'URL cannot be empty')

    def test_redirect_with_invalid_method(self):
        # Attempt to redirect using POST method
        response = self.app.post('/redirect?code=somecode')
        self.assertEqual(response.status_code, 405)

    def test_delete_with_invalid_method(self):
        # Attempt to delete using GET method
        response = self.app.get('/delete?code=somecode')
        self.assertEqual(response.status_code, 405)

    def test_edit_short_code(self):
        # Create a short code to edit
        original_url = 'https://example.com/edit'
        response = self.app.post('/shorten', json={'url': original_url}, headers=self.headers)
        data = response.get_json()
        short_code = data['short_code']

        # Edit the short code to point to a new URL
        new_url = 'https://example.com/edited'
        edit_response = self.app.put('/edit', json={'code': short_code, 'url': new_url}, headers=self.headers)
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(edit_response.get_json()['message'], 'URL updated successfully')

        # Verify that the short code now points to the new URL
        redirect_response = self.app.get(f'/redirect?code={short_code}')
        self.assertEqual(redirect_response.status_code, 302)
        self.assertIn(new_url, redirect_response.location)

    def test_edit_non_existent_short_code(self):
        # Attempt to edit a non-existent short code
        response = self.app.put('/edit', json={'code': 'nonexistent', 'url': 'https://example.com'}, headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['error'], 'Short code not found')

    def test_click_tracking(self):
        # Create a short URL
        original_url = 'https://example.com/track'
        response = self.app.post('/shorten', json={'url': original_url}, headers=self.headers)
        data = response.get_json()
        short_code = data['short_code']

        # Click the URL multiple times
        for _ in range(3):
            redirect_response = self.app.get(f'/redirect?code={short_code}')
            self.assertEqual(redirect_response.status_code, 302)

        # Check popular URLs analytics
        response = self.app.get('/analytics/popular', headers=self.headers)
        data = response.get_json()

        # Verify click count and last access time
        url_data = next(url for url in data if url['short_code'] == short_code)
        self.assertEqual(url_data['click_count'], 3)
        self.assertIsNotNone(url_data['last_accessed_at'])

    def test_analytics_endpoints(self):
        # Create multiple URLs
        urls = [
            'https://example.com/1',
            'https://example.com/2',
            'https://example.com/1'  # Duplicate URL
        ]
        short_codes = []

        for url in urls:
            response = self.app.post('/shorten', json={'url': url}, headers=self.headers)
            data = response.get_json()
            short_codes.append(data['short_code'])

        # Click some URLs
        self.app.get(f'/redirect?code={short_codes[0]}')
        self.app.get(f'/redirect?code={short_codes[0]}')
        self.app.get(f'/redirect?code={short_codes[1]}')

        # Test /analytics/popular
        popular_response = self.app.get('/analytics/popular', headers=self.headers)
        popular_data = popular_response.get_json()
        most_clicked = max(popular_data, key=lambda x: x['click_count'])
        self.assertEqual(most_clicked['short_code'], short_codes[0])
        self.assertEqual(most_clicked['click_count'], 2)

        # Test /analytics/most-shortened
        shortened_response = self.app.get('/analytics/most-shortened', headers=self.headers)
        shortened_data = shortened_response.get_json()
        self.assertEqual(shortened_data[0]['original_url'], 'https://example.com/1')
        self.assertEqual(shortened_data[0]['shortening_count'], 2)

        # Test /analytics/latest
        latest_response = self.app.get('/analytics/latest', headers=self.headers)
        latest_data = latest_response.get_json()
        self.assertEqual(len(latest_data), 3)
        self.assertEqual(latest_data[0]['short_code'], short_codes[2])
        
    def test_missing_api_key(self):
        # Attempt to shorten a URL without an API key
        response = self.app.post('/shorten', json={'url': 'https://example.com'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Invalid or missing API key')
        
    def test_invalid_api_key(self):
        # Attempt to shorten a URL with an invalid API key
        headers = {'X-API-Key': 'invalid-key'}
        response = self.app.post('/shorten', json={'url': 'https://example.com'}, headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Invalid or missing API key')
        
    def test_unauthorized_delete(self):
        # Create a second user
        with app.app_context():
            second_user = User(
                email='second@example.com',
                name='Second User'
            )
            db.session.add(second_user)
            db.session.flush()
            
            # Create API key for second user
            second_api_key_obj = APIKey(user_id=second_user.id)
            second_api_key_obj.key = generate_api_key()
            db.session.add(second_api_key_obj) 
            db.session.commit()
            second_api_key = second_api_key_obj.key
            
        # Create a URL with the first user
        response = self.app.post('/shorten', json={'url': 'https://example.com/unauthorized'}, headers=self.headers)
        data = response.get_json()
        short_code = data['short_code']
        
        # Try to delete the URL with the second user
        headers = {'X-API-Key': second_api_key}
        delete_response = self.app.delete(f'/delete?code={short_code}', headers=headers)
        self.assertEqual(delete_response.status_code, 403)
        self.assertEqual(delete_response.get_json()['error'], 'You do not have permission to delete this URL')
        
    def test_unauthorized_edit(self):
        # Create a second user
        with app.app_context():
            second_user = User(
                email='second@example.com',
                name='Second User'
            )
            db.session.add(second_user)
            db.session.flush()
            
            # Create API key for second user
            second_api_key_obj = APIKey(user_id=second_user.id)
            second_api_key_obj.key = generate_api_key()
            db.session.add(second_api_key_obj)
            db.session.commit()
            second_api_key = second_api_key_obj.key
            
        # Create a URL with the first user
        response = self.app.post('/shorten', json={'url': 'https://example.com/unauthorized'}, headers=self.headers)
        data = response.get_json()
        short_code = data['short_code']
        
        # Try to edit the URL with the second user
        headers = {'X-API-Key': second_api_key}
        edit_response = self.app.put('/edit', json={'code': short_code, 'url': 'https://example.com/edited'}, headers=headers)
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(edit_response.get_json()['error'], 'You do not have permission to edit this URL')

    def test_api_key_encryption(self):
        """Test that API keys are properly encrypted and decrypted."""
        with app.app_context():
            # Generate a new API key
            plain_key = generate_api_key()
            
            # Encrypt the key
            encrypted_key = encrypt_api_key(plain_key)
            
            # Verify that the encrypted key is different from the plain key
            self.assertNotEqual(plain_key, encrypted_key)
            
            # Decrypt the key and verify it matches the original
            decrypted_key = decrypt_api_key(encrypted_key)
            self.assertEqual(plain_key, decrypted_key)
            
            # Test the APIKey model's property
            api_key = APIKey(user_id=self.test_user_id)
            api_key.key = plain_key
            
            # Verify that the encrypted_key attribute contains binary data
            self.assertIsInstance(api_key.encrypted_key, bytes)
            
            # Verify that the key property returns the decrypted key
            self.assertEqual(api_key.key, plain_key)
    
    def test_create_user_endpoint(self):
        """Test the user creation endpoint."""
        # Create a new user
        response = self.app.post('/users', json={
            'email': 'newuser@example.com',
            'name': 'New User'
        })
        
        # Verify the response
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data['message'], 'User created successfully')
        self.assertEqual(data['user']['email'], 'newuser@example.com')
        self.assertEqual(data['user']['name'], 'New User')
        self.assertIsNotNone(data['user']['api_key'])
        
        # Verify the user was created in the database
        with app.app_context():
            user = User.query.filter_by(email='newuser@example.com').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.name, 'New User')
            
            # Verify the API key was created
            api_key = APIKey.query.filter_by(user_id=user.id).first()
            self.assertIsNotNone(api_key)
            
            # Verify the API key works
            headers = {'X-API-Key': data['user']['api_key']}
            response = self.app.post('/shorten', json={'url': 'https://example.com/newuser'}, headers=headers)
            self.assertEqual(response.status_code, 200)
    
    def test_create_user_with_duplicate_email(self):
        """Test creating a user with an email that already exists."""
        # Try to create a user with the same email as the test user
        response = self.app.post('/users', json={
            'email': 'test@example.com',
            'name': 'Duplicate User'
        })
        
        # Verify the response
        self.assertEqual(response.status_code, 409)
        data = response.get_json()
        self.assertEqual(data['error'], 'User with this email already exists')
    
    def test_create_user_without_email(self):
        """Test creating a user without providing an email."""
        # Try to create a user without an email
        response = self.app.post('/users', json={
            'name': 'No Email User'
        })
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data['error'], 'Email is required')
    
    def test_get_user_from_api_key(self):
        """Test that the get_user_from_api_key function works correctly."""
        with app.app_context():
            from app import get_user_from_api_key
            
            # Test with a valid API key
            user = get_user_from_api_key(self.api_key)
            self.assertIsNotNone(user)
            self.assertEqual(user.id, self.test_user_id)
            
            # Test with an invalid API key
            user = get_user_from_api_key('invalid-api-key')
            self.assertIsNone(user)
            
            # Test with None
            user = get_user_from_api_key(None)
            self.assertIsNone(user)
            
    def test_create_url_with_expiry_date(self):
        """Test creating a URL with an expiry date."""
        # Set expiry date to 1 day in the future
        future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        
        # Create a URL with an expiry date
        response = self.app.post('/shorten', 
                               json={'url': 'https://example.com/expiring', 'expiry_date': future_date}, 
                               headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify the expiry date is returned in the response
        self.assertIsNotNone(data['expiry_date'])
        self.assertEqual(data['expiry_date'], future_date)
        
        # Verify we can access the URL
        redirect_response = self.app.get(f"/redirect?code={data['short_code']}")
        self.assertEqual(redirect_response.status_code, 302)  # Redirect status code
    
    def test_expired_url_returns_410(self):
        """Test that an expired URL returns a 410 Gone status code."""
        with app.app_context():
            # Create a URL that is already expired
            expired_date = datetime.utcnow() - timedelta(days=1)
            
            # Create URL directly in the database with an expired date
            url = URL(
                short_code='EXPIR',  # Must be 6 or fewer characters
                original_url='https://example.com/already-expired',
                user_id=self.test_user_id,
                expiry_date=expired_date
            )
            db.session.add(url)
            db.session.commit()
            
            # Try to access the expired URL
            response = self.app.get('/redirect?code=EXPIR')
            
            # Should return 410 Gone
            self.assertEqual(response.status_code, 410)
            data = response.get_json()
            self.assertEqual(data['error'], 'URL has expired')
    
    def test_invalid_expiry_date_format(self):
        """Test that an invalid expiry date format returns a 400 error."""
        # Use an invalid date format
        response = self.app.post('/shorten', 
                               json={'url': 'https://example.com/test', 'expiry_date': 'not-a-date'}, 
                               headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('Invalid expiry date format', data['error'])
    
    def test_past_expiry_date(self):
        """Test that a past expiry date returns a 400 error."""
        # Set expiry date to 1 day in the past
        past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        response = self.app.post('/shorten', 
                               json={'url': 'https://example.com/test', 'expiry_date': past_date}, 
                               headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('Expiry date must be in the future', data['error'])
        
    def test_custom_short_code(self):
        """Test creating a URL with a custom short code."""
        custom_code = 'custom'
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/custom-test', 'custom_code': custom_code},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['short_code'], custom_code)
        
        # Verify we can access the URL with the custom code
        redirect_response = self.app.get(f"/redirect?code={custom_code}")
        self.assertEqual(redirect_response.status_code, 302)  # Redirect status code
    
    def test_custom_code_already_in_use(self):
        """Test that using an existing custom code returns a 409 error."""
        # First create a URL with a custom code
        custom_code = 'taken'
        self.app.post('/shorten',
                   json={'url': 'https://example.com/first', 'custom_code': custom_code},
                   headers=self.headers)
        
        # Try to use the same custom code again
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/second', 'custom_code': custom_code},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 409)  # Conflict
        data = response.get_json()
        self.assertIn('already in use', data['error'])
    
    def test_invalid_custom_code_format(self):
        """Test that an invalid custom code format returns a 400 error."""
        # Test with a code that's too long
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/test', 'custom_code': 'toolong'},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('must be 1-6', data['error'])
        
        # Test with invalid characters
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/test', 'custom_code': 'inv@lid'},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('alphanumeric characters or hyphens', data['error'])
        
    def test_create_url_with_timeout(self):
        """Test creating a URL with a timeout value."""
        timeout_seconds = 60  # 1 minute timeout
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/timeout-test', 'timeout_seconds': timeout_seconds},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['timeout_seconds'], timeout_seconds)
        
    def test_invalid_timeout_value(self):
        """Test that an invalid timeout value returns a 400 error."""
        # Test with a negative timeout
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/test', 'timeout_seconds': -10},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('Timeout must be a positive integer', data['error'])
        
        # Test with a non-integer timeout
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/test', 'timeout_seconds': 'invalid'},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('Timeout must be a valid integer', data['error'])
        
    def test_url_timeout(self):
        """Test that a URL with a timeout returns a 410 status code after timeout."""
        with app.app_context():
            # Create a URL with a very short timeout (1 second)
            timeout_code = 'TIMEO'
            url = URL(
                short_code=timeout_code,
                original_url='https://example.com/timeout',
                timeout_seconds=1,  # 1 second timeout
                last_accessed_at=datetime.utcnow() - timedelta(seconds=2)  # Set last access to 2 seconds ago
            )
            db.session.add(url)
            db.session.commit()
            
            # Try to access the timed out URL
            response = self.app.get(f'/redirect?code={timeout_code}')
            
            # Should return 410 Gone
            self.assertEqual(response.status_code, 410)
            data = response.get_json()
            self.assertIn('timed out', data['error'])
            
    def test_batch_shorten_urls_with_enterprise_tier(self):
        """Test the batch URL shortening endpoint with enterprise tier user."""
        # Create a batch of URLs
        batch_data = {
            'urls': [
                {'url': 'https://example.com/batch1'},
                {'url': 'https://example.com/batch2', 'custom_code': 'batch'},
                {'url': 'https://example.com/batch3', 'timeout_seconds': 60}
            ]
        }
        
        # Use enterprise user headers
        response = self.app.post('/shorten/batch',
                             json=batch_data,
                             headers=self.enterprise_headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Check the response structure
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['successful'], 3)
        self.assertEqual(data['failed'], 0)
        self.assertEqual(len(data['results']), 3)
        
        # Check each result
        for result in data['results']:
            self.assertTrue(result['success'])
            self.assertIn('short_code', result)
            self.assertIn('short_url', result)
            
            # Check the custom code
            if result['original_url'] == 'https://example.com/batch2':
                self.assertEqual(result['short_code'], 'batch')
                
            # Check the timeout
            if result['original_url'] == 'https://example.com/batch3':
                self.assertEqual(result['timeout_seconds'], 60)
                
    def test_batch_shorten_urls_with_hobby_tier(self):
        """Test the batch URL shortening endpoint with hobby tier user (should be denied)."""
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
        data = response.get_json()
        
        # Check the error message
        self.assertIn('Access denied', data['error'])
        self.assertEqual(data['current_tier'], 'hobby')
        self.assertEqual(data['required_tier'], 'enterprise')
                
    def test_batch_with_errors(self):
        """Test the batch URL shortening endpoint with some invalid URLs."""
        # Create a batch with some invalid URLs
        batch_data = {
            'urls': [
                {'url': 'https://example.com/valid'},  # Valid URL
                {'url': ''},  # Empty URL
                {'url': 'https://example.com/invalid', 'timeout_seconds': -10}  # Invalid timeout
            ]
        }
        
        # Use enterprise user headers (since hobby users can't access this endpoint)
        response = self.app.post('/shorten/batch',
                             json=batch_data,
                             headers=self.enterprise_headers)
        
        # Should return 207 Multi-Status for partial success
        self.assertEqual(response.status_code, 207)
        data = response.get_json()
        
        # Check the response structure
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['successful'], 1)
        self.assertEqual(data['failed'], 2)
        self.assertEqual(len(data['results']), 3)
        
        # Check the successful result
        success_result = next(r for r in data['results'] if r['success'])
        self.assertEqual(success_result['original_url'], 'https://example.com/valid')
        
        # Check the error results
        error_results = [r for r in data['results'] if not r['success']]
        self.assertEqual(len(error_results), 2)
        
        # Check specific errors
        empty_url_error = next(r for r in error_results if r['original_url'] == '')
        self.assertIn('empty', empty_url_error['error'].lower())
        
        # Find the timeout error by checking for the URL with the invalid timeout
        timeout_error = next(r for r in error_results if r['original_url'] == 'https://example.com/invalid')
        self.assertIn('positive', timeout_error['error'].lower())
        
    def test_pricing_tier_update(self):
        """Test updating a user's pricing tier."""
        with app.app_context():
            # Get the hobby user
            hobby_user = User.query.filter_by(email='test@example.com').first()
            self.assertEqual(hobby_user.pricing_tier, 'hobby')
            
            # Update the user's pricing tier to enterprise
            hobby_user.pricing_tier = 'enterprise'
            db.session.commit()
            
            # Verify the update
            updated_user = User.query.filter_by(email='test@example.com').first()
            self.assertEqual(updated_user.pricing_tier, 'enterprise')
            
            # Now the user should be able to access the batch endpoint
            batch_data = {
                'urls': [
                    {'url': 'https://example.com/upgrade-test'}
                ]
            }
            
            response = self.app.post('/shorten/batch',
                                 json=batch_data,
                                 headers=self.hobby_headers)
            
            # Should now return 200 OK instead of 403 Forbidden
            self.assertEqual(response.status_code, 200)
            
    def test_update_tier_endpoint(self):
        """Test the endpoint for updating a user's pricing tier."""
        # Get the hobby user ID
        with app.app_context():
            hobby_user = User.query.filter_by(email='test@example.com').first()
            self.assertEqual(hobby_user.pricing_tier, 'hobby')
        
        # Use the enterprise user's API key to update the hobby user's tier
        update_data = {
            'pricing_tier': 'enterprise'
        }
        
        response = self.app.put(
            f'/users/{self.hobby_user_id}/update-tier',
            json=update_data,
            headers=self.enterprise_headers
        )
        
        # Should return 200 OK
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Check the response data
        self.assertEqual(data['user_id'], self.hobby_user_id)
        self.assertEqual(data['pricing_tier'], 'enterprise')
        self.assertIn('User pricing tier updated', data['message'])
        
        # Verify the user can now access the batch endpoint
        batch_data = {
            'urls': [
                {'url': 'https://example.com/api-upgrade-test'}
            ]
        }
        
        batch_response = self.app.post('/shorten/batch',
                                 json=batch_data,
                                 headers=self.hobby_headers)
        
        # Should return 200 OK
        self.assertEqual(batch_response.status_code, 200)
        
    def test_update_tier_invalid_tier(self):
        """Test updating a user's pricing tier with an invalid tier value."""
        update_data = {
            'pricing_tier': 'premium'  # Invalid tier
        }
        
        response = self.app.put(
            f'/users/{self.hobby_user_id}/update-tier',
            json=update_data,
            headers=self.enterprise_headers
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        
        # Check the error message
        self.assertIn('Invalid pricing tier', data['error'])

    def test_make_short_code_inactive(self):
        """Test making a short code inactive by setting an expiry date in the past."""
        # First create a URL
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/to-deactivate'},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        short_code = data['short_code']
        
        # Verify the URL is active (can be accessed)
        redirect_response = self.app.get(f"/redirect?code={short_code}")
        self.assertEqual(redirect_response.status_code, 302)  # Redirect status code
        
        # Set expiry date to 1 day in the past to make it inactive
        past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        edit_response = self.app.put('/edit',
                                  json={'code': short_code, 'expiry_date': past_date},
                                  headers=self.headers)
        
        self.assertEqual(edit_response.status_code, 200)
        edit_data = edit_response.get_json()
        self.assertEqual(edit_data['expiry_date'], past_date)
        self.assertFalse(edit_data['is_active'])
        
        # Verify the URL is now inactive
        inactive_response = self.app.get(f"/redirect?code={short_code}")
        self.assertEqual(inactive_response.status_code, 410)  # Gone status code
        inactive_data = inactive_response.get_json()
        self.assertEqual(inactive_data['error'], 'URL has expired')
    
    def test_reactivate_short_code(self):
        """Test reactivating a short code by clearing its expiry date."""
        with app.app_context():
            # Create a URL that is already expired
            expired_date = datetime.utcnow() - timedelta(days=1)
            
            # Create URL directly in the database with an expired date
            url = URL(
                short_code='REACT',  # Must be 6 or fewer characters
                original_url='https://example.com/to-reactivate',
                user_id=self.test_user_id,
                expiry_date=expired_date
            )
            db.session.add(url)
            db.session.commit()
            
            # Verify the URL is inactive
            inactive_response = self.app.get('/redirect?code=REACT')
            self.assertEqual(inactive_response.status_code, 410)  # Gone status code
            
            # Reactivate by clearing the expiry date
            reactivate_response = self.app.put('/edit',
                                          json={'code': 'REACT', 'expiry_date': None},
                                          headers=self.headers)
            
            self.assertEqual(reactivate_response.status_code, 200)
            reactivate_data = reactivate_response.get_json()
            self.assertIsNone(reactivate_data['expiry_date'])
            self.assertTrue(reactivate_data['is_active'])
            
            # Verify the URL is now active again
            active_response = self.app.get('/redirect?code=REACT')
            self.assertEqual(active_response.status_code, 302)  # Redirect status code
    
    def test_reactivate_short_code_with_future_date(self):
        """Test reactivating a short code by setting its expiry date to the future."""
        with app.app_context():
            # Create a URL that is already expired
            expired_date = datetime.utcnow() - timedelta(days=1)
            
            # Create URL directly in the database with an expired date
            url = URL(
                short_code='REACT2',  # Must be 6 or fewer characters
                original_url='https://example.com/to-reactivate-future',
                user_id=self.test_user_id,
                expiry_date=expired_date
            )
            db.session.add(url)
            db.session.commit()
            
            # Verify the URL is inactive
            inactive_response = self.app.get('/redirect?code=REACT2')
            self.assertEqual(inactive_response.status_code, 410)  # Gone status code
            
            # Reactivate by setting a future expiry date
            future_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
            reactivate_response = self.app.put('/edit',
                                          json={'code': 'REACT2', 'expiry_date': future_date},
                                          headers=self.headers)
            
            self.assertEqual(reactivate_response.status_code, 200)
            reactivate_data = reactivate_response.get_json()
            self.assertEqual(reactivate_data['expiry_date'], future_date)
            self.assertTrue(reactivate_data['is_active'])
            
            # Verify the URL is now active again
            active_response = self.app.get('/redirect?code=REACT2')
            self.assertEqual(active_response.status_code, 302)  # Redirect status code
    
    def test_edit_only_expiry_date(self):
        """Test editing only the expiry date without changing the URL."""
        # First create a URL
        response = self.app.post('/shorten',
                              json={'url': 'https://example.com/expiry-only'},
                              headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        short_code = data['short_code']
        original_url = data['original_url']
        
        # Edit only the expiry date
        future_date = (datetime.utcnow() + timedelta(days=30)).isoformat()
        edit_response = self.app.put('/edit',
                                  json={'code': short_code, 'expiry_date': future_date},
                                  headers=self.headers)
        
        self.assertEqual(edit_response.status_code, 200)
        edit_data = edit_response.get_json()
        
        # Verify that only the expiry date changed, not the URL
        self.assertEqual(edit_data['original_url'], original_url)
        self.assertEqual(edit_data['expiry_date'], future_date)
        
    def test_create_password_protected_url(self):
        """Test creating a password-protected URL."""
        # Create a password-protected URL
        response = self.app.post('/shorten',
                               json={
                                   'url': 'https://example.com/premium-content',
                                   'custom_code': 'PASS',
                                   'password': 'secret123'
                               },
                               headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify the URL is marked as password-protected
        self.assertTrue(data['is_password_protected'])
        self.assertEqual(data['short_code'], 'PASS')
        
        # Verify the password itself is not returned in the response
        self.assertNotIn('password', data)
    
    def test_access_password_protected_url_without_password(self):
        """Test accessing a password-protected URL without providing a password."""
        with app.app_context():
            # Create a password-protected URL directly in the database
            url = URL(
                short_code='SECURE',
                original_url='https://example.com/secure-content',
                user_id=self.test_user_id,
                password='secret123'
            )
            db.session.add(url)
            db.session.commit()
            
            # Try to access without password
            response = self.app.get('/redirect?code=SECURE')
            
            # Should return 401 Unauthorized
            self.assertEqual(response.status_code, 401)
            data = response.get_json()
            self.assertEqual(data['error'], 'This URL is password-protected')
    
    def test_access_password_protected_url_with_correct_password(self):
        """Test accessing a password-protected URL with the correct password."""
        with app.app_context():
            # Create a password-protected URL directly in the database
            url = URL(
                short_code='SECURE2',
                original_url='https://example.com/secure-content-2',
                user_id=self.test_user_id,
                password='secret123'
            )
            db.session.add(url)
            db.session.commit()
            
            # Access with correct password
            response = self.app.get('/redirect?code=SECURE2&password=secret123')
            
            # Should redirect to the original URL
            self.assertEqual(response.status_code, 302)
    
    def test_access_password_protected_url_with_wrong_password(self):
        """Test accessing a password-protected URL with an incorrect password."""
        with app.app_context():
            # Create a password-protected URL directly in the database
            url = URL(
                short_code='SECURE3',
                original_url='https://example.com/secure-content-3',
                user_id=self.test_user_id,
                password='secret123'
            )
            db.session.add(url)
            db.session.commit()
            
            # Access with wrong password
            response = self.app.get('/redirect?code=SECURE3&password=wrongpass')
            
            # Should return 401 Unauthorized
            self.assertEqual(response.status_code, 401)
            data = response.get_json()
            self.assertEqual(data['error'], 'This URL is password-protected')
    
    def test_add_password_to_existing_url(self):
        """Test adding password protection to an existing URL."""
        # First create a URL without password
        response = self.app.post('/shorten',
                               json={'url': 'https://example.com/to-protect'},
                               headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        short_code = data['short_code']
        
        # Verify it's not password-protected
        self.assertFalse(data['is_password_protected'])
        
        # Add password protection
        edit_response = self.app.put('/edit',
                                   json={'code': short_code, 'password': 'newpass123'},
                                   headers=self.headers)
        
        self.assertEqual(edit_response.status_code, 200)
        edit_data = edit_response.get_json()
        
        # Verify it's now password-protected
        self.assertTrue(edit_data['is_password_protected'])
        
        # Try to access without password
        access_response = self.app.get(f'/redirect?code={short_code}')
        self.assertEqual(access_response.status_code, 401)
        
        # Try to access with password
        access_response = self.app.get(f'/redirect?code={short_code}&password=newpass123')
        self.assertEqual(access_response.status_code, 302)
    
    def test_remove_password_from_url(self):
        """Test removing password protection from a URL."""
        with app.app_context():
            # Create a password-protected URL directly in the database
            url = URL(
                short_code='REMOVE',
                original_url='https://example.com/remove-protection',
                user_id=self.test_user_id,
                password='secret123'
            )
            db.session.add(url)
            db.session.commit()
            
            # Verify it requires a password
            response = self.app.get('/redirect?code=REMOVE')
            self.assertEqual(response.status_code, 401)
            
            # Remove password protection
            edit_response = self.app.put('/edit',
                                       json={'code': 'REMOVE', 'password': None},
                                       headers=self.headers)
            
            self.assertEqual(edit_response.status_code, 200)
            edit_data = edit_response.get_json()
            
            # Verify it's no longer password-protected
            self.assertFalse(edit_data['is_password_protected'])
            
            # Verify it can now be accessed without a password
            access_response = self.app.get('/redirect?code=REMOVE')
            self.assertEqual(access_response.status_code, 302)
    
    def test_batch_create_with_password_protection(self):
        """Test creating a batch of URLs including password-protected ones."""
        # Create a batch of URLs, including a password-protected one
        response = self.app.post('/shorten/batch',
                               json={
                                   'urls': [
                                       {'url': 'https://example.com/batch1'},
                                       {'url': 'https://example.com/batch2', 'password': 'batchpass'}
                                   ]
                               },
                               headers=self.enterprise_headers)  # Only enterprise users can use batch
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify both URLs were created successfully
        self.assertEqual(data['successful'], 2)
        
        # Find the password-protected URL in the results
        password_protected_url = None
        for result in data['results']:
            if result['original_url'] == 'https://example.com/batch2':
                password_protected_url = result
                break
        
        # Verify it's marked as password-protected
        self.assertIsNotNone(password_protected_url)
        self.assertTrue(password_protected_url['is_password_protected'])
        
    def test_get_user_urls(self):
        """Test retrieving all URLs for a user."""
        # First create several URLs for the user with distinct original URLs to identify them
        test_id = ''.join(random.choices(string.ascii_lowercase, k=6))  # Generate a unique identifier
        
        # Create URLs with different properties
        urls_to_create = [
            {'url': f'https://example.com/list1-{test_id}'},
            {'url': f'https://example.com/list2-{test_id}', 'password': 'listpass'},
            {'url': f'https://example.com/list3-{test_id}', 'expiry_date': (datetime.utcnow() + timedelta(days=30)).isoformat()}
        ]
        
        # Create the URLs and store the responses
        created_urls = []
        for url_data in urls_to_create:
            response = self.app.post('/shorten', json=url_data, headers=self.headers)
            self.assertEqual(response.status_code, 200, f"Failed to create URL: {response.get_json()}")
            created_urls.append(response.get_json())
        
        # Mark one URL as deleted to test inactive URLs
        deleted_short_code = created_urls[2]['short_code']
        delete_response = self.app.delete(f'/delete?code={deleted_short_code}', headers=self.headers)
        self.assertEqual(delete_response.status_code, 200, "Failed to delete URL")
        
        # Now retrieve all URLs for the user (default query returns all active URLs)
        response = self.app.get('/user/urls', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Check that the response contains the expected structure
        self.assertIn('urls', data)
        self.assertIn('pagination', data)
        self.assertIn('filters', data)
        
        # Verify pagination information
        self.assertEqual(data['pagination']['page'], 1)
        
        # Get all original URLs from the response
        returned_urls = [url['original_url'] for url in data['urls']]
        
        # Verify that the active URLs are in the response
        # The first two URLs should be returned in the default query
        for i in range(2):
            url_data = urls_to_create[i]
            self.assertTrue(any(url_data['url'] == returned_url for returned_url in returned_urls), 
                          f"URL {url_data['url']} not found in response")
        
        # Now specifically request inactive (deleted) URLs
        inactive_response = self.app.get('/user/urls?is_deleted=true', headers=self.headers)
        self.assertEqual(inactive_response.status_code, 200)
        inactive_data = inactive_response.get_json()
        
        # Get all original URLs from the inactive response
        inactive_urls = [url['original_url'] for url in inactive_data['urls']]
        
        # The deleted URL should be in the inactive URLs response
        deleted_url = urls_to_create[2]['url']
        self.assertTrue(any(deleted_url == url for url in inactive_urls),
                      f"Deleted URL {deleted_url} not found in inactive URLs response")
        
        # Verify that the URLs contain all expected fields
        expected_fields = [
            'short_code', 'original_url', 'short_url', 'created_at', 'click_count',
            'last_accessed_at', 'is_deleted', 'deleted_at', 'expiry_date',
            'timeout_seconds', 'is_password_protected', 'is_active'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data['urls'][0])
        
        # Test filtering for active URLs only
        active_response = self.app.get('/user/urls?is_active=true', headers=self.headers)
        active_data = active_response.get_json()
        
        # All URLs in the response should be active
        for url in active_data['urls']:
            self.assertTrue(url['is_active'])
        
        # Test filtering for password-protected URLs
        password_response = self.app.get('/user/urls?is_password_protected=true', headers=self.headers)
        password_data = password_response.get_json()
        
        # All URLs in the response should be password-protected
        for url in password_data['urls']:
            self.assertTrue(url['is_password_protected'])

if __name__ == '__main__':
    unittest.main()
