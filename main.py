import os
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import existing logic to reuse Flask-SQLAlchemy alongside FastAPI
from app import app as flask_app
from models_v2 import db, Portfolios
import helpers_v2 as helpers

app = FastAPI()

# Setup absolute path references for prod reliability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount static files if the directory exists
static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup Jinja2 templates
templates_dir = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=templates_dir)


# ── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    with flask_app.app_context():
        db.engine.connect()
        print("Database connected successfully using Flask context.")


# ── Language Detection: Triple Check ─────────────────────────────────────────

async def detect_language(request: Request) -> str:
    """
    Determines the preferred language using a three-step cascade:
    1. Cookie `lang`          — user's explicit past choice (fastest)
    2. Accept-Language header — browser preference (free, accurate)
    3. IP geolocation         — fallback via ip-api.com (only when needed)
    Returns 'pl' or 'en'.
    """
    # 1. Cookie takes highest priority
    lang_cookie = request.cookies.get("lang")
    if lang_cookie in ("pl", "en"):
        return lang_cookie

    # 2. Accept-Language header
    accept_lang = request.headers.get("Accept-Language", "")
    if accept_lang:
        primary = accept_lang.split(",")[0].split(";")[0].strip().lower()
        if primary.startswith("pl"):
            return "pl"
        # Any non-Polish explicit preference → English
        if primary and not primary.startswith("*"):
            return "en"

    # 3. IP geolocation fallback
    try:
        client_ip = request.client.host
        # Skip geolocation for local/private IPs
        if not client_ip or client_ip in ("127.0.0.1", "::1"):
            return "en"
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{client_ip}?fields=countryCode")
            if resp.status_code == 200:
                country = resp.json().get("countryCode", "").upper()
                if country == "PL":
                    return "pl"
    except Exception:
        pass  # Silently fall back to English

    return "en"


@app.middleware("http")
async def language_cookie_middleware(request: Request, call_next):
    """
    Global middleware to ensure the 'lang' cookie is set immediately 
    when the user navigates to a language-specific route (/pl/ or /en/).
    """
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
    # Always set path="/" so the cookie is available across the whole site
    response.set_cookie(
        "lang", 
        lang, 
        max_age=60 * 60 * 24 * 365, 
        path="/", 
        samesite="lax"
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_portfolio_data() -> list:
    with flask_app.app_context():
        session = db.session()
        try:
            portfolios_list = session.query(Portfolios).all()
            all_returns = helpers.get_portfolio_returns(session)
            return [
                {
                    "name": portfolio.name,
                    "assets": int(portfolio.assets),
                    "return5": float(round(returns[0], 2)),
                    "return10": float(round(returns[1], 2)),
                    "return20": float(round(returns[2], 2)),
                    "return30": float(round(returns[3], 2)),
                }
                for portfolio, returns in zip(portfolios_list, all_returns)
            ]
        finally:
            session.close()


def ctx(request: Request, lang: str, active_page: str, **extra) -> dict:
    """Build a common template context dict."""
    return {"request": request, "lang": lang, "active_page": active_page, **extra}


# ── Root redirect ─────────────────────────────────────────────────────────────

@app.get("/", response_class=RedirectResponse)
async def root(request: Request):
    lang = await detect_language(request)
    response = RedirectResponse(url=f"/{lang}/", status_code=302)
    set_lang_cookie(response, lang)
    return response


# ── Polish routes (/pl/) ──────────────────────────────────────────────────────

@app.get("/pl/", response_class=HTMLResponse)
async def pl_index(request: Request):
    return templates.TemplateResponse(
        request, "pl/index.html", ctx(request, "pl", "index")
    )


@app.get("/pl/portfolios", response_class=HTMLResponse)
async def pl_portfolios(request: Request):
    return templates.TemplateResponse(
        request, "pl/portfolios.html", ctx(request, "pl", "portfolios")
    )


@app.get("/pl/etfs", response_class=HTMLResponse)
async def pl_etfs(request: Request):
    return templates.TemplateResponse(
        request, "pl/etfs.html", ctx(request, "pl", "etfs")
    )


@app.get("/pl/about", response_class=HTMLResponse)
async def pl_about(request: Request):
    return templates.TemplateResponse(
        request, "pl/about.html", ctx(request, "pl", "about")
    )


# ── English routes (/en/) ─────────────────────────────────────────────────────

@app.get("/en/", response_class=HTMLResponse)
async def en_index(request: Request):
    return templates.TemplateResponse(
        request, "en/index.html", ctx(request, "en", "index")
    )


@app.get("/en/portfolios", response_class=HTMLResponse)
async def en_portfolios(request: Request):
    return templates.TemplateResponse(
        request, "en/portfolios.html", ctx(request, "en", "portfolios")
    )


@app.get("/en/etfs", response_class=HTMLResponse)
async def en_etfs(request: Request):
    return templates.TemplateResponse(
        request, "en/etfs.html", ctx(request, "en", "etfs")
    )


@app.get("/en/about", response_class=HTMLResponse)
async def en_about(request: Request):
    return templates.TemplateResponse(
        request, "en/about.html", ctx(request, "en", "about")
    )


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/data")
def get_data():
    """Return portfolio data as JSON for the comparison table."""
    return get_portfolio_data()
