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
   - Request body: JSON with `url` field
   - Example:
     ```bash
     curl -X POST -H "Content-Type: application/json" \
          -d '{"url":"https://example.com"}' \
          http://localhost:5002/shorten
     ```
   - Response:
     ```json
     {
       "short_code": "abc123",
       "original_url": "https://example.com",
       "short_url": "http://localhost:5002/redirect?code=abc123"
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
    last_accessed_at TIMESTAMP
);
```

Key features:
- Multiple short codes can point to the same URL
- Click tracking for each short code
- Last access time tracking
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
- Click tracking accuracy
- Analytics endpoints
- Real-time SSE updates
- Error handling for invalid URLs
- Database constraints and data integrity