import os
import sys
from app import app

if __name__ == '__main__':
    # Force SQLite for local development
    sqlite_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'url_shortener.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
    
    # Run the app
    app.run(host='0.0.0.0', port=5002, debug=True)
