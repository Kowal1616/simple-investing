"""
scripts/sync_macro.py
=====================
Monthly synchronisation of macroeconomic data from the FRED API.

Responsibilities:
  1. On first run: migrate legacy data from InflationRates → AnnualMacroData.
  2. Fetch missing annual CPI and EUR/currency exchange rate data from FRED.
  3. Re-compute MacroAveragesCache after any successful update.
  4. Send a 🔥 notification via SystemNotifier only when NEW data is inserted.
  5. Exit silently (no error) when FRED does not yet have data for the previous year.

FRED series used (Annual frequency straight from FRED):
  - FPCPITOTLZGEMU   : Inflation, consumer prices for the Euro Area (Annual %)
  - FPCPITOTLZGPOL   : Inflation, consumer prices for Poland (Annual %)
  - CCUSMA02EZA618N  : Currency Conversions: EUR per USD (Annual average)
  - CCUSMA02PLA618N  : Currency Conversions: PLN per USD (Annual average)

EUR/PLN cross-rate:  EUR/PLN = (PLN per USD) / (EUR per USD)

This OECD series (CCUSMA...) automatically handles ECU pre-1999 history for the Euro Area.
"""

import os
import sys
import logging
import datetime

import httpx

# ── Path setup so we can import project modules when run standalone ──────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

from flask import Flask
from models_v2 import db, AnnualMacroData, MacroAveragesCache, InflationRates
from notifications import SystemNotifier

# ── Logging ──────────────────────────────────────────────────────────────────
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_KEY  = os.getenv("ECONOMIC_DATA_PROVIDER_KEY", "")

CURRENCIES = ['EUR', 'PLN']
PERIODS    = [5, 10, 20, 30]

# FRED series IDs (Annual data)
SERIES = {
    'cpi_eur': 'FPCPITOTLZGEMU',
    'cpi_pln': 'FPCPITOTLZGPOL',
    'fx_eur_usd': 'CCUSMA02EZA618N',  # EUR per 1 USD (OECD)
    'fx_pln_usd': 'CCUSMA02PLA618N',  # PLN per 1 USD (OECD)
}


# ── Flask app for DB access ───────────────────────────────────────────────────
def _create_flask_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    db_path = os.path.join(_ROOT, 'instance', 'financial_data_v2.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app


# ── FRED helpers ──────────────────────────────────────────────────────────────

def _fred_get(series_id: str, observation_start: str, observation_end: str,
              frequency: str | None = None) -> list[dict]:
    """
    Fetch observations from FRED.
    Returns list of {'date': 'YYYY-MM-DD', 'value': '3.14'} dicts.
    Filters out missing values ('.' in FRED).
    """
    params = {
        'series_id': series_id,
        'api_key': FRED_KEY,
        'file_type': 'json',
        'observation_start': observation_start,
        'observation_end': observation_end,
    }
    if frequency:
        params['frequency'] = frequency

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(FRED_BASE, params=params)
            resp.raise_for_status()
        observations = resp.json().get('observations', [])
        return [o for o in observations if o.get('value', '.') != '.']
    except Exception as exc:
        log.warning("FRED request failed for %s: %s", series_id, exc)
        return []


def _fetch_annual_point(series_id: str, target_year: int) -> float | None:
    """
    Fetch a single annual data point for the specified year.
    We look for dates starting with 'YYYY'.
    """
    obs = _fred_get(
        series_id,
        observation_start=f"{target_year}-01-01",
        observation_end=f"{target_year}-12-31",
    )
    for o in obs:
        if o['date'].startswith(str(target_year)):
            try:
                return float(o['value'])
            except ValueError:
                pass
    
    log.info("%s: no valid data for %d.", series_id, target_year)
    return None


# ── Migration: InflationRates → AnnualMacroData ───────────────────────────────

def migrate_legacy_inflation(session) -> int:
    """
    Copy EUR and PLN rows from the legacy InflationRates table to AnnualMacroData.
    Only currencies 'EUR' and 'PLN' are migrated; USD is ignored.
    eur_rate is left None for all migrated rows — backfilled later via FRED.
    Returns number of rows inserted.
    """
    # Check if table exists (avoids error if it was never created)
    try:
        rows = (session.query(InflationRates)
                .filter(InflationRates.currency_code.in_(['EUR', 'PLN']))
                .order_by(InflationRates.year)
                .all())
    except Exception:
        return 0

    inserted = 0
    for row in rows:
        exists = (session.query(AnnualMacroData)
                  .filter_by(year=row.year, currency_code=row.currency_code)
                  .first())
        if exists:
            continue
        session.add(AnnualMacroData(
            year=row.year,
            currency_code=row.currency_code,
            annual_inflation_pct=row.rate,
            eur_rate=None,  # backfilled in _backfill_missing_eur_rates()
        ))
        inserted += 1

    if inserted:
        session.commit()
        log.info("Legacy migration: inserted %d rows into annual_macro_data.", inserted)

    return inserted


def _backfill_missing_eur_rates(session, currency: str) -> None:
    """
    For rows in annual_macro_data where eur_rate IS NULL, attempt to fetch
    the annual average EUR/currency rate from FRED and update the row.
    Only meaningful for PLN (EUR has no rate — always 1.0).
    """
    if currency == 'EUR':
        return

    rows_missing = (session.query(AnnualMacroData)
                    .filter_by(currency_code=currency)
                    .filter(AnnualMacroData.eur_rate.is_(None))
                    .order_by(AnnualMacroData.year)
                    .all())

    if not rows_missing:
        return

    log.info("Backfilling EUR/%s rates for %d years...", currency, len(rows_missing))

    for row in rows_missing:
        eur_usd_val = _fetch_annual_point(SERIES['fx_eur_usd'], row.year)
        pln_usd_val = _fetch_annual_point(SERIES['fx_pln_usd'], row.year)

        if eur_usd_val is None or pln_usd_val is None:
            log.warning("Could not fetch FX data for %d (EUR_USD: %s, PLN_USD: %s).", 
                        row.year, eur_usd_val, pln_usd_val)
            continue

        # Cross-rate: EUR/PLN = (PLN per USD) / (EUR per USD)
        # We want PLN per 1 EUR.
        eur_pln = round(pln_usd_val / eur_usd_val, 6)
        row.eur_rate = eur_pln
        log.info("  %d: EUR/PLN = %.4f", row.year, eur_pln)

    session.commit()


# ── Fetch new year's data ─────────────────────────────────────────────────────

def fetch_and_insert_year(session, target_year: int) -> bool:
    """
    Fetch CPI and FX data for target_year from FRED and insert into annual_macro_data.
    Returns True if ANY new data was inserted, False otherwise.
    """
    inserted_any = False

    # ── EUR ──────────────────────────────────────────────────────────────────
    eur_exists = session.query(AnnualMacroData).filter_by(
        year=target_year, currency_code='EUR').first()

    if not eur_exists:
        eur_cpi = _fetch_annual_point(SERIES['cpi_eur'], target_year)
        if eur_cpi is not None:
            session.add(AnnualMacroData(
                year=target_year,
                currency_code='EUR',
                annual_inflation_pct=round(eur_cpi, 4),
                eur_rate=None,
            ))
            session.commit()
            log.info("Inserted EUR CPI for %d: %.2f%%", target_year, eur_cpi)
            inserted_any = True
        else:
            log.info("FRED: no CPI data for EUR %d yet.", target_year)

    # ── PLN ──────────────────────────────────────────────────────────────────
    pln_exists = session.query(AnnualMacroData).filter_by(
        year=target_year, currency_code='PLN').first()

    if not pln_exists:
        pln_cpi = _fetch_annual_point(SERIES['cpi_pln'], target_year)
        eur_usd_val = _fetch_annual_point(SERIES['fx_eur_usd'], target_year)
        pln_usd_val = _fetch_annual_point(SERIES['fx_pln_usd'], target_year)

        if pln_cpi is not None and eur_usd_val is not None and pln_usd_val is not None:
            eur_pln = round(pln_usd_val / eur_usd_val, 6)
            session.add(AnnualMacroData(
                year=target_year,
                currency_code='PLN',
                annual_inflation_pct=round(pln_cpi, 4),
                eur_rate=eur_pln,
            ))
            session.commit()
            log.info("Inserted PLN data for %d: CPI=%.2f%%, EUR/PLN=%.4f",
                     target_year, pln_cpi, eur_pln)
            inserted_any = True
        else:
            log.info("FRED: incomplete PLN data for %d yet. (CPI:%s, EUR_USD:%s, PLN_USD:%s)", 
                     target_year, pln_cpi, eur_usd_val, pln_usd_val)

    return inserted_any


# ── Cache pre-computation ─────────────────────────────────────────────────────

def _annualized_rate_change(rates: list[float]) -> float:
    """
    Given a list of EUR/currency rates ordered oldest→newest,
    return the annualized compound rate change (as %).
    """
    n = len(rates) - 1  # number of steps
    if n <= 0 or rates[0] == 0:
        return 0.0
    return round(((rates[-1] / rates[0]) ** (1 / n) - 1) * 100, 4)


def recompute_cache(session) -> None:
    """
    Recompute MacroAveragesCache for all (currency, period) combinations.
    Uses the most recent N complete years of data available in annual_macro_data.
    """
    now_str = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    for currency in CURRENCIES:
        rows = (session.query(AnnualMacroData)
                .filter_by(currency_code=currency)
                .order_by(AnnualMacroData.year)
                .all())

        if not rows:
            log.warning("No data in annual_macro_data for %s — skipping cache.", currency)
            continue

        for period in PERIODS:
            available = len(rows)
            used = min(period, available)
            subset = rows[-used:]  # most recent `used` years

            avg_inflation = round(sum(r.annual_inflation_pct for r in subset) / used, 4)

            # Exchange rate change
            avg_rate_change = None
            if currency != 'EUR':
                rates = [r.eur_rate for r in subset if r.eur_rate is not None]
                if len(rates) >= 2:
                    avg_rate_change = _annualized_rate_change(rates)
                else:
                    avg_rate_change = 0.0

            note = now_str
            if used < period:
                note = f"{now_str} (only {used} years available, requested {period})"

            # Upsert cache row
            cache_row = (session.query(MacroAveragesCache)
                         .filter_by(currency_code=currency, period_years=period)
                         .first())

            if cache_row:
                cache_row.avg_inflation_pct       = avg_inflation
                cache_row.avg_eur_rate_change_pct = avg_rate_change
                cache_row.updated_at              = note
            else:
                session.add(MacroAveragesCache(
                    currency_code=currency,
                    period_years=period,
                    avg_inflation_pct=avg_inflation,
                    avg_eur_rate_change_pct=avg_rate_change,
                    updated_at=note,
                ))

        session.commit()
    log.info("Cache recomputed for all currencies.")


# ── Main entry point ──────────────────────────────────────────────────────────

def run_sync(session) -> None:
    """
    Full synchronisation routine.
    """
    # Step 1: Migrate legacy InflationRates data on first run
    legacy_inserted = migrate_legacy_inflation(session)
    _backfill_missing_eur_rates(session, 'PLN')

    # Step 2: Determine recent years to try extending
    current_year = datetime.date.today().year
    
    # We check the last many years to fill any gaps (back to 1985 for initial sync)
    new_data = False
    for y in range(current_year - 40, current_year):
        if fetch_and_insert_year(session, y):
            new_data = True

    # Step 3: Recompute cache
    recompute_cache(session)

    # Step 4: Notify on new data insertion
    if new_data:
        try:
            notifier = SystemNotifier()
            notifier.send_error_alert(
                f"🔥 ZenETFs: Dane makroekonomiczne zaktualizowane! "
                f"Pobrano nowe dane inflacyjne/kursowe z FRED."
            )
        except Exception as exc:
            log.warning("Notification failed: %s", exc)
        log.info("Macro data sync completed with new data.")
    else:
        log.info("Macro data sync completed (no new yearly data added).")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    flask_app = _create_flask_app()
    with flask_app.app_context():
        session = db.session()
        try:
            run_sync(session)
        except Exception as exc:
            session.rollback()
            log.error("sync_macro failed: %s", exc, exc_info=True)
            raise
        finally:
            session.close()
