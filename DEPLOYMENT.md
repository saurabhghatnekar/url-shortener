# URL Shortener Deployment Guide

This guide provides instructions for deploying the URL Shortener application in different environments.

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- PostgreSQL (recommended for production) or SQLite (for development/testing)

## Deployment Options

### Option 1: Direct Deployment with Gunicorn

This is the simplest deployment method, suitable for development or small-scale production use.

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**
   ```bash
   # For PostgreSQL (recommended for production)
   export DATABASE_URL="postgresql://username:password@localhost:5432/url_shortener"
   
   # Or for SQLite (simpler setup, good for development)
   export DATABASE_URL="sqlite:///url_shortener.db"
   
   # Application settings
   export FLASK_ENV="production"
   export FLASK_APP="app.py"
   export PORT="5002"  # Optional, defaults to 5002
   ```

3. **Run with the Start Script**
   ```bash
   ./start.sh
   ```
   
   Or with Gunicorn directly:
   ```bash
   gunicorn -b 0.0.0.0:5002 app:app
   ```

4. **Access the Application**
   The application will be available at `http://localhost:5002`

### Option 2: Docker Deployment

For more isolated and reproducible deployments, you can use Docker and Docker Compose.

1. **Prerequisites**
   - Docker
   - Docker Compose

2. **Build and Start Containers**
   ```bash
   docker-compose up -d
   ```

3. **Initialize the Database**
   ```bash
   docker-compose exec web python -c "from app import db; db.create_all()"
   ```

4. **Access the Application**
   The application will be available at `http://localhost:5002`

5. **View Logs**
   ```bash
   docker-compose logs -f
   ```

6. **Stop the Application**
   ```bash
   docker-compose down
   ```

### Option 3: Deployment to a Cloud Provider

The URL Shortener can be deployed to various cloud providers:

#### Heroku

1. **Create a Heroku account and install the Heroku CLI**

2. **Login to Heroku**
   ```bash
   heroku login
   ```

3. **Create a new Heroku app**
   ```bash
   heroku create url-shortener-app
   ```

4. **Add PostgreSQL add-on**
   ```bash
   heroku addons:create heroku-postgresql:hobby-dev
   ```

5. **Deploy the application**
   ```bash
   git push heroku main
   ```

6. **Initialize the database**
   ```bash
   heroku run python -c "from app import db; db.create_all()"
   ```

#### AWS Elastic Beanstalk

1. **Install the EB CLI**
   ```bash
   pip install awsebcli
   ```

2. **Initialize EB application**
   ```bash
   eb init -p python-3.8 url-shortener
   ```

3. **Create an environment and deploy**
   ```bash
   eb create url-shortener-env
   ```

4. **Set environment variables**
   ```bash
   eb setenv DATABASE_URL=postgresql://username:password@your-rds-instance:5432/url_shortener
   ```

## Environment Variables

The application uses the following environment variables:

- `DATABASE_URL`: Connection string for the database
- `FLASK_ENV`: Application environment (development, production)
- `FLASK_APP`: The application entry point
- `PORT`: The port to run the application on (default: 5002)
- `SECRET_KEY`: Secret key for session security
- `BASE_URL`: Base URL for generating short links

## Database Migrations

If you make changes to the database schema, you'll need to create and apply migrations:

1. **Create a migration**
   ```bash
   # If using Flask-Migrate
   flask db migrate -m "Description of changes"
   ```

2. **Apply the migration**
   ```bash
   # If using Flask-Migrate
   flask db upgrade
   ```

## Security Considerations

1. **API Keys**: Ensure API keys are securely stored and transmitted
2. **Database Credentials**: Use environment variables for database credentials
3. **HTTPS**: Use HTTPS in production environments
4. **Secret Key**: Use a strong, unique secret key for session management

## Monitoring and Maintenance

1. **Logging**: Configure logging to monitor application activity
2. **Backups**: Regularly backup the database
3. **Updates**: Keep dependencies updated to address security vulnerabilities

## Troubleshooting

1. **Database Connection Issues**
   - Verify database credentials and connection string
   - Check network connectivity to the database server

2. **Application Errors**
   - Check application logs for error messages
   - Verify environment variables are correctly set

3. **Performance Issues**
   - Consider adding a caching layer for frequently accessed URLs
   - Optimize database queries and indexes
