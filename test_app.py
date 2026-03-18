from app import app, db, Portfolios
import os

def test_app_config():
    print(f"App instance path: {app.instance_path}")
    print(f"Config URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    expected_db_path = os.path.join(app.instance_path, 'financial_data.db')
    print(f"Expected DB path: {expected_db_path}")
    print(f"Exists? {os.path.exists(expected_db_path)}")

    with app.app_context():
        try:
            count = db.session.query(Portfolios).count()
            print(f"SUCCESS: Found {count} portfolios in the database.")
        except Exception as e:
            print(f"FAILURE: Could not query Portfolios. Error: {e}")

if __name__ == "__main__":
    test_app_config()
