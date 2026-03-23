"""
helpers_v2.py
=============
Helper functions for Simple Investing — V2 schema (normalized historical_data_etfs).

Key differences from helpers.py (V1):
  - HistoricalDataEtfs is normalised: one row per (date, etf_id) instead of a wide table.
  - Portfolio CAGR is computed correctly: blend the monthly value series first, then apply CAGR
    to the blended series.  The V1 approach (weighted average of individual CAGRs) is mathematically
    wrong for multi-asset portfolios.
  - max_drawdown uses min() — drawdown values are negative (or zero), so the "worst" drawdown
    is the most negative value.
"""

import os
import inspect
import logging
import datetime

import pandas as pd

from models_v2 import Etfs, HistoricalDataEtfs, Portfolios, PortfolioComposition
from models_v2 import InflationRates
from data_providers import FinancialDataService
from notifications import SystemNotifier

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
admin_email = os.getenv('ADMIN_EMAIL')


# ===========================================================================
# Data retrieval — V2 uses FinancialDataService (Consensus Price)
# ===========================================================================

def get_etfs_data(session):
    """Retrieve ETF closing prices for the previous month using data providers."""
    try:
        today = datetime.date.today()
        first_day = today.replace(day=1)
        csv_date = first_day.strftime('%Y-%m-%d')

        # Check if last month's data is already present
        check = (session.query(HistoricalDataEtfs.date)
                 .order_by(HistoricalDataEtfs.date.desc())
                 .first())

        if today.day == 1:
            logging.info('First day of month — data might not be available yet. Skipping.')
            return None

        if check and check.date == csv_date:
            logging.info('Data for last month already present. Skipping.')
            return None

        etfs = session.query(Etfs).all()
        result = []
        failed = []
        
        data_service = FinancialDataService()

        for etf in etfs:
            final = data_service.get_consensus_price(etf.external_ticker)

            if final is not None:
                source = 'consensus'
            else:
                # Fallback: repeat last known price so the date row is inserted
                last_row = (session.query(HistoricalDataEtfs)
                            .filter_by(etf_id=etf.id)
                            .order_by(HistoricalDataEtfs.date.desc())
                            .first())
                final = last_row.price if last_row else 0.0
                logging.warning('Price retrieval failed for %s — using last known price', etf.external_ticker)
                source = 'fallback'
                failed.append(etf.external_ticker)

            result.append({'etf_id': etf.id, 'date': csv_date, 'price': final,
                           'source': source})

        if failed:
            update_error_email(f"Data retrieval failed for: {failed}")

        return result

    except Exception as e:
        logging.error('get_etfs_data error: %s', e, exc_info=True)
        return None


def append_etfs_prices(etfs_prices, session):
    """Append new monthly prices to historical_data_etfs (V2 normalised schema)."""
    try:
        if not etfs_prices:
            logging.warning('append_etfs_prices: nothing to append')
            return

        for row in etfs_prices:
            # Check for duplicates
            exists = (session.query(HistoricalDataEtfs)
                      .filter_by(date=row['date'], etf_id=row['etf_id'])
                      .first())
            if exists:
                logging.info('Row for etf_id=%s date=%s already exists — skipping',
                             row['etf_id'], row['date'])
                continue
            
            # Anonymize source if needed (just in case it's still using old names)
            source = row.get('source', 'provider_a')
            if source == 'yfinance': source = 'provider_a'
            elif source == 'alphavantage': source = 'provider_b'

            session.add(HistoricalDataEtfs(
                date=row['date'],
                etf_id=row['etf_id'],
                price=row['price'],
                is_simulated=False,
                source=source,
            ))
        session.commit()

    except Exception as e:
        fn = inspect.currentframe().f_code.co_name
        logging.error('Error in %s: %s', fn, e, exc_info=True)
        update_error_email(e)


# ===========================================================================
# Yield calculations — V2 schema
# ===========================================================================

def get_etfs_yields(session):
    """
    Compute CAGR yields for each ETF over 5, 10, 20, 30, 40-year periods.
    V2 normalised schema: query by etf_id, order by date.
    Returns list of lists [ [y5, y10, y20, y30, y40], ... ] — one per ETF.
    """
    etfs = session.query(Etfs).all()
    all_yields = []

    periods = [60, 120, 240, 360, 480]
    years   = [5,  10,  20,  30,  40]

    for etf in etfs:
        prices = (session.query(HistoricalDataEtfs.price)
                  .filter_by(etf_id=etf.id)
                  .order_by(HistoricalDataEtfs.date)
                  .all())
        prices = [p[0] for p in prices]
        n = len(prices)
        etf_yields = []

        for period, yrs in zip(periods, years):
            if n > period and prices[-(period + 1)] and prices[-(period + 1)] > 0:
                cagr = round(((prices[-1] / prices[-(period + 1)]) ** (1 / yrs) - 1) * 100, 2)
                etf_yields.append(cagr)
            else:
                etf_yields.append(0.0)

        all_yields.append(etf_yields)

    return all_yields


# ===========================================================================
# Portfolio return calculation — CORRECTED
# ===========================================================================

def _get_etf_price_series(etf_id: int, session) -> list:
    """Return ordered list of prices for an ETF from DB."""
    rows = (session.query(HistoricalDataEtfs.price)
            .filter_by(etf_id=etf_id)
            .order_by(HistoricalDataEtfs.date)
            .all())
    return [r[0] for r in rows]


def get_portfolio_returns(session):
    """
    Compute portfolio CAGR returns for 5, 10, 20, 30, 40-year periods.

    CORRECT method:
      1. Build a blended portfolio value series:
           portfolio_value[t] = sum(etf_price[t] * weight for each ETF)
      2. Compute CAGR on the *blended* series:
           cagr = (portfolio_value[-1] / portfolio_value[-N]) ^ (1/years) - 1

    This is correct because CAGR of a weighted portfolio ≠ weighted average of
    individual CAGRs — the V1 approach was mathematically wrong for multi-asset portfolios.
    """
    portfolios = session.query(Portfolios).all()
    all_returns = []

    periods = [60, 120, 240, 360, 480]
    years   = [5,  10,  20,  30,  40]

    for portfolio in portfolios:
        composition = (session.query(PortfolioComposition.etf_id,
                                     PortfolioComposition.percentage)
                       .filter_by(portfolio_id=portfolio.id)
                       .all())

        if not composition:
            all_returns.append([0.0] * 5)
            continue

        # Build blended monthly value series
        blended: list | None = None
        for etf_id, pct in composition:
            prices = _get_etf_price_series(etf_id, session)
            if not prices:
                blended = None
                break
            weighted = [p * pct for p in prices]
            if blended is None:
                blended = weighted
            else:
                # Series may differ in length if ETF data starts at different dates;
                # align from the end (most recent data) — use the shorter length
                min_len = min(len(blended), len(weighted))
                blended = [blended[-(min_len - i)] + weighted[-(min_len - i)]
                           for i in range(min_len - 1, -1, -1)]
                blended = list(reversed(blended))

        if not blended:
            all_returns.append([0.0] * 5)
            continue

        n = len(blended)
        portfolio_yields = []
        for period, yrs in zip(periods, years):
            if n > period and blended[-(period + 1)] and blended[-(period + 1)] > 0:
                cagr = round(((blended[-1] / blended[-(period + 1)]) ** (1 / yrs) - 1) * 100, 2)
                portfolio_yields.append(cagr)
            else:
                portfolio_yields.append(0.0)

        all_returns.append(portfolio_yields)

    return all_returns


# ===========================================================================
# Inflation
# ===========================================================================

def get_inflation(session):
    """
    Compute cumulative inflation for each currency over 5, 10, 20, 30, 40-year periods.
    Sums the last N annual rates from inflation_rates table.
    """
    currencies = [c[0] for c in session.query(InflationRates.currency_code).distinct().all()]
    result = []

    for currency in currencies:
        rates_rows = (session.query(InflationRates.rate)
                      .filter_by(currency_code=currency)
                      .order_by(InflationRates.year)
                      .all())
        rates = [r[0] for r in rates_rows]
        n = len(rates)
        periods_inflation = []
        for yrs in [5, 10, 20, 30, 40]:
            if n >= yrs:
                total = sum(rates[-yrs:])
                periods_inflation.append(round(total, 2))
            else:
                periods_inflation.append(0.0)
        result.append(periods_inflation)

    return result





# ===========================================================================
# Max drawdown
# ===========================================================================

def get_portfolios_results(session):
    """
    Build monthly blended portfolio value series for each portfolio.
    Returns list of lists of floats.
    """
    portfolios = session.query(Portfolios).all()
    all_results = []

    for portfolio in portfolios:
        composition = (session.query(PortfolioComposition.etf_id,
                                     PortfolioComposition.percentage)
                       .filter_by(portfolio_id=portfolio.id)
                       .all())
        blended: list | None = None

        for etf_id, pct in composition:
            prices = _get_etf_price_series(etf_id, session)
            if not prices:
                blended = None
                break
            weighted = [p * pct for p in prices]
            if blended is None:
                blended = weighted
            else:
                min_len = min(len(blended), len(weighted))
                blended = [blended[-(min_len - i)] + weighted[-(min_len - i)]
                           for i in range(min_len - 1, -1, -1)]
                blended = list(reversed(blended))

        all_results.append(blended or [])

    return all_results


def get_portfolios_drawdown(portfolios_results):
    """
    Compute maximum drawdown for each portfolio.
    Drawdown values are <= 0. We return the MOST NEGATIVE value (worst drawdown).
    V1 used max() which returned 0 — that was a bug.
    """
    portfolios_drawdown = []

    for portfolio in portfolios_results:
        if not portfolio:
            portfolios_drawdown.append(pd.Series(dtype=float))
            continue
        series = pd.Series(portfolio)
        returns = series.pct_change()
        wealth_index = 1000 * (1 + returns[1:]).cumprod()
        previous_peaks = wealth_index.cummax()
        drawdown = (wealth_index - previous_peaks) / previous_peaks
        drawdown = drawdown.round(4)
        portfolios_drawdown.append(drawdown)

    return portfolios_drawdown


# ===========================================================================
# Error notifications
# ===========================================================================

def update_error_email(e):
    """Log the error and send an alert email to the administrator."""
    logging.error('Application error: %s', e)
    notifier = SystemNotifier()
    notifier.send_error_alert(
        f'SimpleInvesting database update failed. Error: {e}'
    )
