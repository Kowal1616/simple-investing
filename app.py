import os
import logging
from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.base import STATE_RUNNING
from dotenv import load_dotenv

from models_v2 import db, Portfolios
import helpers_v2 as helpers

# Load environment variables
load_dotenv()

# Initialize scheduler globally so it can be shut down
scheduler = BackgroundScheduler(timezone='Europe/Berlin')

def create_app():
    """Create and configure the Flask application."""
    # Configure application
    # instance_relative_config=True ensures Flask looks for instance/financial_data.db
    flask_app = Flask(__name__, instance_relative_config=True)

    flask_app.debug = False

    # Configure SQLAlchemy Library to use SQLite database
    # With instance_relative_config=True, this path is relative to the instance folder
    # However, for simplicity in this project structure, we might want it in root or handle it dynamically.
    # The previous code used os.path.join(os.path.dirname(__file__), 'financial_data.db') which is root.
    # Let's stick to root for now as that's where the user put the DB.
    
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'financial_data_v2.db')
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize SQLAlchemy with the app
    db.init_app(flask_app)

    # Configure the logging system
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    # Create all tables if they don't exist
    with flask_app.app_context():
        db.create_all()

    return flask_app


# Call factory function to create the app instance
app = create_app()


@app.route("/")
def index():
    """Render the index page."""
    # Index page content is rendered via Grid.js + /api/data route
    return render_template("index.html")

@app.route('/portfolios')
def portfolios():
    """Render the portfolios page."""
    return render_template('portfolios.html')

@app.route('/etfs')
def etfs():
    """Render the ETFs page."""
    return render_template('etfs.html')

@app.route('/about')
def about():
    """Render the about page."""
    return render_template('about.html')


@app.route('/api/data')
def data():
    """Return portfolio data as JSON."""
    # Create a session
    session = db.session()

    try:
        # Query database for basic portfolios data
        portfolios_list = session.query(Portfolios).all()
        
        # Compute portfolio returns dynamically
        all_returns = helpers.get_portfolio_returns(session)

        # Convert to list of dictionaries
        json_data = []
        for portfolio, returns in zip(portfolios_list, all_returns):
            rounded_row = {
                "name": portfolio.name,
                "assets": int(portfolio.assets),
                "return5": float(round(returns[0], 2)),
                "return10": float(round(returns[1], 2)),
                "return20": float(round(returns[2], 2)),
                "return30": float(round(returns[3], 2))
            }
            json_data.append(rounded_row)

        # Convert to JSON and return
        return jsonify(json_data)
    finally:
        # Close the session
        session.close()


def update():
    """Perform periodic data updates."""
    # Call helpers functions
    try:
        # Retrive data from online sources
        etfs_prices = helpers.get_etfs_data(db.session)

        # Append historical_data_etfs table
        helpers.append_etfs_prices(etfs_prices, db.session)

        # Compute etfs yields
        # (Calculated but no longer stored in DB)
        etfs_yields = helpers.get_etfs_yields(db.session)

        # Compute portfolios returns 
        # (Calculated but no longer stored in DB)
        portfolios_returns = helpers.get_portfolio_returns(db.session)

        # Compute inflation rates
        currencies_inflation = helpers.get_inflation(db.session)

        # Compute portfolios historical results
        portfolios_results = helpers.get_portfolios_results(db.session)

        # Compute portfolios maximum drawdown
        portfolios_drawdown = helpers.get_portfolios_drawdown(portfolios_results)

    except Exception as e:
        logging.error('An error occurred in update(): %s', e, exc_info=True)
        helpers.update_error_email(e)


# Shut down the scheduler when application ends
@app.teardown_appcontext
def shutdown_scheduler(error):
    if scheduler.state == STATE_RUNNING:
        scheduler.shutdown()

def start_scheduler():
    """Start the background scheduler if not already running."""
    if not scheduler.running:
        # misfire_grace_time=3600 allows jobs to run even if the scheduler was down/busy for up to an hour
        scheduler.add_job(func=update, trigger=CronTrigger(day='10', hour='4'), misfire_grace_time=3600)
        scheduler.start()

if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True)
else:
    # If imported (e.g. by Gunicorn), allow scheduler to start
    # Note: In multi-worker environments (like Gunicorn with multiple workers), 
    # this might cause the job to run multiple times. 
    # For a simple app, this is acceptable, but for production, use a dedicated worker.
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true': # Prevent double execution in Flask debug reloader
         start_scheduler()
