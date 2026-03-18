from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy
db = SQLAlchemy()


class InflationRates(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    year = db.Column(db.Integer, nullable=False)
    EUR_inflation_rate = db.Column(db.Float, nullable=False)
    USD_inflation_rate = db.Column(db.Float, nullable=False)
    PLN_inflation_rate = db.Column(db.Float, nullable=False)


class InflationHistoricalPeriods(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    currency = db.Column(db.String, nullable=False)
    inflation5 = db.Column(db.Float, nullable=False)
    inflation10 = db.Column(db.Float, nullable=False)
    inflation20 = db.Column(db.Float, nullable=False)
    inflation30 = db.Column(db.Float, nullable=False)
    inflation40 = db.Column(db.Float, nullable=False)


class Etfs(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    ticker = db.Column(db.String, nullable=False)
    isin = db.Column(db.String, nullable=False)
    asset_type = db.Column(db.String, nullable=False)
    currency = db.Column(
        db.String,
        db.ForeignKey("inflation_historical_periods.currency"),
        nullable=False,
    )
    yfinance_name = db.Column(db.String, nullable=False)
    alphavantage_name = db.Column(db.String, nullable=False)
    yield5 = db.Column(db.Float, nullable=False)
    yield10 = db.Column(db.Float, nullable=False)
    yield20 = db.Column(db.Float, nullable=False)
    yield30 = db.Column(db.Float, nullable=False)
    yield40 = db.Column(db.Float, nullable=False)


class HistoricalDataEtfs(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.String, nullable=False)
    etf1_price = db.Column(db.Float, nullable=False)
    etf2_price = db.Column(db.Float, nullable=False)
    etf3_price = db.Column(db.Float, nullable=False)
    etf4_price = db.Column(db.Float, nullable=False)
    etf5_price = db.Column(db.Float, nullable=False)
    etf6_price = db.Column(db.Float, nullable=False)


class Portfolios(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    assets = db.Column(db.Integer, nullable=False)
    stocks = db.Column(db.Float, nullable=False)
    bonds = db.Column(db.Float, nullable=False)
    other = db.Column(db.Float, nullable=False)
    return5 = db.Column(db.Float, nullable=False)
    return10 = db.Column(db.Float, nullable=False)
    return20 = db.Column(db.Float, nullable=False)
    return30 = db.Column(db.Float, nullable=False)
    return40 = db.Column(db.Float, nullable=False)
    max_drawdown5 = db.Column(db.Float)


class PortfolioComposition(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey("portfolios.id"), nullable=False)
    etf_id = db.Column(db.Integer, db.ForeignKey("etfs.id"), nullable=False)
    percentage = db.Column(db.Float, nullable=False)
