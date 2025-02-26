from app import app, db
import sqlalchemy as sa

def check_tables():
    with app.app_context():
        try:
            # For PostgreSQL, we can query the information_schema
            result = db.session.execute(sa.text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            print(f"Tables in database: {tables}")
            
            # Check the structure of the urls table
            result = db.session.execute(sa.text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'urls'
            """))
            columns = [f"{row[0]} ({row[1]}, nullable: {row[2]})" for row in result]
            print(f"Columns in urls table: {columns}")
            
            # Check the structure of the users table
            result = db.session.execute(sa.text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
            """))
            columns = [f"{row[0]} ({row[1]}, nullable: {row[2]})" for row in result]
            print(f"Columns in users table: {columns}")
            
        except Exception as e:
            print(f"Error checking tables: {e}")

if __name__ == "__main__":
    check_tables()
