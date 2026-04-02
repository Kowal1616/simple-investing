import os
from flask import Flask
from models import db, Portfolios

def reproduce():
    app = Flask(__name__)
    # Reproducing the configuration from app.py
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financial_data.db'
    db.init_app(app)

    print(f"App instance path: {app.instance_path}")
    print(f"App root path: {app.root_path}")
    print(f"Config URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        print(f"Checking for DB in root: {os.path.abspath('financial_data.db')}")
        print(f"Exists? {os.path.exists('financial_data.db')}")
        
        print(f"Checking for DB in instance: {os.path.abspath('instance/financial_data.db')}")
        print(f"Exists? {os.path.exists('instance/financial_data.db')}")

        try:
            # Try to access the DB
            # If the DB is not found (or is empty/new in root), this table might not exist or be empty
            # If it creates a new DB, it won't have tables unless we call create_all
            # We want to see if it sees the EXISTING data in instance folder
            count = db.session.query(Portfolios).count()
            print(f"SUCCESS: Found {count} portfolios.")
        except Exception as e:
            print(f"FAILURE: Could not query Portfolios. Error: {e}")

if __name__ == "__main__":
    reproduce()
