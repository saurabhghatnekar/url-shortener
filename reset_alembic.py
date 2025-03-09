from app import app, db
import sqlalchemy as sa

def reset_alembic_version():
    with app.app_context():
        try:
            # Drop the alembic_version table
            db.session.execute(sa.text('DROP TABLE IF EXISTS alembic_version'))
            db.session.commit()
            print("Dropped alembic_version table.")
            
            # Create a new empty alembic_version table
            db.session.execute(sa.text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))'))
            db.session.commit()
            print("Created new empty alembic_version table.")
        except Exception as e:
            print(f"Error resetting alembic_version: {e}")

if __name__ == "__main__":
    reset_alembic_version()
