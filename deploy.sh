#!/bin/bash

# Exit on error
set -e

echo "Starting deployment of URL Shortener application..."

# Build and start the Docker containers
echo "Building and starting Docker containers..."
docker-compose down
docker-compose build
docker-compose up -d

# Wait for the database to be ready
echo "Waiting for database to be ready..."
sleep 10

# Run database migrations if needed
echo "Running database migrations..."
docker-compose exec web python -c "from app import db; db.create_all()"

echo "Deployment completed successfully!"
echo "The application is now running at http://localhost:5002"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop the application: docker-compose down"
