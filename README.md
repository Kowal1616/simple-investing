# Simple Investing - Long-term Strategy Analyzer

A robust financial analysis tool designed to track and visualize long-term investment strategies. The application focuses on 30-year performance horizons, providing investors with reliable data insights through a sophisticated multi-source data aggregation engine.

## 🚀 Key Features

* **Consensus Price Engine:** Implements a proprietary data validation logic that aggregates financial information from multiple independent market data providers to ensure accuracy and reliability.
* **Long-term Strategy Backtesting:** Specialized in analyzing ETF performance and investment models over extended periods (up to 30 years).
* **Monthly Data Integrity:** Automated updates designed for long-term tracking, reducing noise from daily market volatility.
* **Data Abstraction Layer:** Fully decoupled architecture allowing seamless integration with various professional financial APIs.
* **Clean & Informative UI:** Focused on clarity and actionable insights for strategic asset allocation.

## 🛠 Tech Stack

* **Backend:** Python / Flask (Migrating to FastAPI for async performance)
* **Data Validation:** Pydantic models for strict financial data integrity
* **Frontend:** HTML5, CSS3, Jinja2
* **External Integrations:** Multi-provider REST APIs
* **Environment Management:** Secure configuration via decoupled environment variables

## 📦 Installation & Setup

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
   Create a `.env` file based on the `.env.example` provided in the repository:
   ```env
   DATA_PROVIDER_A_KEY=your_api_key_here
   DATA_PROVIDER_B_KEY=your_api_key_here
   NOTIFIER_API_KEY=your_api_key_here
   ADMIN_EMAIL=your_email@example.com
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

## 🛡 Disclaimer

For Educational Purposes Only.
The information provided by this application is for educational and informational purposes only and should not be construed as professional financial, investment, or legal advice. Past performance is not indicative of future results. All investment strategies involve risk of loss. The author is not responsible for any financial decisions made based on the data provided by this tool.

Developed as a high-performance investment tracking solution.