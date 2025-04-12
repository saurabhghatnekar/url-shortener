#!/bin/bash

# Exit on error
set -e

echo "Starting URL Shortener application..."

# Set environment variables if not already set
export FLASK_ENV=${FLASK_ENV:-production}
export FLASK_APP=${FLASK_APP:-app.py}
export PORT=${PORT:-5002}

# Check if DATABASE_URL is set, otherwise use SQLite
if [ -z "$DATABASE_URL" ]; then
  echo "No DATABASE_URL provided, using SQLite database"
  export DATABASE_URL="sqlite:///url_shortener.db"
fi

# Install dependencies if needed
if [ "$1" == "--install" ]; then
  echo "Installing dependencies..."
  pip install -r requirements.txt
fi

# Run the application with Gunicorn
echo "Starting Gunicorn server on port $PORT..."
gunicorn -b 0.0.0.0:$PORT app:app

echo "Application is running at http://localhost:$PORT"
