# URL Shortener Service

A simple URL shortener service built with Python and Flask, using SQLite as the database.

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

The server will start at http://localhost:5001

Note: The application uses SQLite as the database, which will be automatically created as `urls.db` in the project directory when you first run the application.

## API Endpoints

1. Shorten URL
   - **POST** `/shorten`
   - Request body: JSON with `url` field
   - Example:
     ```bash
     curl -X POST -H "Content-Type: application/json" \
          -d '{"url":"https://example.com"}' \
          http://localhost:5001/shorten
     ```
   - Response:
     ```json
     {
       "short_code": "abc123",
       "original_url": "https://example.com",
       "short_url": "http://localhost:5001/redirect?code=abc123"
     }
     ```

2. Redirect to Original URL
   - **GET** `/redirect?code={code}`
   - Example: http://localhost:5001/redirect?code=abc123
   - Redirects to the original URL if found

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

## Database

The application uses SQLite with the following schema:
```sql
CREATE TABLE urls (
    short_code VARCHAR(10) NOT NULL PRIMARY KEY,
    original_url VARCHAR(2048) NOT NULL,
    created_at DATETIME
);
```

To view the database contents:
```bash
sqlite3 urls.db "SELECT * FROM urls;"
  
```