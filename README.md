# ZenETFs (SimpleInvesting) - Long-term Strategy Analyzer 🚀

ZenETFs is a sophisticated financial analysis platform designed for evaluating long-term investment strategies over extended horizons (30+ years). The system utilizes a high-performance aggregation engine to synthesize market and macroeconomic data, providing investors with accurate, inflation-adjusted performance metrics for complex asset portfolios.

## 🚀 Key Engine Features

### Multi-Source Data Aggregator
The platform implements advanced data validation logic across multiple **Professional Financial APIs**. By aggregating disparate market signals, the engine ensures high data integrity and eliminates single-source dependencies, providing a reliable consensus for asset pricing and valuation.

### Inflation & FX-Adjusted Returns (Real CAGR)
To track true purchasing power, ZenETFs features a sophisticated mechanism for calculating **Real CAGR**. This process incorporates local consumer price indices and historical exchange rate fluctuations, allowing investors to analyze performance in terms of real-world value rather than nominal figures.

### V3 Portfolio Architecture
The system utilizes an automated **3-ETF Basket Strategy** for each asset class. This architecture provides a mathematically balanced representation of market segments, ensuring that portfolio modeling reflects a diversified and weighted average of the target markets.

### Rebalanced Compounding Logic
Portfolio performance is calculated using a robust **Monthly Compound Returns** algorithm. This logic eliminates common errors associated with asset denomination differences and ensures that reinvestment and rebalancing effects are accurately captured over the three-decade analysis window.

## 🛠 Technical Ecosystem

### Backend
**Modern Python (FastAPI):** The core service has been fully migrated to an asynchronous FastAPI architecture. This transition ensures high concurrency, low-latency data processing, and superior performance.

### Frontend
**Responsive Dark-Mode UI:** Built with standard HTML5, Vanilla CSS3, and JavaScript, the interface is integrated with Jinja2 for dynamic server-side rendering. The design system is optimized for accessibility and mobility, providing a premium user experience across all devices.

### Infrastructure
**Containerized Orchestration:** The entire application stack is fully containerized using **Docker** and **Docker Compose**. A dedicated **Nginx Proxy Manager** handles SSL termination and reverse proxying, ensuring secure and efficient traffic management.

### DevOps & Automation
**Automated CI/CD Pipeline:** Leveraging **GitHub Actions**, the platform implements a "hands-off" deployment workflow. The **Continuous Deployment (Watchtower)** mechanism automatically detects registry updates and rotates containers in real-time, ensuring zero-downtime updates.

## 📢 Reliability & Security

### Dual-Channel Notification System
A hybrid monitoring system provides real-time visibility into system health and deployment status. Stakeholders receive synchronized alerts via **Mobile Messaging** and **Email** for deployment confirmations and critical runtime events.

### Configuration Management
Strict adherence to a **Zero-Hardcoding Policy** ensures that sensitive data is entirely decoupled from the source code. Configuration is managed exclusively through secure environment variables, following industry-standard safety practices.

## 📦 Setup & Usage Guidelines

### Installation
The application requires a standard Python environment (3.10+ recommended):

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

### Environment Variables
To operate the data ingestion and notification engines, a `.env` file must be prepared in the root directory. This file should contain the necessary API keys and configuration parameters according to the internal project specification (e.g., `DATA_PROVIDER_KEY`, `NOTIFIER_API_KEY`). Ensure that the service has access to the required market data endpoints and notification gateways.

## 🛡 Disclaimer

For Educational Purposes Only. 
The information provided by this application is for educational and informational purposes only and should not be construed as professional financial, investment, or legal advice. Past performance is not indicative of future results. All investment strategies involve risk of loss. The author is not responsible for any financial decisions made based on the data provided by this tool.

---
*Developed as a high-performance investment tracking solution.*