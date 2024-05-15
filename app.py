from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.base import STATE_RUNNING
from flask import jsonify
from models import db, Portfolios
import helpers
import logging


def initializer():
    # Configure application
    app = Flask(__name__)

    app.debug = False

    # Configure SQLAlchemy Library to use SQLite database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financial_data.db'

    # Initialize SQLAlchemy with the app
    db.init_app(app)

    # Configure the logging system
    logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

    # Create all tables
    with app.app_context():
        db.create_all()

    return app


# Call initializer function
app = initializer()

# Initialize APScheduler
scheduler = BackgroundScheduler()
scheduler.start()


@app.route("/")
def index():
    # Index page content is rendered via Grid.js + /api/data route
    return render_template("index.html")

@app.route('/api/data')
def data():
    # Create a session
    session = db.session()

    try:
        # Query database for portfolios data
        portfolios_data = session.query(
            Portfolios.name,
            Portfolios.assets,
            Portfolios.return5,
            Portfolios.return10,
            Portfolios.return20,
            Portfolios.return30
        ).all()

        # Convert list of tuples to list of dictionaries
        data = []
        for row in portfolios_data:
            # Round numerical values to 2 decimal points
            rounded_row = {
                "name": row[0],
                "assets": int(row[1]),
                "return5": float(round(row[2], 2)),
                "return10": float(round(row[3], 2)),
                "return20": float(round(row[4], 2)),
                "return30": float(round(row[5], 2))
            }
            data.append(rounded_row)

        # Convert to JSON and return
        return jsonify(data)
    finally:
        # Close the session
        session.close()


def update():
    # Call helpers functions
    try:
        # Retrive data from online sources
        etfs_prices = helpers.get_etfs_data(db.session)

        # Append historical_data_etfs table
        helpers.append_etfs_prices(etfs_prices, db.session)

        # Compute etfs yieldswith app.app_context():
        etfs_yields = helpers.get_etfs_yields(db.session)

        # Update ETFs table
        helpers.update_etfs_yields(etfs_yields, db.session)

        # Compute portfolios returns
        portfolios_returns = helpers.get_portfolio_returns(db.session)

        # Update portfolios table
        helpers.update_portfolios_returns(portfolios_returns, db.session)

        # Compute inflation rates
        currencies_inflation = helpers.get_inflation(db.session)

        # Update inflation_historical_periods table
        helpers.update_inflation(currencies_inflation, db.session)

        # Compute portfolios historical results
        portfolios_results = helpers.get_portfolios_results(db.session)

        # Compute portfolios maximum drawdown
        portfolios_drawdown = helpers.get_portfolios_drawdown(portfolios_results)

        # Update portfolios table
        helpers.update_portfolios_drawdown(portfolios_drawdown, db.session)

    except Exception as e:
        logging.error('An error occurred in update(): %s', e, exc_info=True)
        helpers.update_error_email(e)

# Run update once (on 'sturtup')
with app.app_context():
    update()


# Set Scheduler to work in set intervals
scheduler = BackgroundScheduler(timezone='Europe/Berlin')
scheduler.add_job(func=update, trigger=CronTrigger(day='10', hour='4'))
scheduler.start()


# Shut down the scheduler when application ends
@app.teardown_appcontext
def shutdown_scheduler(error):
    if scheduler.state == STATE_RUNNING:
        scheduler.shutdown()

