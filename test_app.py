import unittest
from app import app, db, URL

class URLShortenerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Create a new database for testing
        with app.app_context():
            db.create_all()

    def tearDown(self):
        # Drop the database after testing
        with app.app_context():
            db.drop_all()

    def test_duplicate_url(self):
        original_url = 'https://example.com/'

        # First request
        response1 = self.app.post('/shorten', json={'url': original_url})
        data1 = response1.get_json()
        short_code1 = data1['short_code']

        # Second request
        response2 = self.app.post('/shorten', json={'url': original_url})
        data2 = response2.get_json()
        short_code2 = data2['short_code']

        # Assert that the same short code is returned
        self.assertEqual(short_code1, short_code2)

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
        self.assertEqual(response.get_json()['error'], 'Original URL is required')

    def test_redirect_with_invalid_method(self):
        # Attempt to redirect using POST method
        response = self.app.post('/redirect?code=somecode')
        self.assertEqual(response.status_code, 405)

    def test_delete_with_invalid_method(self):
        # Attempt to delete using GET method
        response = self.app.get('/delete?code=somecode')
        self.assertEqual(response.status_code, 405)

if __name__ == '__main__':
    unittest.main()
