import os
import httpx
import logging
from datetime import datetime
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.base import STATE_RUNNING
from dotenv import load_dotenv

# Internal imports
from models_v2 import db, Portfolios
import helpers_v2 as helpers
from scripts.sync_macro import run_sync as run_macro_sync

# ── Setup & Configuration ───────────────────────────────────────────────────
load_dotenv(override=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://zenetfs.com"


# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ── Flask App & DB Configuration ───────────────────────────────────────────
# We use a Flask instance purely for Flask-SQLAlchemy compatibility 
# with the existing models and database migration state.
def create_flask_app():
    f_app = Flask(__name__, instance_relative_config=True)
    f_app.debug = False
    
    # DB path relative to script location
    db_path = os.path.join(BASE_DIR, 'instance', 'financial_data_v2.db')
    f_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    f_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(f_app)
    
    with f_app.app_context():
        db.create_all()
    
    return f_app

flask_app = create_flask_app()

# ── Scheduler Configuration ────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone='Europe/Berlin')

def update_job():
    """Periodic task to refresh ETF data."""
    with flask_app.app_context():
        try:
            logging.info("Starting background update job...")
            etfs_prices = helpers.get_etfs_data(db.session)
            helpers.append_etfs_prices(etfs_prices, db.session)
            
            # Additional calculations can be re-enabled here if needed:
            # helpers.get_etfs_yields(db.session)
            # helpers.get_portfolio_returns(db.session)
            # helpers.get_portfolios_results(db.session)
            
            success_msg = "✅ ZenETFs: Miesięczna aktualizacja danych zakończona sukcesem! Wszystkie ETF-y mają świeże ceny."
            helpers.notify_success(success_msg)
            logging.info("Background update job completed successfully.")
        except Exception as e:
            db.session.rollback()
            logging.error('An error occurred in update_job(): %s', e, exc_info=True)
            helpers.update_error_email(e)

def sync_macro_job():
    """Sync macroeconomic data (CPI inflation + EUR/currency FX rates) from FRED."""
    with flask_app.app_context():
        session = db.session()
        try:
            logging.info("Starting background macro sync job...")
            run_macro_sync(session)
            logging.info("Background macro sync job completed.")
        except Exception as e:
            session.rollback()
            logging.error('An error occurred in sync_macro_job(): %s', e, exc_info=True)
        finally:
            session.close()

def start_scheduler():
    if not scheduler.running:
        # Run on the 10th of every month at 04:00 AM
        scheduler.add_job(
            func=update_job, 
            trigger=CronTrigger(day='10', hour='4'), 
            misfire_grace_time=3600
        )
        # Macro data sync: 10th of every month at 05:00 AM (1h after ETF job)
        scheduler.add_job(
            func=sync_macro_job, 
            trigger=CronTrigger(day='10', hour='5'), 
            misfire_grace_time=3600
        )
        scheduler.start()
        logging.info("Scheduler started.")

# ── FastAPI App Setup ──────────────────────────────────────────────────────
app = FastAPI(title="ZenETFs API")

# Mount static files
static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup Jinja2 templates
templates_dir = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=templates_dir)

# ── FastAPI Lifecycle ──────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    # Verify DB connectivity
    with flask_app.app_context():
        db.engine.connect()
        logging.info("Database connected successfully using Flask context.")
    
    # Start scheduler
    # In multi-worker prod environments, ensure this only runs once or use a separate worker.
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler.state == STATE_RUNNING:
        scheduler.shutdown()
        logging.info("Scheduler shut down.")


# ── Language Detection: Triple Check ─────────────────────────────────────────

async def detect_language(request: Request) -> str:
    """
    Determines the preferred language using a three-step cascade:
    1. Cookie `lang`          — user's explicit past choice
    2. Accept-Language header — browser preference
    3. IP geolocation         — fallback via ip-api.com
    """
    lang_cookie = request.cookies.get("lang")
    if lang_cookie in ("pl", "en"):
        return lang_cookie

    accept_lang = request.headers.get("Accept-Language", "")
    if accept_lang:
        primary = accept_lang.split(",")[0].split(";")[0].strip().lower()
        if primary.startswith("pl"):
            return "pl"
        if primary and not primary.startswith("*"):
            return "en"

    try:
        client_ip = request.client.host
        if not client_ip or client_ip in ("127.0.0.1", "::1"):
            return "en"
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{client_ip}?fields=countryCode")
            if resp.status_code == 200:
                country = resp.json().get("countryCode", "").upper()
                if country == "PL":
                    return "pl"
    except Exception:
        pass

    return "en"

@app.middleware("http")
async def trailing_slash_redirect(request: Request, call_next):
    """Redirect /en or /pl to /en/ or /pl/ (add trailing slash for lang roots)."""
    path = request.url.path
    if path in ("/pl", "/en"):
        new_url = f"{path}/"
        if request.url.query:
            new_url += f"?{request.url.query}"
        return RedirectResponse(url=new_url, status_code=301)
    response = await call_next(request)
    return response


@app.middleware("http")
async def https_www_redirect(request: Request, call_next):
    """Redirect www to non-www. HTTPS is handled by Nginx Proxy Manager."""
    host = request.headers.get("host", "")

    if host.startswith("www."):
        new_host = host[4:]
        proto = request.headers.get("X-Forwarded-Proto", "https")
        new_url = f"{proto}://{new_host}{request.url.path}"
        if request.url.query:
            new_url += f"?{request.url.query}"
        return RedirectResponse(url=new_url, status_code=301)

    response = await call_next(request)
    return response

@app.middleware("http")
async def language_cookie_middleware(request: Request, call_next):
    path = request.url.path
    lang_from_path = None
    if path.startswith("/pl"):
        lang_from_path = "pl"
    elif path.startswith("/en"):
        lang_from_path = "en"

    response = await call_next(request)

    if lang_from_path:
        set_lang_cookie(response, lang_from_path)
    
    return response

def set_lang_cookie(response: Response, lang: str) -> None:
    response.set_cookie(
        "lang", 
        lang, 
        max_age=60 * 60 * 24 * 365, 
        path="/", 
        samesite="lax"
    )

# ── Business Logic Helpers ──────────────────────────────────────────────────

def get_portfolio_data(currency: str = 'EUR', lang: str = 'en') -> list:
    """Return nominal CAGR portfolio data in the requested currency, filtered by language."""
    with flask_app.app_context():
        session = db.session()
        try:
            # Fetch all and filter in Python to ensure zipping remains aligned with helpers output
            all_ports = session.query(Portfolios).order_by(Portfolios.id).all()
            all_returns = helpers.get_portfolio_returns_in_currency(session, currency)
            
            result = []
            for portfolio, returns in zip(all_ports, all_returns):
                # Filter logic: hide EN portfolios on PL page and vice versa
                if lang == 'pl' and portfolio.name.endswith(' EN'):
                    continue
                if lang == 'en' and portfolio.name.endswith(' PL'):
                    continue
                
                result.append({
                    "name": portfolio.name,
                    "assets": int(portfolio.assets),
                    "return5":  float(round(returns[0], 2)),
                    "return10": float(round(returns[1], 2)),
                    "return20": float(round(returns[2], 2)),
                    "return30": float(round(returns[3], 2)),
                })
            return result
        finally:
            session.close()


def get_real_portfolio_data(currency: str = 'EUR', lang: str = 'en') -> list:
    """Return inflation-adjusted (real) CAGR portfolio data in the requested currency, filtered by language."""
    with flask_app.app_context():
        session = db.session()
        try:
            all_ports = session.query(Portfolios).order_by(Portfolios.id).all()
            all_returns = helpers.get_real_portfolio_returns(session, currency)
            
            result = []
            for portfolio, returns in zip(all_ports, all_returns):
                if lang == 'pl' and portfolio.name.endswith(' EN'):
                    continue
                if lang == 'en' and portfolio.name.endswith(' PL'):
                    continue
                    
                result.append({
                    "name": portfolio.name,
                    "assets": int(portfolio.assets),
                    "return5":  float(round(returns[0], 2)),
                    "return10": float(round(returns[1], 2)),
                    "return20": float(round(returns[2], 2)),
                    "return30": float(round(returns[3], 2)),
                })
            return result
        finally:
            session.close()

def ctx(request: Request, lang: str, active_page: str, **extra) -> dict:
    canonical_url = f"{BASE_URL}{request.url.path}"
    return {
        "request": request, 
        "lang": lang, 
        "active_page": active_page, 
        "canonical_url": canonical_url,
        **extra
    }

# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=RedirectResponse)
async def root(request: Request):
    # www redirect is handled by https_www_redirect middleware
    lang = await detect_language(request)
    response = RedirectResponse(url=f"/{lang}/", status_code=301)
    set_lang_cookie(response, lang)
    return response

# Polish routes
@app.get("/pl/", response_class=HTMLResponse)
async def pl_index(request: Request):
    return templates.TemplateResponse(request, "pl/index.html", ctx(request, "pl", "index"))

@app.get("/pl/portfolios", response_class=HTMLResponse)
async def pl_portfolios(request: Request):
    return templates.TemplateResponse(request, "pl/portfolios.html", ctx(request, "pl", "portfolios"))

@app.get("/pl/etfs", response_class=HTMLResponse)
async def pl_etfs(request: Request):
    return templates.TemplateResponse(request, "pl/etfs.html", ctx(request, "pl", "etfs"))

@app.get("/pl/about", response_class=HTMLResponse)
async def pl_about(request: Request):
    return templates.TemplateResponse(request, "pl/about.html", ctx(request, "pl", "about"))

# English routes
@app.get("/en/", response_class=HTMLResponse)
async def en_index(request: Request):
    return templates.TemplateResponse(request, "en/index.html", ctx(request, "en", "index"))

@app.get("/en/portfolios", response_class=HTMLResponse)
async def en_portfolios(request: Request):
    return templates.TemplateResponse(request, "en/portfolios.html", ctx(request, "en", "portfolios"))

@app.get("/en/etfs", response_class=HTMLResponse)
async def en_etfs(request: Request):
    return templates.TemplateResponse(request, "en/etfs.html", ctx(request, "en", "etfs"))

@app.get("/en/about", response_class=HTMLResponse)
async def en_about(request: Request):
    return templates.TemplateResponse(request, "en/about.html", ctx(request, "en", "about"))

@app.get("/api/data")
def get_data(inflation: bool = False, currency: str = "EUR", lang: str = "en"):
    """
    Return portfolio CAGR data as JSON.

    Query parameters:
      currency  : 'EUR' (default) or 'PLN'
      inflation : false (default) — nominal CAGR
                  true            — real CAGR
      lang      : 'pl' or 'en'    — filters portfolios by language
    """
    currency = currency.upper()
    if currency not in ('EUR', 'PLN'):
        currency = 'EUR'
    if inflation:
        return get_real_portfolio_data(currency, lang)
    return get_portfolio_data(currency, lang)

# SEO files
@app.get("/robots.txt", response_class=Response)
async def robots_txt():
    content = "User-agent: *\nAllow: /\nSitemap: https://zenetfs.com/sitemap.xml\n"
    return Response(content=content, media_type="text/plain")

@app.get("/sitemap.xml", response_class=Response)
async def sitemap():
    pages = ["", "portfolios", "etfs", "about"]
    date_now = datetime.utcnow().strftime("%Y-%m-%d")

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">')

    for page in pages:
        # Root paths need trailing slash, subpages don't (matching route definitions)
        path = f"/{page}" if page else "/"
        pl_url = f"{BASE_URL}/pl{path}"
        en_url = f"{BASE_URL}/en{path}"
        
        # PL entry
        xml.append('  <url>')
        xml.append(f'    <loc>{pl_url}</loc>')
        xml.append(f'    <lastmod>{date_now}</lastmod>')
        xml.append('    <changefreq>weekly</changefreq>')
        xml.append(f'    <xhtml:link rel="alternate" hreflang="pl" href="{pl_url}"/>')
        xml.append(f'    <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>')
        xml.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{en_url}"/>')
        xml.append('  </url>')
        
        # EN entry
        xml.append('  <url>')
        xml.append(f'    <loc>{en_url}</loc>')
        xml.append(f'    <lastmod>{date_now}</lastmod>')
        xml.append('    <changefreq>weekly</changefreq>')
        xml.append(f'    <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>')
        xml.append(f'    <xhtml:link rel="alternate" hreflang="pl" href="{pl_url}"/>')
        xml.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{en_url}"/>')
        xml.append('  </url>')

    xml.append('</urlset>')
    return Response(content="\n".join(xml), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
