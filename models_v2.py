from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy
db = SQLAlchemy()


class InflationRates(db.Model):
    """Legacy table — kept for backward compatibility. Data migrated to AnnualMacroData."""
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    year = db.Column(db.Integer, nullable=False)
    currency_code = db.Column(db.String, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class InflationHistoricalPeriods(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    currency = db.Column(db.String, nullable=False)
    inflation5 = db.Column(db.Float, nullable=False)
    inflation10 = db.Column(db.Float, nullable=False)
    inflation20 = db.Column(db.Float, nullable=False)
    inflation30 = db.Column(db.Float, nullable=False)
    inflation40 = db.Column(db.Float, nullable=False)


class AnnualMacroData(db.Model):
    """
    Annual macroeconomic data sourced from FRED (and migrated from InflationRates legacy).
    Stores yearly CPI inflation and the average EUR/currency exchange rate.
    """
    __tablename__ = 'annual_macro_data'
    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    year                 = db.Column(db.Integer, nullable=False)
    currency_code        = db.Column(db.String(3), nullable=False)  # 'EUR', 'PLN'
    annual_inflation_pct = db.Column(db.Float, nullable=False)      # annual CPI change, %
    eur_rate             = db.Column(db.Float, nullable=True)        # avg annual EUR/currency rate
                                                                     # None for EUR (always 1.0)
    __table_args__ = (
        db.UniqueConstraint('year', 'currency_code', name='uq_amd_year_currency'),
    )


class MacroAveragesCache(db.Model):
    """
    Pre-computed macro averages per (currency, period).
    The API reads exclusively from this table — no inflation calculations in endpoints.
    """
    __tablename__ = 'macro_averages_cache'
    id                      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    currency_code           = db.Column(db.String(3), nullable=False)
    period_years            = db.Column(db.Integer, nullable=False)  # 5, 10, 20, 30
    avg_inflation_pct       = db.Column(db.Float, nullable=False)    # mean annual CPI over period
    avg_eur_rate_change_pct = db.Column(db.Float, nullable=True)     # annualized EUR/currency
                                                                     # rate change; None for EUR
    updated_at              = db.Column(db.String, nullable=True)    # ISO timestamp + notes
    __table_args__ = (
        db.UniqueConstraint('currency_code', 'period_years', name='uq_mac_currency_period'),
    )


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

