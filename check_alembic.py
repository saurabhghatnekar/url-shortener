from app import app, db
import sqlalchemy as sa

def check_alembic_version():
    with app.app_context():
        try:
            result = db.session.execute(sa.text('SELECT * FROM alembic_version'))
            versions = [row for row in result]
            if versions:
                print(f"Found alembic versions: {versions}")
            else:
                print("No alembic versions found.")
        except Exception as e:
            print(f"Error checking alembic_version: {e}")
            # If the table doesn't exist, let's create it
            try:
                db.session.execute(sa.text('CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))'))
                db.session.commit()
                print("Created alembic_version table.")
            except Exception as create_error:
                print(f"Error creating alembic_version table: {create_error}")

if __name__ == "__main__":
    check_alembic_version()
