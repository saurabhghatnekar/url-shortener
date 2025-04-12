from app import app, db, RequestLog

# Create the RequestLog table in the database
with app.app_context():
    print("Creating RequestLog table...")
    db.create_all()
    print("RequestLog table created successfully.")
