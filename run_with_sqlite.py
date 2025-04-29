import os
import sys

# Set environment variable for SQLite before importing app
os.environ['DATABASE_URL'] = 'sqlite:///url_shortener.db'
os.environ['USE_SQLITE'] = 'True'

# Now import the app
from app import app

if __name__ == '__main__':
    print("Starting URL Shortener with SQLite database...")
    app.run(host='0.0.0.0', port=5002, debug=True)
