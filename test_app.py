import unittest
from app import app, db, URL

class URLShortenerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Create a new database for testing
        with app.app_context():
            db.drop_all()  # Drop all tables first
            db.create_all()  # Create fresh tables

    def tearDown(self):
        # Drop the database after testing
        with app.app_context():
            db.drop_all()

    def test_multiple_codes_for_same_url(self):
        original_url = 'https://example.com/'

        # First request
        response1 = self.app.post('/shorten', json={'url': original_url})
        data1 = response1.get_json()
        short_code1 = data1['short_code']

        # Second request
        response2 = self.app.post('/shorten', json={'url': original_url})
        data2 = response2.get_json()
        short_code2 = data2['short_code']

        # Assert that different short codes are returned
        self.assertNotEqual(short_code1, short_code2)

        # Check most-shortened analytics
        response = self.app.get('/analytics/most-shortened')
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
        # Create a short code to delete
        original_url = 'https://example.com/delete'
        response = self.app.post('/shorten', json={'url': original_url})
        data = response.get_json()
        short_code = data['short_code']

        # Delete the short code
        delete_response = self.app.delete(f'/delete?code={short_code}')
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.get_json()['message'], 'Short code deleted successfully')

        # Verify that the short code no longer exists
        redirect_response = self.app.get(f'/redirect?code={short_code}')
        self.assertEqual(redirect_response.status_code, 404)

    def test_delete_non_existent_short_code(self):
        # Attempt to delete a non-existent short code
        response = self.app.delete('/delete?code=nonexistent')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['error'], 'Short code not found')

    def test_invalid_url_format(self):
        # Attempt to shorten an invalid URL
        response = self.app.post('/shorten', json={'url': 'invalid-url'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'Invalid URL format')

    def test_missing_url_parameter(self):
        # Attempt to shorten with missing URL parameter
        response = self.app.post('/shorten', json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'URL cannot be empty')

    def test_empty_url(self):
        # Test empty URL string
        response = self.app.post('/shorten', json={'url': ''})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'URL cannot be empty')

        # Test URL with only whitespace
        response = self.app.post('/shorten', json={'url': '   \n\t  '})
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
        response = self.app.post('/shorten', json={'url': original_url})
        data = response.get_json()
        short_code = data['short_code']

        # Edit the short code to point to a new URL
        new_url = 'https://example.com/edited'
        edit_response = self.app.put('/edit', json={'code': short_code, 'url': new_url})
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(edit_response.get_json()['message'], 'URL updated successfully')

        # Verify that the short code now points to the new URL
        redirect_response = self.app.get(f'/redirect?code={short_code}')
        self.assertEqual(redirect_response.status_code, 302)
        self.assertIn(new_url, redirect_response.location)

    def test_edit_non_existent_short_code(self):
        # Attempt to edit a non-existent short code
        response = self.app.put('/edit', json={'code': 'nonexistent', 'url': 'https://example.com'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['error'], 'Short code not found')

    def test_click_tracking(self):
        # Create a short URL
        original_url = 'https://example.com/track'
        response = self.app.post('/shorten', json={'url': original_url})
        data = response.get_json()
        short_code = data['short_code']

        # Click the URL multiple times
        for _ in range(3):
            redirect_response = self.app.get(f'/redirect?code={short_code}')
            self.assertEqual(redirect_response.status_code, 302)

        # Check popular URLs analytics
        response = self.app.get('/analytics/popular')
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
            response = self.app.post('/shorten', json={'url': url})
            data = response.get_json()
            short_codes.append(data['short_code'])

        # Click some URLs
        self.app.get(f'/redirect?code={short_codes[0]}')
        self.app.get(f'/redirect?code={short_codes[0]}')
        self.app.get(f'/redirect?code={short_codes[1]}')

        # Test /analytics/popular
        popular_response = self.app.get('/analytics/popular')
        popular_data = popular_response.get_json()
        most_clicked = max(popular_data, key=lambda x: x['click_count'])
        self.assertEqual(most_clicked['short_code'], short_codes[0])
        self.assertEqual(most_clicked['click_count'], 2)

        # Test /analytics/most-shortened
        shortened_response = self.app.get('/analytics/most-shortened')
        shortened_data = shortened_response.get_json()
        self.assertEqual(shortened_data[0]['original_url'], 'https://example.com/1')
        self.assertEqual(shortened_data[0]['shortening_count'], 2)

        # Test /analytics/latest
        latest_response = self.app.get('/analytics/latest')
        latest_data = latest_response.get_json()
        self.assertEqual(len(latest_data), 3)
        self.assertEqual(latest_data[0]['short_code'], short_codes[2])

if __name__ == '__main__':
    unittest.main()
