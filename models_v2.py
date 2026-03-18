from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy
db = SQLAlchemy()

class InflationRates(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    year = db.Column(db.Integer, nullable=False)
    currency_code = db.Column(db.String, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class Etfs(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    ticker = db.Column(db.String, nullable=False)
    isin = db.Column(db.String, nullable=False)
    asset_type = db.Column(db.String, nullable=False)
    currency = db.Column(db.String, nullable=False)
    external_ticker = db.Column(db.String, nullable=False)

class HistoricalDataEtfs(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.String, nullable=False)  # Store as YYYY-MM-DD
    etf_id = db.Column(db.Integer, db.ForeignKey("etfs.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    is_simulated = db.Column(db.Boolean, default=False)
    # Source: 'provider_a', 'provider_b', 'index_proxy', 'extrapolated'
    source = db.Column(db.String, default='provider_a')
    __table_args__ = (
        db.UniqueConstraint('date', 'etf_id', name='uq_date_etf'),
    )

class Portfolios(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    assets = db.Column(db.Integer, nullable=False, default=0)
    stocks = db.Column(db.Float, nullable=False, default=0)
    bonds = db.Column(db.Float, nullable=False, default=0)
    other = db.Column(db.Float, nullable=False, default=0)

class PortfolioComposition(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey("portfolios.id"), nullable=False)
    etf_id = db.Column(db.Integer, db.ForeignKey("etfs.id"), nullable=False)
    percentage = db.Column(db.Float, nullable=False)
