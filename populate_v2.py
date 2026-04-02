"""
populate_v2.py
==============
Populates financial_data_v2.db from scratch (or top-ups safely on re-run).

Phases:
  1. Copy static data (ETFs, Portfolios, PortfolioComposition, InflationHistoricalPeriods,
     InflationRates) from V1 → V2.
  2. For each ETF:
       a. Fetch real monthly price data via yfinance (primary) and AlphaVantage (fallback).
       b. Fetch real index proxy data for the pre-launch gap:
            SXR8  => ^GSPC  (S&P 500, Yahoo Finance)
            EUNL  => ^MSCIW (MSCI World, stooq CSV)
            IUSQ  => ^MSCIW (MSCI World proxy for ACWI, stooq CSV)
            SYBJ  => BAMLHE00EHY0EY (ICE BofA Euro HY yield, FRED)
            4GLD  => XAUUSD (gold spot, stooq CSV)
            XDWT  => no simulation needed (real YF history covers 30 yrs)
       c. Apply proxy percentage returns backwards from the ETF's first real price
          to fill the gap — rows stored with source='index_proxy'.
       d. If gap still exists after proxy (e.g. proxy data unavailable), fall back
          to simple extrapolation with source='extrapolated'.

Safe to re-run: deletes existing V2 data before re-inserting.
"""

import os
import io
import time
import datetime
import requests
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models_v2 import (db, Etfs, HistoricalDataEtfs, Portfolios,
                       PortfolioComposition, InflationHistoricalPeriods,
                       InflationRates)

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_V1_URI = 'sqlite:///instance/financial_data.db'
DB_V2_URI = 'sqlite:///instance/financial_data_v2.db'
TARGET_MONTHS = 485      # 40+ years
SLEEP_BETWEEN_ETFS = 12  # seconds — keeps YF + AV happy
ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY')

# Map ETF ticker → index proxy config.
# Only entries that need pre-launch simulation are listed.
# Keys are the ETF *ticker* field (as stored in the DB).
# proxy_source: 'yfinance' | 'stooq' | 'fred'
PROXY_CONFIG = {
    'SXR8': {
        'proxy_source': 'yfinance',
        'proxy_ticker': '^GSPC',
        'note': 'S&P 500 index — full history since 1927',
    },
    'IUSQ': {
        'proxy_source': 'yfinance',
        'proxy_ticker': '^GSPC',
        'note': 'S&P 500 as proxy for historical ACWI (since original lacked data)',
    },
    'EUNL': {
        'proxy_source': 'yfinance',
        'proxy_ticker': '^GSPC',
        'note': 'S&P 500 as proxy for historical MSCI World (since original lacked data)',
    },
    '4GLD': {
        'proxy_source': 'stooq',
        'proxy_ticker': 'xauusd',
        'note': 'XAUUSD gold spot — 200+ year history on stooq',
    },
    # SYBJ: FRED API stopped responding with CSV. Extrapolation will take over automatically.
    # XDWT: real YF data goes back to 1985 — no proxy needed.
}

# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------
engine_v1 = create_engine(DB_V1_URI)
SessionV1 = sessionmaker(bind=engine_v1)
session_v1 = SessionV1()

os.makedirs('instance', exist_ok=True)
engine_v2 = create_engine(DB_V2_URI)
db.metadata.create_all(engine_v2)
SessionV2 = sessionmaker(bind=engine_v2)
session_v2 = SessionV2()


# ===========================================================================
# PHASE 1 : Copy static / reference data
# ===========================================================================

def copy_static_data():
    """Copy all reference tables from V1 → V2 (deletes V2 first)."""
    print("\n=== PHASE 1: Copying static data ===")

    # Delete in FK-safe order
    for tbl in ['portfolio_composition', 'portfolios', 'etfs',
                 'inflation_rates', 'inflation_historical_periods']:
        session_v2.execute(text(f'DELETE FROM {tbl}'))
    session_v2.commit()

    # --- InflationHistoricalPeriods ---
    for row in session_v1.execute(text('SELECT * FROM inflation_historical_periods')):
        session_v2.add(InflationHistoricalPeriods(
            currency=row.currency,
            inflation5=row.inflation5,
            inflation10=row.inflation10,
            inflation20=row.inflation20,
            inflation30=row.inflation30,
            inflation40=row.inflation40,
        ))

    # --- InflationRates (year-by-year source table — was empty in V2 before) ---
    rows_ir = list(session_v1.execute(text('SELECT * FROM inflation_rates')))
    for row in rows_ir:
        session_v2.add(InflationRates(
            year=row.year,
            EUR_inflation_rate=row.EUR_inflation_rate,
            USD_inflation_rate=row.USD_inflation_rate,
            PLN_inflation_rate=row.PLN_inflation_rate,
        ))
    print(f"  InflationRates: copied {len(rows_ir)} rows")

    # --- ETFs (without yield columns — those are recomputed by app.py update()) ---
    for row in session_v1.execute(text('SELECT * FROM etfs')):
        session_v2.add(Etfs(
            id=row.id,
            name=row.name,
            ticker=row.ticker,
            isin=row.isin,
            asset_type=row.asset_type,
            currency=row.currency,
            yfinance_name=row.yfinance_name,
            alphavantage_name=row.alphavantage_name,
        ))

    # --- Portfolios ---
    for row in session_v1.execute(text('SELECT * FROM portfolios')):
        session_v2.add(Portfolios(
            id=row.id,
            name=row.name,
            assets=row.assets,
            stocks=row.stocks,
            bonds=row.bonds,
            other=row.other,
        ))

    # --- PortfolioComposition ---
    for row in session_v1.execute(text('SELECT * FROM portfolio_composition')):
        session_v2.add(PortfolioComposition(
            portfolio_id=row.portfolio_id,
            etf_id=row.etf_id,
            percentage=row.percentage,
        ))

    session_v2.commit()
    print("  Static data copy complete.")


# ===========================================================================
# PHASE 2 : Proxy index fetchers
# ===========================================================================

def fetch_stooq_monthly(ticker: str) -> pd.Series:
    """
    Fetch monthly close prices from stooq direct CSV endpoint.
    Returns a pd.Series indexed by month-start dates, sorted ascending.
    """
    url = f'https://stooq.com/q/d/l/?s={ticker}&i=m'
    print(f"  Fetching stooq CSV: {url}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if 'Date' not in df.columns or 'Close' not in df.columns:
            print(f"  Unexpected stooq columns: {df.columns.tolist()}")
            return pd.Series(dtype=float)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        series = df['Close'].dropna()
        # Resample to month-start
        series = series.resample('MS').first().dropna()
        print(f"  stooq OK — {len(series)} rows from {series.index.min().date()} to {series.index.max().date()}")
        return series
    except Exception as e:
        print(f"  stooq fetch error for {ticker}: {e}")
        return pd.Series(dtype=float)


def fetch_fred_monthly(series_id: str) -> pd.Series:
    """
    Fetch monthly data from FRED (Federal Reserve Economic Data).
    Returns a pd.Series of yield values indexed by month-start dates.
    """
    url = (f'https://fred.stlouisfed.org/graph/fredgraph.csv'
           f'?id={series_id}&vintage_date=&realtime_start=&realtime_end=')
    print(f"  Fetching FRED series: {series_id}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), parse_dates=['DATE'])
        df.rename(columns={'DATE': 'Date', series_id: 'Value'}, inplace=True)
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        # FRED may use '.' for missing — replace and drop
        df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
        series = df['Value'].dropna()
        series = series.resample('MS').first().dropna()
        print(f"  FRED OK — {len(series)} rows from {series.index.min().date()} to {series.index.max().date()}")
        return series
    except Exception as e:
        print(f"  FRED fetch error for {series_id}: {e}")
        return pd.Series(dtype=float)


def fred_yields_to_synthetic_prices(yield_series: pd.Series,
                                    anchor_price: float,
                                    anchor_date: pd.Timestamp) -> pd.Series:
    """
    Convert a FRED yield (%) time series into a synthetic price series.

    The yield is an annual %. We convert to monthly and apply backwards:
      price[t-1] = price[t] / (1 + monthly_change)
    where monthly_change = (yield[t] - yield[t-1]) / 12 / 100

    The series is anchored so that the price at anchor_date equals anchor_price.
    Returns a Series of prices (sorted ascending, month-start indexed).
    """
    # Only keep dates before (and up to) anchor
    series = yield_series[yield_series.index <= anchor_date].copy()
    if series.empty:
        return pd.Series(dtype=float)

    # Monthly yield change as fraction
    monthly_changes = series.pct_change().fillna(0) / 12

    # Build price series backwards from anchor
    dates = list(series.index)
    prices = {}

    # Find the closest date to anchor_date to set the starting anchor
    anchor_idx = len(dates) - 1
    prices[dates[anchor_idx]] = anchor_price

    for i in range(anchor_idx - 1, -1, -1):
        chg = monthly_changes.iloc[i + 1]
        prices[dates[i]] = prices[dates[i + 1]] / (1 + chg)

    result = pd.Series(prices).sort_index()
    return result


def apply_proxy_returns_backwards(proxy_series: pd.Series,
                                  anchor_price: float,
                                  anchor_date: pd.Timestamp) -> pd.Series:
    """
    Given a proxy price series, apply its % monthly returns backwards
    starting from anchor_price at anchor_date.

    Result: a Series of synthetic prices (month-start, ascending),
    ending AT anchor_date with anchor_price.
    Only returns dates BEFORE anchor_date.
    """
    # Only keep dates before the anchor
    series = proxy_series[proxy_series.index < anchor_date].copy()
    if series.empty:
        return pd.Series(dtype=float)

    # Compute monthly pct_change on the proxy (ascending order)
    pct = series.pct_change().fillna(0)

    # Walk backwards from anchor
    dates = list(series.index)
    prices = {}
    current_price = anchor_price

    for i in range(len(dates) - 1, -1, -1):
        # The return at date[i+1] relative to date[i] is pct.iloc[i+1] (if i+1 exists)
        if i + 1 < len(dates):
            chg = pct.iloc[i + 1]
        else:
            # Last date in proxy series: use pct change of the date itself
            chg = pct.iloc[i]
        safe_chg = chg if (not pd.isna(chg) and chg > -0.999) else 0.0
        current_price = current_price / (1 + safe_chg)
        prices[dates[i]] = current_price

    result = pd.Series(prices).sort_index()
    return result


def simple_extrapolate_backwards(first_price: float,
                                 first_date: pd.Timestamp,
                                 avg_monthly_return: float,
                                 n_months: int) -> pd.Series:
    """Fallback: extrapolate backwards using average monthly return."""
    prices = {}
    current_price = first_price
    for i in range(1, n_months + 1):
        sim_date = first_date - pd.DateOffset(months=i)
        # Normalize to month-start
        sim_date = sim_date.replace(day=1)
        if abs(avg_monthly_return) > 1e-9:
            current_price = current_price / (1 + avg_monthly_return)
        prices[sim_date] = current_price
    return pd.Series(prices).sort_index()


def fetch_yf_monthly(ticker: str) -> pd.Series:
    """Fetch max monthly price history from Yahoo Finance."""
    print(f"  Fetching yfinance: {ticker}")
    try:
        data = yf.download(ticker, period='max', interval='1mo',
                           auto_adjust=True, progress=False)
        if data.empty:
            print("  YF: empty response")
            return pd.Series(dtype=float)
        # Handle multi-level columns (yfinance >= 0.2)
        if isinstance(data.columns, pd.MultiIndex):
            close_col = ('Close', ticker) if ('Close', ticker) in data.columns else data.columns[0]
            series = data[close_col]
        else:
            series = data['Close']
        series = series.dropna().resample('MS').first().dropna()
        print(f"  YF OK — {len(series)} rows from {series.index.min().date()} to {series.index.max().date()}")
        return series
    except Exception as e:
        print(f"  YF error: {e}")
        return pd.Series(dtype=float)


def fetch_av_monthly(ticker_av: str) -> pd.Series:
    """Fetch monthly adjusted close via AlphaVantage API."""
    if not ALPHAVANTAGE_API_KEY:
        return pd.Series(dtype=float)
    print(f"  Fetching AlphaVantage: {ticker_av}")
    url = (f'https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED'
           f'&symbol={ticker_av}&apikey={ALPHAVANTAGE_API_KEY}&datatype=csv')
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            if 'Thank you for using Alpha Vantage' in resp.text or 'rate limit' in resp.text.lower():
                print(f"  AV rate limit (attempt {attempt+1}/3). Waiting 65s...")
                time.sleep(65)
                continue
            df = pd.read_csv(io.StringIO(resp.text))
            if 'timestamp' not in df.columns or 'adjusted close' not in df.columns:
                print(f"  AV unexpected format")
                return pd.Series(dtype=float)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            series = df['adjusted close'].resample('MS').first().dropna()
            print(f"  AV OK — {len(series)} rows")
            return series
        except Exception as e:
            print(f"  AV error (attempt {attempt+1}/3): {e}")
            time.sleep(10)
    return pd.Series(dtype=float)


# ===========================================================================
# PHASE 2 & 3 : Fetch & populate price history
# ===========================================================================

def fetch_and_populate_prices():
    """Main price population loop for all ETFs."""
    print("\n=== PHASE 2/3: Fetching and populating price history ===")

    # Pre-fetch proxy series (do it once, reuse across ETFs)
    print("\n--- Pre-fetching proxy index series ---")
    proxy_cache = {}
    proxy_cache['stooq_xauusd'] = fetch_stooq_monthly('xauusd')
    proxy_cache['stooq_msciw'] = fetch_stooq_monthly('msciw')
    proxy_cache['fred_hy'] = fetch_fred_monthly('BAMLHE00EHY0EY')
    time.sleep(2)

    etfs = session_v2.query(Etfs).all()
    target_start = pd.Timestamp.now().replace(day=1) - pd.DateOffset(months=TARGET_MONTHS)

    for etf in etfs:
        print(f"\n--- Processing {etf.ticker} ({etf.name}) ---")

        # Check if already fully populated
        existing = session_v2.query(HistoricalDataEtfs).filter_by(etf_id=etf.id).count()
        if existing >= TARGET_MONTHS:
            print(f"  Already have {existing} rows. Skipping.")
            continue

        # --- Step 1: Fetch real ETF prices ---
        real_data = fetch_yf_monthly(etf.yfinance_name)
        if len(real_data) < 12:
            av_data = fetch_av_monthly(etf.alphavantage_name)
            if len(av_data) > len(real_data):
                real_data = av_data
                real_source = 'alphavantage'
            else:
                real_source = 'yfinance'
        else:
            real_source = 'yfinance'

        if real_data.empty:
            print(f"  WARNING: No real data for {etf.ticker}. Skipping.")
            continue

        real_count = len(real_data)
        first_real_date = real_data.index[0]
        first_real_price = float(real_data.iloc[0])

        print(f"  Real data: {real_count} rows, first={first_real_date.date()}, price={first_real_price:.4f}")

        # --- Step 2: Build proxy series for the gap ---
        gap_needed = max(0, TARGET_MONTHS - real_count)
        proxy_series = pd.Series(dtype=float)
        proxy_source_label = 'extrapolated'

        if gap_needed > 0:
            cfg = PROXY_CONFIG.get(etf.ticker)
            if cfg:
                src = cfg['proxy_source']
                ticker_prx = cfg['proxy_ticker']
                print(f"  Gap: {gap_needed} months. Using proxy: {ticker_prx} ({src})")

                if src == 'yfinance':
                    raw_proxy = fetch_yf_monthly(ticker_prx)
                    if not raw_proxy.empty:
                        proxy_series = apply_proxy_returns_backwards(
                            raw_proxy, first_real_price, first_real_date)
                        proxy_source_label = 'index_proxy'

                elif src == 'stooq':
                    cache_key = f'stooq_{ticker_prx}'
                    raw_proxy = proxy_cache.get(cache_key)
                    if raw_proxy is None:
                        raw_proxy = fetch_stooq_monthly(ticker_prx)
                        proxy_cache[cache_key] = raw_proxy

                    if etf.ticker == 'SYBJ':
                        # FRED yield path — handled separately
                        pass
                    elif not raw_proxy.empty:
                        proxy_series = apply_proxy_returns_backwards(
                            raw_proxy, first_real_price, first_real_date)
                        proxy_source_label = 'index_proxy'

                elif src == 'fred':
                    fred_yields = proxy_cache.get('fred_hy', pd.Series(dtype=float))
                    if not fred_yields.empty:
                        # Convert yield series to synthetic prices anchored at first_real_price
                        proxy_series = fred_yields_to_synthetic_prices(
                            fred_yields, first_real_price, first_real_date)
                        # Only keep dates before first_real_date
                        proxy_series = proxy_series[proxy_series.index < first_real_date]
                        proxy_source_label = 'index_proxy'
            else:
                print(f"  No proxy config for {etf.ticker} — will extrapolate if needed")

        # --- Step 3: Fallback extrapolation for remaining gap ---
        if gap_needed > 0 and proxy_source_label == 'extrapolated':
            returns = real_data.pct_change().dropna()
            avg_ret = returns.mean()
            if pd.isna(avg_ret):
                avg_ret = 0.005
            n_extrap = gap_needed if proxy_series.empty else max(0, gap_needed - len(proxy_series))
            if n_extrap > 0 and proxy_series.empty:
                proxy_series = simple_extrapolate_backwards(
                    first_real_price, first_real_date, avg_ret, n_extrap)

        # --- Step 4: Write to DB ---
        # Delete existing rows for this ETF (idempotency)
        session_v2.execute(text('DELETE FROM historical_data_etfs WHERE etf_id = :id'),
                           {'id': etf.id})

        # Insert proxy/simulated rows first (older dates)
        sim_count = 0
        for dt, price in proxy_series.items():
            if pd.isna(price) or price <= 0:
                continue
            session_v2.add(HistoricalDataEtfs(
                date=dt.strftime('%Y-%m-%d'),
                etf_id=etf.id,
                price=float(price),
                is_simulated=True,
                source=proxy_source_label,
            ))
            sim_count += 1

        # Insert real rows
        real_inserted = 0
        for dt, price in real_data.items():
            if pd.isna(price) or price <= 0:
                continue
            session_v2.add(HistoricalDataEtfs(
                date=dt.strftime('%Y-%m-%d'),
                etf_id=etf.id,
                price=float(price),
                is_simulated=False,
                source=real_source,
            ))
            real_inserted += 1

        session_v2.commit()
        total = sim_count + real_inserted
        print(f"  Inserted: {real_inserted} real + {sim_count} proxy/simulated = {total} total rows")

        print(f"  Sleeping {SLEEP_BETWEEN_ETFS}s...")
        time.sleep(SLEEP_BETWEEN_ETFS)


# ===========================================================================
# Summary check
# ===========================================================================

def print_summary():
    print("\n=== SUMMARY ===")
    rows = session_v2.execute(text(
        "SELECT e.ticker, COUNT(*) as cnt, MIN(h.date), MAX(h.date), "
        "SUM(CASE WHEN h.is_simulated=1 THEN 1 ELSE 0 END) as sim, "
        "SUM(CASE WHEN h.source='index_proxy' THEN 1 ELSE 0 END) as proxy "
        "FROM historical_data_etfs h "
        "JOIN etfs e ON h.etf_id = e.id "
        "GROUP BY e.ticker ORDER BY e.id"
    )).fetchall()
    print(f"{'Ticker':<8} {'Rows':>5} {'Min Date':<12} {'Max Date':<12} {'Sim':>5} {'Proxy':>6}")
    print("-" * 55)
    for r in rows:
        print(f"{r[0]:<8} {r[1]:>5} {r[2]:<12} {r[3]:<12} {r[4]:>5} {r[5]:>6}")

    ir = session_v2.execute(text("SELECT COUNT(*) FROM inflation_rates")).scalar()
    print(f"\nInflationRates rows: {ir}")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == '__main__':
    copy_static_data()
    fetch_and_populate_prices()
    print_summary()
    print("\nDone! V2 database populated.")
    session_v1.close()
    session_v2.close()
