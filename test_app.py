import unittest
from datetime import datetime, timedelta
from app import app, db, URL, User, APIKey, generate_api_key, encrypt_api_key, decrypt_api_key

class URLShortenerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Create a new database for testing
        with app.app_context():
            db.drop_all()  # Drop all tables first
            db.create_all()  # Create fresh tables
            
            # Create a test user
            test_user = User(
                email='test@example.com',
                name='Test User'
            )
            db.session.add(test_user)
            db.session.flush()  # Flush to get the user ID
            
            # Store the user ID for tests
            self.test_user_id = test_user.id
            
            # Create an API key for the test user
            api_key_value = generate_api_key()
            test_api_key = APIKey(user_id=self.test_user_id)
            test_api_key.key = api_key_value
            db.session.add(test_api_key)
            db.session.commit()
            
            # Store the API key for tests
            self.api_key = api_key_value
            self.headers = {'X-API-Key': self.api_key}

    def tearDown(self):
        # Drop the database after testing
        with app.app_context():
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

if __name__ == '__main__':
    unittest.main()
