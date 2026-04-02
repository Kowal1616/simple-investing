import os
from flask import Flask
from models import db, Portfolios

def verify():
    # usage of instance_relative_config=True
    app = Flask(__name__, instance_relative_config=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financial_data.db'
    db.init_app(app)

    with app.app_context():
        print(f"Checking for DB in instance (via config): {os.path.join(app.instance_path, 'financial_data.db')}")
        
        try:
            count = db.session.query(Portfolios).count()
            print(f"SUCCESS: Found {count} portfolios.")
        except Exception as e:
            print(f"FAILURE: Could not query Portfolios. Error: {e}")

if __name__ == "__main__":
    verify()
