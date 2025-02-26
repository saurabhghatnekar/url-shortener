from app import app, db, User, URL, generate_api_key
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tables():
    """Create database tables and sample users."""
    with app.app_context():
        # Drop existing tables
        db.drop_all()
        
        # Create tables
        db.create_all()
        
        # Create sample users
        sample_users = [
            User(email='user1@example.com', name='User One', api_key=generate_api_key()),
            User(email='user2@example.com', name='User Two', api_key=generate_api_key()),
            User(email='user3@example.com', name='User Three', api_key=generate_api_key())
        ]
        db.session.add_all(sample_users)
        db.session.commit()
        
        # Log the API keys for the client
        for user in sample_users:
            logger.info(f'Created user: {user.email} with API key: {user.api_key}')

if __name__ == '__main__':
    create_tables()
