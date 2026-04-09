# ZenETFs - Long-term Strategy Analyzer

A robust financial analysis tool designed to track and visualize long-term investment strategies. The application focuses on 30-year performance horizons, providing investors with reliable data insights through a sophisticated multi-source data aggregation engine.

## 🚀 Key Features

* **Consensus Price Engine:** Aggregates financial information from multiple independent market data providers (e.g., Yahoo Finance, AlphaVantage) to ensure accuracy and reliability.
* **Long-term Strategy Backtesting:** Specialized in analyzing ETF performance and investment models over extended periods (up to 30 years).
* **Monthly Data Integrity:** Automated background updates designed for long-term tracking, reducing noise from daily market volatility.
* **Modern & Responsive UI:** Custom dark-mode interface optimized for both desktop and mobile, with seamless PL/EN language switching.
* **Automated CI/CD Pipeline:** Fully automated, "hands-off" deployments utilizing modern DevOps practices.

## 🛠 Tech Stack

* **Backend:** Python / FastAPI / Gunicorn
* **Database:** SQLite with SQLAlchemy ORM
* **Frontend:** HTML5, Vanilla CSS3 (Custom Design System), Jinja2, Lucide Icons
* **Infrastructure:** Docker, Docker Compose
* **CI/CD:** GitHub Actions (Image Build & Push to GHCR), Watchtower (Auto-deployment)
* **Networking & Security:** Nginx Proxy Manager (Reverse Proxy, Auto SSL Termination via Let's Encrypt) 

## 📦 Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Kowal1616/simple-investing.git
   cd simple-investing
   ```

2. **Set up virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Create a `.env` file based on the `.env.example` provided:
   ```env
   ALPHAVANTAGE_API_KEY=your_api_key_here
   ADMIN_EMAIL=your_email@example.com
   CALLMEBOT_API_KEY=your_callmebot_api_key
   MY_PHONE_NUMBER=your_phone_number_with_country_code
   ```

5. **Run the application locally:**
   ```bash
   uvicorn main:app --reload
   ```

## 🚀 Deployment & Production (CI/CD)

The application runs on a production-ready containerized stack with a fully automated pipeline:

1. **Continuous Integration (CI):** Every push to the `main` branch triggers a GitHub Actions workflow. This builds a new Docker image, tags it with a unique commit SHA, and pushes it to the GitHub Container Registry (GHCR).
2. **Continuous Deployment (CD) with Watchtower:** An actively maintained fork of Watchtower (`nickfedor/watchtower`) runs as a background container on the production server. It checks GHCR every 5 minutes for new image layers. Upon detecting a change, it automatically pulls the new image, updates the application container, and removes old data.
3. **Reverse Proxy & SSL:** **Nginx Proxy Manager** sits in front of the application network. It manages HTTPS traffic, automatically provisions and renews SSL certificates via Let's Encrypt, and forwards requests securely to the isolated FastAPI container on port 5000.

To manually start the production stack on the server:
```bash
docker compose pull
docker compose up -d
```

## 🛡 Disclaimer

For Educational Purposes Only.
The information provided by this application is for educational and informational purposes only and should not be construed as professional financial, investment, or legal advice. Past performance is not indicative of future results. All investment strategies involve risk of loss. The author is not responsible for any financial decisions made based on the data provided by this tool.

Developed as a high-performance investment tracking solution.