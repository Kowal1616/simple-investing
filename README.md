
> [!NOTE] 
> <sub>Disclaimer: This repository contains the final project for the CS50 Course, shared for educational purposes and to demonstrate coding skills. While some of the data utilized in this project may be intended for personal use, it is not displayed on the application web page. The historical data stored in the database is sourced from various sources and has been enhanced with simulations.</sub>


:star: For HOW-TO scroll to the bottom :star:


# SIMPLE INVESTING - portfolio comparison tool
### Video Demo:  Coming soon..<URL HERE>
### Description:

Simple Investing is a Flask App that aims at promotion of low-cost, low-maintains, long-term investing (Boggleheads style!). My app's main feature is a table which displays long term returns of chosen etfs based portfolios over 5, 10, 20 and 30 years periods. A comparison table is fed with extended historical data (enhanced with corresponding indexes and simulations) and up to date thanks to monthly performed updates from two independent data sources.

There is a similar tool for US based investors featuring US Etfs that I took inspiration of. My app is unique in a way that it's aimed at EU based investors and all Portfolios consist of European Etfs. The first EU-based ETF was launched approximately 20 years ago, and the ETFs I've utilized likely have a historical record spanning 10-15 years. As a result, the extended historical data significantly enhances the value of the final data displayed on the web page.

#### **PROJECT STRUCTURE**
In *app.py*:
+ Initialize my flask app, SQL-Alchemy and logging system
+ Define app routes
+ Call functions (see below) and set scheduler

In *helpers.py*:
+ Define most of my app's functions

In *models.py*:
+ Set the db
+ Define db classes

Additionally I used *csv-importer.py* - a simple script to feed the db with csv structured data before first running my app. To reach 30 years history I have extended etfs historical returns with indexes and at some cases simulated results based on average long term returns.

I intended to avoid using robust functions, trying to follow *one_function-one_purpose* principle. I have also worked hard to implement *clean-code* philosophy with clear and informative names and comments.

#### **STEP-BY-STEP - PROCESS EXPLAINED**

1. `get_etfs_data` function - App is set to fetch data (etfs prices) from two different online sources (one via API, one via library).
2. `append_etfs_prices` function - A db table storing historical prices is appended with new data. 
3. `get_etfs_yields` function and `update_etfs_yields` function - Etfs annual yeilds are computed and updated to the db. I decided to use CAGR (Compound Annual Growth Rate) as it is really good at showing how different investments have performed over time.
4. `get_portfolio_returns` function and `update_portfolios_returns` function - Portfolios annual yields are computed (based on etfs yields) and updated to the db.
5. `get_inflation` function and `update_inflation` function - Inflation cumulative rates are computed for 5, 10, 20 and 30 years periods. Those are updated to the db.
6. `get_portfolios_results` function, `get_portfolios_drawdown` function and `update_portfolios_drawdown` function - Portfolios historical results are computed to be later used to compute max drawdowns (biggest loss in set period of time - good indicator to show investment risk) over set periods of time (5, 10, ...). Those are updated to the db.
7. App is displaying chosen db data on the web page.

#### **RE 1:**
This process is triggered once on a startup and than once a month via scheduler (monthly data is used). Whole process runs only if: 1) data for previous month isn't already present in the db, or 2) it's not the first day of the month and data might not be available yet.

To minimize the lack of data I decided to use two separate sources. One of those I access via API (output in *csv* format) and the other one via open-source library (output in pandas *DataFrame* format). If data from both is available I use the average.

I have considered adding a mechanism checking db for needed update further back in time but as the app is intended to run on the server all the time and in event of crash it would be soon restarted, I dropped it as unneeded.

#### **RE 2-6:**
All functions are stored in *helpers.py* and called in *app.py* on startup and than once a month via scheduler.

#### **RE 7:**
The portfolio comparison tool (= index page table) displays data from the database. `@app.route('/api/data')` is making the data available for `@app.route("/")`. On the index page I use *Grid.js* library to create the table. It makes it easy to create it simple and slick with custom sorting - exactly as I need it. Table can be 'scrolled' to the right to access more data.

I use *Bootstrap* Cover template (I link to the author in the footer of each page).

#### **ADDITIONAL FEATURES**
User can access each Portfolio and Etf profile page with additional information and link to official profile (Etfs). Those are accessible both via collapsible menu and by clicking Portfolio/Etf name in the table.

I'm also using an AI generated project logo :)

#### **ERROR HANDLING**
I use `try/except` blocks in functions susceptible to errors, particularly those involving database operations or external online data. In addition I set up an e-mail notification tool, so I will get notified via e-mail (using *Sendgrid* library) when serious errors occur. I'm also logging errors using Python's *logging* module.

#### **FUTURE DEVELOPMENT**
+ Adding more strategies and real estate investment to comparison tool.
+ Quiz game assigning a investor profile based on answered questions, investor profiles would be matched with best fitting portfolios.
+ GEM feature - a Global Equity Momentum strategy signals. 
+ User profiles to store their favorite strategies, send alerts and performance reports.
+ Portfolio profiles enhanced with one
+ And more...


:herb: I have decided to use only dark theme for my web page as it's more energy efficient. Dark themes consume less energy as they require less power to illuminate pixels. By minimizing energy consumption, I contribute to reducing the carbon footprint associated with digital activities.


My Flask app represents an effort to provide EU-based investors with a powerful tool for long-term investment planning. With a focus on simplicity, reliability, and sustainability, I have developed a platform that empowers users to make informed decisions about their financial futures.

# How to Run the Application
Choose your preferable way to run my application from options below, if encountered any problems look into Troubleshooting.

<details>
<summary>Running Locally</summary>


1. **Clone the repository:**

    ```
    git clone https://github.com/Kowal1616/simple-investing.git
    cd your-repo
    ```

2. **Create a virtual environment:**

    ```
    python3 -m venv venv
    source venv/bin/activate   # On Windows use `venv\Scripts\activate`
    ```

3. **Install the dependencies:**

    ```
    pip install -r requirements.txt
    ```

4. **Set environment variables:**
    The only necessary environment variable you need is (you can obtain it for free):
    - `ALPHAVANTAGE_API_KEY`

    For full functionality make sure you add those environment variables:

    - `SENDGRID_API_KEY`
    - `ADMIN_EMAIL`

    You can set these variables in your environment or create a `.env` file in the root of your project and add the variables there.

5. **Initialize the database:**

    ```
    flask db init
    flask db migrate
    flask db upgrade
    ```

6. **Run the application:**

    ```
    flask run
    ```

    The application will be available at `http://127.0.0.1:5000/`.

</details>

<details>
<summary>Running in GitHub Codespaces</summary>


1. **Open the repository in GitHub Codespaces:**

    - Navigate to your repository on GitHub.
    - Click the `Code` button and select `Codespaces`.
    - Create a new Codespace or open an existing one.

2. **Install the dependencies:**

    In the Codespace terminal, run:

    ```
    pip install -r requirements.txt
    ```

3. **Set environment variables:**

    In the Codespace terminal, set the environment variable:

    ```
    export ALPHAVANTAGE_API_KEY=your_alphavantage_api_key
    ```
    For full fucntionality you can add:

    ```
    export SENDGRID_API_KEY=your_sendgrid_api_key
    export ADMIN_EMAIL=your_admin_email
    ```

    Alternatively, you can set these variables in the `.devcontainer/devcontainer.json` file to automatically set them up when the Codespace is created.

4. **Initialize the database:**

    ```
    flask db init
    flask db migrate
    flask db upgrade
    ```

5. **Run the application:**

    ```
    flask run --host=0.0.0.0
    ```

    The application will be available at `http://localhost:5000/`.

</details>

<details>
<summary>Troubleshooting</summary>

+ Make sure your database (SQLite in this case) and other dependencies are correctly set up.
+ Adjust paths and configurations as necessary for your specific environment.
+ Make sure the environment variables are correctly set.
+ Check the Flask documentation for more details on configuration and setup: Flask Documentation
</details>