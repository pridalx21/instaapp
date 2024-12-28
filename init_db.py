import os
from instaapp import app, db

# Delete existing database file
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'instaapp.db')
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"Deleted existing database at {db_path}")

# Create new database with updated schema
with app.app_context():
    db.create_all()
    print("Created new database with updated schema")
