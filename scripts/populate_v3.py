import os
import sys
import logging
import datetime
import time
import sqlite3
import pandas as pd
import yfinance as yf
import httpx

# ── Path setup ──────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

from flask import Flask
from models_v2 import db, Etfs, HistoricalDataEtfs, Portfolios, PortfolioComposition

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# ── Configuration: 16 ETFs ───────────────────────────────────────────────────
ETF_CONFIG = [
    # All World
    {"ticker": "IUSQ", "name": "iShares MSCI ACWI UCITS ETF", "isin": "IE00B6R26155", "asset_type": "Stocks - All World", "currency": "EUR", "ext_ticker": "IUSQ.DE", "eodhd": "IUSQ.XETRA"},
    {"ticker": "VWCE", "name": "Vanguard FTSE All-World UCITS ETF", "isin": "IE00BK5BQT80", "asset_type": "Stocks - All World", "currency": "EUR", "ext_ticker": "VWCE.DE", "eodhd": "VWCE.XETRA"},
    {"ticker": "SPYY", "name": "SPDR MSCI ACWI UCITS ETF", "isin": "IE00B3YLMD38", "asset_type": "Stocks - All World", "currency": "EUR", "ext_ticker": "SPYY.DE", "eodhd": "SPYY.XETRA"},
    
    # S&P 500
    {"ticker": "SXR8", "name": "iShares Core S&P 500 UCITS ETF", "isin": "IE00B5BMR087", "asset_type": "Stocks - USA", "currency": "EUR", "ext_ticker": "SXR8.DE", "eodhd": "SXR8.XETRA"},
    {"ticker": "XDP6", "name": "Xtrackers S&P 500 Swap UCITS", "isin": "LU0490618542", "asset_type": "Stocks - USA", "currency": "EUR", "ext_ticker": "XDP6.DE", "eodhd": "XSPX.LSE"},
    {"ticker": "SPXP", "name": "Invesco S&P 500 UCITS ETF", "isin": "IE00B3YCGJ38", "asset_type": "Stocks - USA", "currency": "EUR", "ext_ticker": "SPXP.DE", "eodhd": "SPXP.LSE"},
    
    # Global Technology
    {"ticker": "SPFT", "name": "SPDR MSCI World Technology UCITS ETF", "isin": "IE00BYTRRD19", "asset_type": "Stocks - Tech", "currency": "EUR", "ext_ticker": "SPFT.DE", "eodhd": "SPFT.XETRA"},
    {"ticker": "XDWT", "name": "Xtrackers MSCI World IT UCITS", "isin": "IE00BM67HT60", "asset_type": "Stocks - Tech", "currency": "EUR", "ext_ticker": "XDWT.DE", "eodhd": "XDWT.XETRA"},
    {"ticker": "IITU", "name": "Amundi S&P Global IT ESG UCITS", "isin": "IE000E7EI9P0", "asset_type": "Stocks - Tech", "currency": "EUR", "ext_ticker": "IITU.DE", "eodhd": "WELU.XETRA"},
    
    # Global Bonds (EN version)
    {"ticker": "VGGF", "name": "Vanguard Global Govt Bond EUR Hedged", "isin": "IE00BGYWFF04", "asset_type": "Bonds - Global", "currency": "EUR", "ext_ticker": "VGGF.DE", "eodhd": "VGGF.XETRA"},
    {"ticker": "XG7S", "name": "Amundi Core Global Govt Bond EUR Hedged", "isin": "LU1708330235", "asset_type": "Bonds - Global", "currency": "EUR", "ext_ticker": "XG7S.DE", "eodhd": "GOVH.PA"},
    {"ticker": "DBXW", "name": "Xtrackers II Global Govt Bond EUR Hedged", "isin": "LU0378818131", "asset_type": "Bonds - Global", "currency": "EUR", "ext_ticker": "DBXW.DE", "eodhd": "DBZB.XETRA"},
    
    # Polish Bonds (PL version)
    {"ticker": "BETTBSP", "name": "Beta ETF TBSP", "isin": "PLBTBSP00012", "asset_type": "Bonds - Poland", "currency": "PLN", "ext_ticker": "BETTBSP.WA", "eodhd": None},
    
    # Gold
    {"ticker": "4GLD", "name": "Xetra Gold Acc", "isin": "DE000A0S9GB0", "asset_type": "Commodities - Gold", "currency": "EUR", "ext_ticker": "4GLD.DE", "eodhd": "4GLD.XETRA"},
    {"ticker": "PPFB", "name": "iShares Physical Gold ETC", "isin": "IE00B4ND3602", "asset_type": "Commodities - Gold", "currency": "EUR", "ext_ticker": "PPFB.DE", "eodhd": "SGLN.LSE"},
    {"ticker": "8PSG", "name": "Invesco Physical Gold A", "isin": "IE00B579F325", "asset_type": "Commodities - Gold", "currency": "EUR", "ext_ticker": "8PSG.DE", "eodhd": "SGLD.LSE"},
]

# ── Configuration: Portfolios ───────────────────────────────────────────────
PORTFOLIO_CONFIG = [
    {"name": "USA (S&P 500)", "slug": "sp500", "composition": {"SXR8": 33.333, "XDP6": 33.333, "SPXP": 33.334}},
    {"name": "GLOBAL TECHNOLOGY", "slug": "tech", "composition": {"SPFT": 33.333, "XDWT": 33.333, "IITU": 33.334}},
    {"name": "ALL WORLD", "slug": "allworld", "composition": {"IUSQ": 33.333, "VWCE": 33.333, "SPYY": 33.334}},
    
    {"name": "80-20 (Stocks-Bonds) EN", "slug": "80-20_EN", "composition": {
        "IUSQ": 26.666, "VWCE": 26.667, "SPYY": 26.667,
        "VGGF": 6.666, "XG7S": 6.667, "DBXW": 6.667
    }},
    {"name": "60-40 (Stocks-Bonds) EN", "slug": "60-40_EN", "composition": {
        "IUSQ": 20.0, "VWCE": 20.0, "SPYY": 20.0,
        "VGGF": 13.333, "XG7S": 13.333, "DBXW": 13.334
    }},
    
    {"name": "80-20 (Stocks-Bonds) PL", "slug": "80-20_PL", "composition": {
        "IUSQ": 26.666, "VWCE": 26.667, "SPYY": 26.667,
        "BETTBSP": 20.0
    }},
    {"name": "60-40 (Stocks-Bonds) PL", "slug": "60-40_PL", "composition": {
        "IUSQ": 20.0, "VWCE": 20.0, "SPYY": 20.0,
        "BETTBSP": 40.0
    }},
    
    {"name": "GOLD", "slug": "gold", "composition": {"4GLD": 33.333, "PPFB": 33.333, "8PSG": 33.334}},
]

# ── Flask app ────────────────────────────────────────────────────────────────
def create_app():
    app = Flask(__name__, instance_relative_config=True)
    db_path = os.path.join(_ROOT, 'instance', 'financial_data_v2.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

# ── Price Fetchers ───────────────────────────────────────────────────────────

def get_eodhd_data(ticker, from_date="1980-01-01"):
    """Fetch monthly closing prices from EODHD API."""
    key = os.getenv('DATA_PROVIDER_A_KEY')
    host = os.getenv('DATA_PROVIDER_A_HOST', 'https://eodhd.com/api')
    if not key or not ticker: return None
    
    url = f"{host}/eod/{ticker}?api_token={key}&fmt=json&from={from_date}&period=m"
    try:
        r = httpx.get(url, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if not data or not isinstance(data, list): return None
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            return df['adjusted_close']
    except Exception as e:
        log.warning("EODHD failed for %s: %s", ticker, e)
    return None

def get_stooq_data(ticker, period='m'):
    """Fetch data from Stooq with headers and content validation."""
    url = f"https://stooq.com/q/d/l/?s={ticker}&i={period}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = httpx.get(url, headers=headers, timeout=20)
        if r.status_code != 200: return None
        # Check if we got CSV or a "Rate Limit" HTML page
        if "<html" in r.text.lower() or "limit" in r.text.lower():
            log.warning("Stooq rate limit or HTML page received for %s", ticker)
            return None
            
        from io import StringIO
        df = pd.read_csv(StringIO(r.text))
        if df.empty or 'Date' not in df.columns: return None
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        return df['Close']
    except Exception as e:
        log.warning("Stooq parsing failed for %s: %s", ticker, e)
        return None

def get_yf_data(ticker):
    """Fetch monthly closing prices from Yahoo Finance with caching and retries."""
    cache_file = os.path.join(_ROOT, 'instance', f'cache_{ticker}.csv')
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return df['Close']
        
    log.info("Fetching %s from YFinance...", ticker)
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="max", interval="1mo")
        if df.empty: return None
        df.index = df.index.tz_localize(None).to_period('M').to_timestamp()
        # Save to cache
        df[['Close']].to_csv(cache_file)
        return df['Close']
    except Exception as e:
        log.warning("YF failed for %s: %s", ticker, e)
        return None

def get_fred_data(series_id):
    """Fetch series from FRED API."""
    key = os.getenv('ECONOMIC_DATA_PROVIDER_KEY')
    if not key: return None
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={key}&file_type=json"
    try:
        r = httpx.get(url, timeout=20)
        if r.status_code == 200:
            data = r.json()['observations']
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna().set_index('date')
            return df['value']
    except Exception as e:
        log.warning("FRED failed for %s: %s", series_id, e)
    return None

def get_eurusd_history():
    """Fetch historical EUR/USD exchange rate from FRED (DEXUSEU)."""
    return get_fred_data('DEXUSEU')

# ── Logic: TBSP Proxy (Poland Bonds) ────────────────────────────────────────

def get_tbsp_proxy():
    """
    Simulates TBSP Index history:
    - 2006-present: Real ^TBSP from Stooq.
    - Fallback: Simulate from GPW 10Y yields (FRED or Stooq).
    """
    log.info("Generating TBSP Index proxy...")
    real_tbsp = get_stooq_data("^TBSP")
    if real_tbsp is None: 
        real_tbsp = get_yf_data("^TBSP")
    
    # Fallback to FRED Long-term Govt Bond Yields for Poland
    yld_10y = get_stooq_data("10ypl.b")
    if yld_10y is None:
        log.info("Fetching Poland 10Y Yield from FRED...")
        yld_10y = get_fred_data("IRLTLT01PLM156N")

    if yld_10y is None:
        log.warning("No yield data for Poland. TBSP proxy failed.")
        return real_tbsp # Might be None

    yld_10y = yld_10y.sort_index()
    
    if real_tbsp is not None:
        real_tbsp = real_tbsp.sort_index()
        start_date = real_tbsp.index[0]
        start_price = real_tbsp.iloc[0]
        pre_tbsp_yields = yld_10y[yld_10y.index < start_date].sort_index(ascending=False)
    else:
        log.info("No real TBSP data. Simulating from earliest yield point.")
        # Start at 100.0 on the first yield date
        start_date = yld_10y.index[-1] # Newest
        start_price = 100.0
        pre_tbsp_yields = yld_10y.sort_index(ascending=False)

    sim_prices = {}
    curr_price = start_price
    curr_yield = yld_10y.asof(start_date) if start_date in yld_10y.index else yld_10y.iloc[0]
    duration = 4.5
    
    for date, yld in pre_tbsp_yields.items():
        delta_y = (curr_yield - yld) / 100.0
        price_ret = -duration * delta_y
        prev_price = curr_price / (1 + price_ret)
        sim_prices[date] = prev_price
        curr_price = prev_price
        curr_yield = yld
        
    sim_series = pd.Series(sim_prices).sort_index()
    if real_tbsp is not None:
        return pd.concat([sim_series, real_tbsp]).sort_index()
    return sim_series

def get_chained_stock_proxy():
    """Combines ACWI (2008+), SPY (1993+), and ^GSPC (pre-1993)."""
    # Prefer YFinance for these as it provides 30+ years
    acwi = get_yf_data("ACWI")
    spy = get_yf_data("SPY")
    spx = get_yf_data("^GSPC")
    
    if spx is None: spx = get_stooq_data("^SPX")
    if spx is None: spx = get_eodhd_data("GSPC.INDX") # Last resort
    
    if spx is None: return acwi if acwi is not None else spy
    
    full = spx / spx.iloc[-1]
    
    if spy is not None:
        idx = spy.index[0]
        if idx in full.index:
            ratio = spy.iloc[0] / full.asof(idx)
            full = pd.concat([full[full.index < idx] * ratio, spy]).sort_index()
        
    if acwi is not None:
        idx = acwi.index[0]
        if idx in full.index:
            ratio = acwi.iloc[0] / full.asof(idx)
            full = pd.concat([full[full.index < idx] * ratio, acwi]).sort_index()
        
    return full

def get_bond_proxy_en():
    """Global Govt Bond proxy using BND + VUSTX."""
    bnd = get_yf_data("BND") # Changed: YF has better history for US-listed
    vustx = get_yf_data("VUSTX")
    
    if vustx is None: return bnd
    if bnd is not None:
        idx = bnd.index[0]
        if idx in vustx.index:
            ratio = bnd.iloc[0] / vustx.asof(idx)
            return pd.concat([vustx[vustx.index < idx] * ratio, bnd]).sort_index()
    return vustx

# ── Main Population Routine ──────────────────────────────────────────────────

def run_population(session, force=False):
    # 0. Ensure cache dir exists
    cache_dir = os.path.join(_ROOT, 'instance')
    os.makedirs(cache_dir, exist_ok=True)

    if force:
        log.info("Force flag detected. Clearing database for full rebuild...")
        session.query(PortfolioComposition).delete()
        session.query(HistoricalDataEtfs).delete()
        session.query(Etfs).delete()
        session.query(Portfolios).delete()
        session.commit()
    
    # 2. Register ETFs (if not present)
    etf_map = {}
    for cfg in ETF_CONFIG:
        existing = session.query(Etfs).filter_by(ticker=cfg['ticker']).first()
        if not existing:
            e = Etfs(
                ticker=cfg['ticker'], name=cfg['name'], isin=cfg['isin'],
                asset_type=cfg['asset_type'], currency=cfg['currency'],
                external_ticker=cfg['ext_ticker']
            )
            session.add(e)
            session.commit()
            etf_map[cfg['ticker']] = e.id
        else:
            etf_map[cfg['ticker']] = existing.id

    # 3. Register Portfolios (if not present)
    port_map = {}
    for cfg in PORTFOLIO_CONFIG:
        existing_p = session.query(Portfolios).filter_by(name=cfg['name']).first()
        if not existing_p:
            p = Portfolios(name=cfg['name'], assets=len(cfg['composition']))
            session.add(p)
            session.commit()
            port_map[cfg['slug']] = p.id
            
            # Add Composition
            for t, pct in cfg['composition'].items():
                pc = PortfolioComposition(portfolio_id=p.id, etf_id=etf_map[t], percentage=pct/100.0)
                session.add(pc)
            session.commit()
        else:
            port_map[cfg['slug']] = existing_p.id

    # 4. Fetch and backfill Historical Data
    # USE YFINANCE FOR PROXIES - Higher history than restricted EODHD
    log.info("Fetching global proxies from YFinance...")
    sp500_proxy = get_yf_data("^GSPC")
    nasdaq_proxy = get_yf_data("^NDX")
    gold_proxy = get_yf_data("GC=F")
    
    time.sleep(10) # Heavy delay after proxies
    
    acwi_proxy = get_chained_stock_proxy()
    bond_proxy_en = get_bond_proxy_en()
    tbsp_proxy = get_tbsp_proxy()
            
    for cfg in ETF_CONFIG:
        ticker = cfg['ticker']
        ext = cfg['ext_ticker']
        etf_id = etf_map[ticker]
        
        # RESUME CHECK: Skip if already has history
        row_count = session.query(HistoricalDataEtfs).filter_by(etf_id=etf_id).count()
        if row_count > 10 and not force:
            log.info("Skipping %s: %d rows already present.", ticker, row_count)
            continue

        log.info("Processing %s (%s)...", ticker, ext)
        # 1. Try EODHD primarily for history
        prices = get_eodhd_data(cfg.get('eodhd'))
        source = 'eodhd'
        
        # 2. Fallbacks
        if prices is None:
            prices = get_yf_data(ext)
            source = 'yfinance'
        if prices is None:
            prices = get_stooq_data(ext)
            source = 'stooq'
            
        time.sleep(10) # High delay to avoid 429
        
        if prices is None or prices.empty:
            log.warning("No real data for %s", ticker)
            prices = pd.Series()
            
        # Backfill logic
        proxy = None
        if "Stocks - USA" in cfg['asset_type']: proxy = sp500_proxy
        elif "Tech" in cfg['asset_type']: proxy = nasdaq_proxy
        elif "Gold" in cfg['asset_type']: proxy = gold_proxy
        elif "All World" in cfg['asset_type']: proxy = acwi_proxy
        elif "Bonds - Global" in cfg['asset_type']: proxy = bond_proxy_en
        elif "Bonds - Poland" in cfg['asset_type']: proxy = tbsp_proxy
        
        # EUR/USD correction for gold proxy (GC=F is USD, ETFs are EUR)
        if "Gold" in cfg['asset_type'] and proxy is not None and not proxy.empty:
            eurusd = get_eurusd_history()
            if eurusd is not None and not eurusd.empty:
                anchor_date = prices.index[0] if not prices.empty else proxy.index[-1]
                eurusd_at_anchor = eurusd.asof(anchor_date)
                if pd.notna(eurusd_at_anchor) and eurusd_at_anchor > 0:
                    eurusd_aligned = eurusd.reindex(proxy.index).ffill().bfill()
                    proxy = proxy / eurusd_aligned * eurusd_at_anchor
                    log.info("Applied EUR/USD correction to gold proxy (anchor: %s, rate: %.4f)", anchor_date.date(), eurusd_at_anchor)
        
        if proxy is not None and not proxy.empty:
            # Shift proxy to match first price of ETF
            if not prices.empty:
                # Ensure date alignment
                prices.index = pd.to_datetime(prices.index)
                proxy.index = pd.to_datetime(proxy.index)
                
                first_date = prices.index[0]
                first_price = prices.iloc[0]
                
                # Robust match for proxy value at ETF launch
                try:
                    proxy_val_at_start = proxy.asof(first_date)
                    if pd.isna(proxy_val_at_start):
                        proxy_val_at_start = proxy.iloc[0]
                except:
                    proxy_val_at_start = proxy.iloc[0]
                
                # Simple ratio backfill
                ratio = first_price / proxy_val_at_start
                proxy_shifted = proxy[proxy.index < first_date] * ratio
                
                # Insert proxy rows
                for d, p in proxy_shifted.items():
                    session.add(HistoricalDataEtfs(
                        date=d.strftime('%Y-%m-%d'), etf_id=etf_id, price=float(p),
                        is_simulated=True, source='index_proxy'
                    ))
            else:
                # No ETF data at all - use proxy directly (normalized)
                # Ensure some baseline price (e.g. 100.0)
                norm = 100.0 / proxy.iloc[0] if proxy.iloc[0] != 0 else 1.0
                for d, p in proxy.items():
                    session.add(HistoricalDataEtfs(
                        date=d.strftime('%Y-%m-%d'), etf_id=etf_id, price=float(p) * norm,
                        is_simulated=True, source='index_proxy'
                    ))

        # Insert real rows
        for d, p in prices.items():
            session.add(HistoricalDataEtfs(
                date=d.strftime('%Y-%m-%d'), etf_id=etf_id, price=float(p),
                is_simulated=False, source=source
            ))
        
        session.commit()
    
    log.info("Population V3 complete.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help="Clear database and refetch all data")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        run_population(db.session, force=args.force)
