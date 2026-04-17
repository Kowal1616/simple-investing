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
from models_v2 import AnnualMacroData, MacroAveragesCache
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
            # Check for duplicates securely without flushing previous failed inserts
            with session.no_autoflush:
                exists = (session.query(HistoricalDataEtfs)
                          .filter_by(date=row['date'], etf_id=row['etf_id'])
                          .first())
                
            if exists:
                logging.info('Row for etf_id=%s date=%s already exists — skipping',
                             row['etf_id'], row['date'])
                continue
            
            # Anonymize source if needed
            source = row.get('source', 'provider_a')
            if source == 'yfinance': source = 'provider_a'
            elif source == 'alphavantage': source = 'provider_b'

            try:
                session.add(HistoricalDataEtfs(
                    date=row['date'],
                    etf_id=row['etf_id'],
                    price=row['price'],
                    is_simulated=False,
                    source=source,
                ))
                session.commit()
            except Exception as loop_ext:
                session.rollback()
                logging.warning(
                    'Insert failed for etf_id=%s date=%s (likely concurrent insert). Exception: %s',
                    row['etf_id'], row['date'], loop_ext
                )

    except Exception as e:
        session.rollback()
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

    CORRECT method for V3 (Monthly Compound Returns):
      1. Compute monthly percentage returns for each ETF.
      2. Blend the Returns using the original startup weight:
           portfolio_return[t] = sum(etf_return[t] * weight for each ETF)
      3. Compound the blended monthly returns into a Wealth Index series.
      4. Compute CAGR on the Wealth series.
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

        # Build blended monthly returns series
        blended_returns: list | None = None
        for etf_id, pct in composition:
            prices = _get_etf_price_series(etf_id, session)
            if not prices or len(prices) < 2:
                blended_returns = None
                break
            
            # Compute monthly returns
            returns = [(prices[i] / prices[i-1]) - 1 for i in range(1, len(prices))]
            weighted_returns = [r * pct for r in returns]
            
            if blended_returns is None:
                blended_returns = weighted_returns
            else:
                # Align from the right (most recent data)
                min_len = min(len(blended_returns), len(weighted_returns))
                blended_returns = [
                    blended_returns[-(min_len - i)] + weighted_returns[-(min_len - i)]
                    for i in range(min_len - 1, -1, -1)
                ]
                blended_returns = list(reversed(blended_returns))

        if not blended_returns:
            all_returns.append([0.0] * 5)
            continue

        # Convert the blended returns back into a compounded Wealth Index
        blended_series = [1.0]
        for r in blended_returns:
            blended_series.append(blended_series[-1] * (1 + r))

        n = len(blended_series)
        portfolio_yields = []
        for period, yrs in zip(periods, years):
            if n > period and blended_series[-(period + 1)] and blended_series[-(period + 1)] > 0:
                cagr = round(((blended_series[-1] / blended_series[-(period + 1)]) ** (1 / yrs) - 1) * 100, 2)
                portfolio_yields.append(cagr)
            else:
                portfolio_yields.append(0.0)

        all_returns.append(portfolio_yields)

    return all_returns


# ===========================================================================
# Inflation-adjusted and currency-converted portfolio returns
# ===========================================================================

def get_portfolio_returns_in_currency(session, currency: str = 'EUR') -> list:
    """
    Return nominal CAGR for each portfolio in the requested currency.

    For EUR: returns the raw EUR CAGR series unchanged.
    For PLN: converts EUR CAGR to PLN using pre-computed annualised EUR/PLN
             rate change from MacroAveragesCache.

    Formula (PLN):
        nominal_pln = (1 + eur_cagr/100) * (1 + avg_rate_change/100) - 1

    This is mathematically exact because:
        (rate_end/rate_start)^(1/N) - 1 == avg_eur_rate_change_pct (annualised)

    All heavy lifting (rate averaging) is in the cache — only 2 operations here.
    """
    nominal_eur = get_portfolio_returns(session)   # existing function — EUR CAGR

    if currency == 'EUR':
        return nominal_eur

    # Read pre-computed PLN rate changes from cache
    cache = {
        row.period_years: row
        for row in session.query(MacroAveragesCache)
                          .filter_by(currency_code='PLN').all()
    }

    if not cache:
        logging.warning('MacroAveragesCache empty for PLN — returning EUR data.')
        return nominal_eur

    periods = [5, 10, 20, 30]
    result = []
    for port_eur in nominal_eur:
        pln_returns = []
        for cagr_eur, yrs in zip(port_eur[:4], periods):
            if yrs not in cache or cagr_eur == 0.0:
                pln_returns.append(0.0)
                continue
            rate_chg = (cache[yrs].avg_eur_rate_change_pct or 0.0) / 100
            nominal_pln = ((1 + cagr_eur / 100) * (1 + rate_chg) - 1) * 100
            pln_returns.append(round(nominal_pln, 2))
        result.append(pln_returns)
    return result


def get_real_portfolio_returns(session, currency: str = 'EUR') -> list:
    """
    Return inflation-adjusted (real) CAGR for each portfolio in the requested currency.

    Steps:
      1. Get nominal CAGR in the target currency (via get_portfolio_returns_in_currency).
      2. Look up pre-computed average annual CPI for the currency and period
         from MacroAveragesCache.
      3. Apply the Fisher formula:
             real_cagr = (1 + nominal/100) / (1 + avg_cpi/100) - 1

    No inflation calculations are performed here — all averages are pre-computed
    by scripts/sync_macro.py and stored in macro_averages_cache.
    """
    nominal_data = get_portfolio_returns_in_currency(session, currency)

    cache = {
        row.period_years: row
        for row in session.query(MacroAveragesCache)
                          .filter_by(currency_code=currency).all()
    }

    if not cache:
        logging.warning('MacroAveragesCache empty for %s — returning nominal data.', currency)
        return nominal_data

    periods = [5, 10, 20, 30]
    result = []
    for port_nominal in nominal_data:
        real_returns = []
        for cagr, yrs in zip(port_nominal, periods):
            if yrs not in cache or cagr == 0.0:
                real_returns.append(0.0)
                continue
            avg_inf = cache[yrs].avg_inflation_pct / 100
            real_cagr = ((1 + cagr / 100) / (1 + avg_inf) - 1) * 100
            real_returns.append(round(real_cagr, 2))
        result.append(real_returns)
    return result





# ===========================================================================
# Max drawdown
# ===========================================================================

def get_portfolios_results(session):
    """
    Build monthly blended portfolio wealth series for each portfolio.
    Returns list of lists of floats (Starting index 100.0).
    """
    portfolios = session.query(Portfolios).all()
    all_results = []

    for portfolio in portfolios:
        composition = (session.query(PortfolioComposition.etf_id,
                                     PortfolioComposition.percentage)
                       .filter_by(portfolio_id=portfolio.id)
                       .all())
        blended_returns: list | None = None

        for etf_id, pct in composition:
            prices = _get_etf_price_series(etf_id, session)
            if not prices or len(prices) < 2:
                blended_returns = None
                break
            
            returns = [(prices[i] / prices[i-1]) - 1 for i in range(1, len(prices))]
            weighted_returns = [r * pct for r in returns]
            
            if blended_returns is None:
                blended_returns = weighted_returns
            else:
                min_len = min(len(blended_returns), len(weighted_returns))
                blended_returns = [
                    blended_returns[-(min_len - i)] + weighted_returns[-(min_len - i)]
                    for i in range(min_len - 1, -1, -1)
                ]
                blended_returns = list(reversed(blended_returns))

        if not blended_returns:
            all_results.append([])
            continue
            
        blended_series = [100.0]
        for r in blended_returns:
            blended_series.append(blended_series[-1] * (1 + r))

        all_results.append(blended_series)

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
    """Log the error and send an alert email + WhatsApp to the administrator."""
    logging.error('Application error: %s', e)
    notifier = SystemNotifier()
    notifier.send_error_alert(
        f'SimpleInvesting database update failed. Error: {e}'
    )

def notify_success(message: str):
    """Log the success and send an info alert via WhatsApp."""
    logging.info('Application success: %s', message)
    notifier = SystemNotifier()
    notifier.send_info_alert(message)
