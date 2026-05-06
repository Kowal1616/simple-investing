# SEO Optimization Plan — ZenETFs

## Overview
Add Open Graph tags and improve title/meta description tags across all pages (PL + EN).

---

## 1. `templates/layout.html` — Open Graph + Title Fix

### Current (lines 7-11):
```html
<meta name="description"
  content="{% block meta_description %}...{% endblock %}">
<meta name="keywords" content="ETF, UCITS, investing, portfolio, CAGR, comparison, European, passive investing">
<meta name="robots" content="index, follow">
<title>ZenETFs — {% block title %}{% endblock %}</title>
```

### Replace with:
```html
<meta name="description"
  content="{% block meta_description %}ZenETFs — Long-term ETF portfolio comparison tool for European investors. CAGR data for 5, 10, 20 and 30 years.{% endblock %}">
<meta name="keywords" content="ETF, UCITS, investing, portfolio, CAGR, comparison, European, passive investing, bogleheads">
<meta name="robots" content="index, follow">
<title>{% block title_full %}ZenETFs — {% block title %}{% endblock %}{% endblock %}</title>

<!-- Open Graph + Twitter Card -->
<meta property="og:title" content="{% block og_title %}{% endblock %}">
<meta property="og:description" content="{% block og_description %}{% endblock %}">
<meta property="og:image" content="{{ BASE_URL }}/static/og-image.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="{{ canonical_url }}">
<meta property="og:type" content="website">
<meta property="og:locale" content="{{ 'pl_PL' if lang == 'pl' else 'en_US' }}">
<meta property="og:site_name" content="ZenETFs">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
```

**Note:** Canonical `<link rel="canonical" href="{{ canonical_url }}">` is already present on line 12 — no change needed.

### Also needed: Pass `BASE_URL` to template context in `main.py`

In the `ctx()` function (line 299-307), add `"BASE_URL": BASE_URL`:

```python
def ctx(request: Request, lang: str, active_page: str, **extra) -> dict:
    canonical_url = f"{BASE_URL}{request.url.path}"
    return {
        "request": request,
        "lang": lang,
        "active_page": active_page,
        "canonical_url": canonical_url,
        "BASE_URL": BASE_URL,
        **extra
    }
```

---

## 2. `templates/en/index.html`

### Replace blocks (lines 3-5):
```html
{% block meta_description %}ZenETFs — Compare ETF portfolio strategies for European investors. 30-year CAGR data, inflation-adjusted returns, UCITS funds.{% endblock %}
{% block og_title %}ZenETFs — Compare ETF Portfolio Returns | 30-Year CAGR Data{% endblock %}
{% block og_description %}Compare long-term ETF portfolio strategies for European investors. CAGR data for 5, 10, 20 and 30 years. Inflation-adjusted returns available.{% endblock %}
{% block title %}Compare ETF Portfolio Returns | 30-Year CAGR Data{% endblock %}
```

---

## 3. `templates/en/portfolios.html`

### Replace blocks (lines 2-3):
```html
{% block meta_description %}ZenETFs — Curated ETF portfolio strategies for European passive investors. Bogleheads-inspired, low-cost, long-term portfolios with CAGR data.{% endblock %}
{% block og_title %}ZenETFs — ETF Portfolio Strategies | Passive Investing Portfolios{% endblock %}
{% block og_description %}Explore curated ETF portfolio strategies for European passive investors. Bogleheads-inspired, low-cost, long-term portfolios with 30-year CAGR data.{% endblock %}
{% block title %}ETF Portfolio Strategies | Passive Investing{% endblock %}
```

---

## 4. `templates/en/etfs.html`

### Replace blocks (lines 2-3):
```html
{% block meta_description %}ZenETFs — Complete list of UCITS ETFs for European investors. Accumulating funds, low TER, domiciled in Ireland and Germany.{% endblock %}
{% block og_title %}ZenETFs — UCITS ETF List | European ETF Database{% endblock %}
{% block og_description %}Browse European UCITS ETFs: accumulating funds, low TER, Irish and German domiciled funds. Compare iShares, Xtrackers, SPDR and more.{% endblock %}
{% block title %}UCITS ETF List | European ETF Database{% endblock %}
```

---

## 5. `templates/en/about.html`

### Replace blocks (lines 2-3):
```html
{% block meta_description %}ZenETFs — About the project. Educational tool comparing long-term historical returns of passive portfolio strategies for European investors.{% endblock %}
{% block og_title %}ZenETFs — About the Project | ETF Portfolio Comparison Tool{% endblock %}
{% block og_description %}Learn about ZenETFs — an educational tool comparing 30-year historical returns of passive ETF portfolio strategies for European investors.{% endblock %}
{% block title %}About the Project | ETF Comparison Tool{% endblock %}
```

---

## 6. `templates/pl/index.html`

### Replace blocks (lines 3-4):
```html
{% block meta_description %}ZenETFs — Porównaj strategie inwestycyjne w ETF dla europejskich inwestorów. 30-letnie dane CAGR, stopy zwrotu skorygowane o inflację, fundusze UCITS.{% endblock %}
{% block og_title %}ZenETFs — Porównanie Portfeli ETF | Dane CAGR z 30 Lat{% endblock %}
{% block og_description %}Porównaj długoterminowe strategie inwestycyjne w ETF dla europejskich inwestorów. Dane CAGR za 5, 10, 20 i 30 lat. Dostępne stopy zwrotu skorygowane o inflację.{% endblock %}
{% block title %}Porównanie Portfeli ETF | Dane CAGR z 30 Lat{% endblock %}
```

---

## 7. `templates/pl/portfolios.html`

### Replace blocks (lines 2-3):
```html
{% block meta_description %}ZenETFs — Strategie portfelowe ETF dla europejskich inwestorów pasywnych. Inspirowane filozofią Bogleheads, niskie koszty, długoterminowe portfele z danymi CAGR.{% endblock %}
{% block og_title %}ZenETFs — Strategie Portfelowe ETF | Inwestowanie Pasywne{% endblock %}
{% block og_description %}Poznaj sprawdzone strategie portfelowe ETF dla europejskich inwestorów pasywnych. Portfele inspirowane filozofią Bogleheads z 30-letnimi danymi CAGR.{% endblock %}
{% block title %}Strategie Portfelowe ETF | Inwestowanie Pasywne{% endblock %}
```

---

## 8. `templates/pl/etfs.html`

### Replace blocks (lines 2-3):
```html
{% block meta_description %}ZenETFs — Kompletna lista ETF UCITS dla europejskich inwestorów. Fundusze akumulujące, niskie TER, domicyl w Irlandii i Niemczech.{% endblock %}
{% block og_title %}ZenETFs — Lista ETF UCITS | Baza Europejskich Funduszy ETF{% endblock %}
{% block og_description %}Przeglądaj europejskie ETFy UCITS: fundusze akumulujące, niskie TER, fundusze z domicylem w Irlandii i Niemczech. Porównaj iShares, Xtrackers, SPDR.{% endblock %}
{% block title %}Lista ETF UCITS | Baza Europejskich ETF{% endblock %}
```

---

## 9. `templates/pl/about.html`

### Replace blocks (lines 2-3):
```html
{% block meta_description %}ZenETFs — O projekcie. Edukacyjne narzędzie porównujące 30-letnie wyniki historyczne pasywnych strategii portfelowych dla europejskich inwestorów.{% endblock %}
{% block og_title %}ZenETFs — O Projekcie | Narzędzie Porównawcze ETF{% endblock %}
{% block og_description %}Dowiedz się więcej o ZenETFs — edukacyjnym narzędziu porównującym 30-letnie historyczne wyniki pasywnych strategii portfelowych ETF.{% endblock %}
{% block title %}O Projekcie | Narzędzie Porównawcze ETF{% endblock %}
```

---

## 10. OG Image Placeholder

Create `/static/og-image.jpg` — a 1200×630px placeholder image. This should be replaced with a branded graphic showing the ZenETFs logo, tagline, and a stylized chart/portfolio visual.

Until a proper image is created, a simple dark background (#0D1B2A) with "ZenETFs" text in the brand colors will work.

---

## 11. Git Workflow

### Branch strategy
```bash
# Start from vibecoding-mod
git checkout vibecoding-mod
git checkout -b feat/seo-improvements
```

### Atomic commits (4 commits total)
1. **`feat(seo): add Open Graph and Twitter Card tags to layout`**
   - `templates/layout.html` — OG tags, twitter:card, title_full block
   - `main.py` — BASE_URL added to ctx()

2. **`feat(seo): improve meta tags for English pages`**
   - `templates/en/index.html`
   - `templates/en/portfolios.html`
   - `templates/en/etfs.html`
   - `templates/en/about.html`

3. **`feat(seo): improve meta tags for Polish pages`**
   - `templates/pl/index.html`
   - `templates/pl/portfolios.html`
   - `templates/pl/etfs.html`
   - `templates/pl/about.html`

4. **`feat(seo): add OG image placeholder`**
   - `static/og-image.jpg` — 1200×630px placeholder

### After review
```bash
# Merge back to vibecoding-mod
git checkout vibecoding-mod
git merge feat/seo-improvements
```

---

## Summary of Changes

| File | Changes |
|------|---------|
| `templates/layout.html` | Add OG tags, add `title_full` block, pass `BASE_URL` |
| `main.py` | Add `BASE_URL` to `ctx()` function |
| `templates/en/index.html` | New title + meta + OG blocks |
| `templates/en/portfolios.html` | New title + meta + OG blocks |
| `templates/en/etfs.html` | New title + meta + OG blocks |
| `templates/en/about.html` | New title + meta + OG blocks |
| `templates/pl/index.html` | New title + meta + OG blocks |
| `templates/pl/portfolios.html` | New title + meta + OG blocks |
| `templates/pl/etfs.html` | New title + meta + OG blocks |
| `templates/pl/about.html` | New title + meta + OG blocks |
| `static/og-image.jpg` | Create placeholder (1200×630px) |
