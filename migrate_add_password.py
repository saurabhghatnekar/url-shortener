import os
import sys
from datetime import datetime

# Get the database path from environment variable or use default
DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///urls.db')

print(f"Database URL: {DB_PATH}")

# Determine database type and connect accordingly
if DB_PATH.startswith('sqlite:///'):  # SQLite database
    import sqlite3
    
    db_file = DB_PATH[10:]
    print(f"Running migration to add password column to URL table in SQLite database: {db_file}")
    
    # Connect to the database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check if the password column already exists
    cursor.execute("PRAGMA table_info(urls)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'password' not in column_names:
        print("Adding 'password' column to the URLs table...")
        cursor.execute("ALTER TABLE urls ADD COLUMN password TEXT")
        
        # Log the migration
        print(f"Migration completed at {datetime.utcnow().isoformat()}")
    else:
        print("Password column already exists. No migration needed.")
    
    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    
elif 'postgresql' in DB_PATH or 'postgres' in DB_PATH:  # PostgreSQL database
    try:
        import psycopg2
        from psycopg2 import sql
        from urllib.parse import urlparse
        
        # Parse the database URL
        result = urlparse(DB_PATH)
        username = result.username
        password = result.password
        database = result.path[1:]
        hostname = result.hostname
        port = result.port if result.port else 5432
        
        print(f"Running migration to add password column to URL table in PostgreSQL database: {hostname}/{database}")
        
        # Connect to the database
        conn = psycopg2.connect(
            host=hostname,
            database=database,
            user=username,
            password=password,
            port=port
        )
        conn.autocommit = False
        cursor = conn.cursor()
        
        # Check if the password column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'urls' AND column_name = 'password';
        """)
        column_exists = cursor.fetchone()
        
        if not column_exists:
            print("Adding 'password' column to the URLs table...")
            cursor.execute("ALTER TABLE urls ADD COLUMN password TEXT;")
            
            # Log the migration
            print(f"Migration completed at {datetime.utcnow().isoformat()}")
        else:
            print("Password column already exists. No migration needed.")
        
        # Commit the changes and close the connection
        conn.commit()
        cursor.close()
        conn.close()
        
    except ImportError:
        print("Error: psycopg2 module not found. Please install it using: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        sys.exit(1)
        
else:
    print(f"Unsupported database type: {DB_PATH}")
    print("This migration script supports SQLite and PostgreSQL databases only.")
    sys.exit(1)

print("Migration completed successfully!")
