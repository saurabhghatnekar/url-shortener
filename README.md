# URL Shortener Service

A simple URL shortener service built with Python and Flask, using PostgreSQL as the database. Features include URL analytics, real-time updates via Server-Sent Events (SSE), and click tracking.

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

## Running Locally

To run the application locally, follow these steps:

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd url-shortener-py
   ```

2. **Set Up a Virtual Environment** (optional but recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**
   ```bash
   python app.py
   ```

The application will start on `http://localhost:5002`. You can test the APIs using a tool like Postman or `curl`. Ensure port 5002 is available or modify the port in `app.py` if needed.

## Local Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd url-shortener-py
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Unix/macOS
# OR
.\venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

The server will start at http://localhost:5002

Note: The application uses PostgreSQL as the database. Make sure to set up your database connection string in the environment variables.

## API Endpoints

1. **Shorten URL**
   - **POST** `/shorten`
   - Creates a new short code for a URL (allows multiple short codes for the same URL)
   - Request body: JSON with the following fields:
     - `url` (required): The URL to shorten
     - `custom_code` (optional): A custom short code (1-6 alphanumeric characters or hyphens)
     - `expiry_date` (optional): ISO format date when the URL will expire (e.g., "2026-01-01T00:00:00")
     - `timeout_seconds` (optional): Number of seconds of inactivity after which the URL will time out
   - Example:
     ```bash
     curl -X POST -H "Content-Type: application/json" \
          -H "X-API-Key: your_api_key" \
          -d '{"url":"https://example.com", "custom_code":"demo", "timeout_seconds":3600}' \
          http://localhost:5002/shorten
     ```
   - Response:
     ```json
     {
       "short_code": "demo",
       "original_url": "https://example.com",
       "short_url": "http://localhost:5002/redirect?code=demo",
       "expiry_date": null,
       "timeout_seconds": 3600
     }
     ```

2. **Redirect to Original URL**
   - **GET** `/redirect?code={code}`
   - Redirects to the original URL and tracks click count and last access time
   - Example: http://localhost:5002/redirect?code=abc123

3. **Analytics Dashboard**
   - **GET** `/analytics`
   - Web interface showing real-time URL creation and analytics
   - Updates automatically via Server-Sent Events

4. **Most Popular URLs**
   - **GET** `/analytics/popular`
   - Returns top 10 most clicked URLs with click counts
   - Example:
     ```bash
     curl http://localhost:5002/analytics/popular
     ```
   - Response:
     ```json
     [
       {
         "short_code": "abc123",
         "original_url": "https://example.com",
         "click_count": 42,
         "last_accessed_at": "2025-02-21T14:30:00Z"
       }
     ]
     ```

5. **Most Shortened URLs**
   - **GET** `/analytics/most-shortened`
   - Returns top 10 URLs that have been shortened most frequently
   - Example:
     ```bash
     curl http://localhost:5002/analytics/most-shortened
     ```
   - Response:
     ```json
     [
       {
         "original_url": "https://example.com",
         "shortening_count": 5,
         "short_codes": ["abc123", "def456", "ghi789"]
       }
     ]
     ```

6. **Batch URL Shortening**
   - **POST** `/shorten/batch`
   - Creates multiple short URLs in a single request
   - Request body: JSON with an array of URL objects
   - Example:
     ```bash
     curl -X POST -H "Content-Type: application/json" \
          -H "X-API-Key: your_api_key" \
          -d '{
            "urls": [
              {"url": "https://example.com/page1", "custom_code": "page1"},
              {"url": "https://example.com/page2", "timeout_seconds": 3600},
              {"url": "https://example.com/page3", "expiry_date": "2026-01-01T00:00:00"}
            ]
          }' \
          http://localhost:5002/shorten/batch
     ```
   - Response:
     ```json
     {
       "total": 3,
       "successful": 3,
       "failed": 0,
       "results": [
         {
           "original_url": "https://example.com/page1",
           "success": true,
           "short_code": "page1",
           "short_url": "http://localhost:5002/redirect?code=page1",
           "expiry_date": null,
           "timeout_seconds": null
         },
         {
           "original_url": "https://example.com/page2",
           "success": true,
           "short_code": "abc123",
           "short_url": "http://localhost:5002/redirect?code=abc123",
           "expiry_date": null,
           "timeout_seconds": 3600
         },
         {
           "original_url": "https://example.com/page3",
           "success": true,
           "short_code": "def456",
           "short_url": "http://localhost:5002/redirect?code=def456",
           "expiry_date": "2026-01-01T00:00:00",
           "timeout_seconds": null
         }
       ]
     }
     ```
   - See `/docs/batch_api.md` for detailed documentation

## Performance Testing

To test the performance of the application, you can use `oha` to simulate traffic. Below are the results from testing the `/shorten` and `/redirect` endpoints with 10 simultaneous requests:

### /shorten Endpoint
- **p50**: 0.0500 seconds
- **p90**: 0.0705 seconds
- **p95**: 0.0705 seconds
- **p99**: 0.0705 seconds

### /redirect Endpoint
- **p50**: 1.0180 seconds
- **p90**: 1.0766 seconds
- **p95**: 1.0766 seconds
- **p99**: 1.0766 seconds

### How to Run Load Tests
1. Install `oha` using Homebrew:
   ```bash
   brew install oha
   ```
2. Run the load test for the `/shorten` endpoint:
   ```bash
   oha -n 10 -c 10 -m POST -H "Content-Type: application/json" -d '{"url": "https://example.com"}' http://localhost:5002/shorten
   ```
3. Run the load test for the `/redirect` endpoint:
   ```bash
   oha -n 10 -c 10 "http://localhost:5002/redirect?code=SQeltg"
   ```

These tests will help you assess the performance of your application under load.

## Database Schema

The application uses PostgreSQL with the following schema:
```sql
CREATE TABLE urls (
    short_code VARCHAR(6) NOT NULL PRIMARY KEY,
    original_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    click_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    user_id INTEGER REFERENCES users(id),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    expiry_date TIMESTAMP,
    timeout_seconds INTEGER
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    name VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    encrypted_key BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);
```

Key features:
- Multiple short codes can point to the same URL
- Click tracking for each short code
- Last access time tracking
- URL expiration based on date
- URL timeout based on inactivity
- User management and API key authentication
- Soft delete functionality
- Timestamps in UTC

## Running Tests

1. **Unit Tests**
   ```bash
   python -m pytest test_app.py
   ```

2. **Test Coverage**
   ```bash
   coverage run -m pytest test_app.py
   coverage report
   ```

Key test cases:
- URL shortening with duplicate URLs
- Custom short code validation
- URL expiration functionality
- URL timeout functionality
- Batch URL shortening
- API key authentication

## Features

### Custom Short Codes
- Create memorable, branded short URLs with custom codes
- Validation ensures codes are 1-6 alphanumeric characters or hyphens
- Prevents duplicate codes with appropriate error handling

### URL Expiration
- Set an expiry date for URLs that should only be valid for a limited time
- Expired URLs return a 410 Gone status code
- ISO format date strings for easy integration

### URL Timeout
- Set an inactivity timeout for URLs
- URLs become invalid after the specified period of inactivity
- Useful for temporary links or links that should only be valid for a short time after they're last accessed

### Batch URL Processing
- Create multiple short URLs in a single API request
- Detailed success/failure information for each URL
- Efficient for bulk processing
- Appropriate status codes for different scenarios (200, 207, 400)

### API Key Authentication
- Secure API access with encrypted API keys
- User management with email-based accounts
- API key generation and validation
- Click tracking accuracy
- Analytics endpoints
- Real-time SSE updates
- Error handling for invalid URLs
- Database constraints and data integrity