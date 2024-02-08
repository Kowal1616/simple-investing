import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import yfinance as yf
import requests
import pandas as pd
from io import StringIO
import datetime
import inspect
from models import *
import logging


# Use SendGrid api_key that is stored as environment variable
sendgrid_api_key = os.getenv('SENDGRID_API_KEY')

# Use admin email that is stored as environment variable
admin_email = os.getenv('ADMIN_EMAIL')

# Use AlphaVantage api_key that is stored as environment variable
alphavantage_api_key = os.getenv('ALPHAVANTAGE_API_KEY')


def get_etfs_data(session):
    """ Retrive data from online sources """
    try:
        # Generate the 'date' record
        # (first day of the month date is a symbol date for previous month closing price!)
        today = datetime.date.today()
        first_day = today.replace(day=1)
        csv_date = first_day.strftime('%Y-%m-%d')

        # Check if data retrival was already performed for previous month but skip checking if it's first day of the month (data might not be available yet)
        check_date = session.query(HistoricalDataEtfs.date).order_by(HistoricalDataEtfs.date.desc()).first()

        if today.day == 1:
            print("DATA NOT AVAILABLE! -> Today is the first day of the month. Try retriving data tomorrow.")

        elif not check_date.date == csv_date:

            # Retrive both tickers from the db
            result = session.query(Etfs.id, Etfs.yfinance_name, Etfs.alphavantage_name).all()

            # Initialize lists to store data and failed retrieval tickers
            etfs_prices = [csv_date]
            failed_retrieval_etfs = ['Data retrival failed for:']

            # Iterate through tickers and retrieve data
            for id, ticker_yf, ticker_av in result:
                av_price, yf_price = 0, 0
                try:
                    # Retrieve data using AlphaVantage API
                    av_price = round(data_retrival_av(ticker_av), 2)
                    if av_price == 0:
                        av_price = None

                except Exception as e:
                    # Handle AlphaVantage API errors
                    failed_retrieval_etfs.append(f"AV - {ticker_av} ({e})")
                try:
                    # Retrieve data using Yahoo Finance
                    yf_price = round(data_retrival_yf(ticker_yf, today), 2)
                    if yf_price == 0:
                        yf_price = None

                except Exception as e:
                    # Handle Yahoo Finance errors
                    failed_retrieval_etfs.append(f"YF - {ticker_yf} ({e})")

                # Compute final value using both sources if available
                if av_price is not None and av_price != 0 and yf_price is not None and yf_price != 0:
                    final_price = round((av_price + yf_price) / 2, 2)
                    etfs_prices.append(final_price)
                elif av_price is not None and av_price != 0:
                    etfs_prices.append(av_price)
                elif yf_price is not None and yf_price != 0:
                    etfs_prices.append(yf_price)
                else:
                    # Both methods failed, temporarily add last month price (so the user see that db is 'up to date')
                    column_name = f"etf{id}_price"
                    last_month_price = session.query(getattr(HistoricalDataEtfs, column_name)).order_by(HistoricalDataEtfs.id.desc()).first()
                    etfs_prices.append(last_month_price)
                    print(f'\n#*#*#*#* DATA RETRIVAL FAILED FOR: *#*#*#*#\n{ticker_yf} / {ticker_av}\n#*#*#*#* LAST ADDED FOR TEMP FIX #*#*#*#*')

            # Send email if db update error occurred
            if failed_retrieval_etfs:
                update_error_email(failed_retrieval_etfs)

            return etfs_prices

        else:
            print("DATA ALREADY APPENDED -> Data for the last month have been appended previously, current call dropped")

    except Exception as e:
        # Handle unexpected errors
        print(f"An unexpected error occurred: {e}")
        logging.error(f'An error occurred in get_etfs_data(): {e}', exc_info=True)
        return None


def append_etfs_prices(etfs_prices, session):
    """ Update historical_data_etfs table """
    print(etfs_prices)
    try:
        if etfs_prices is not None:
            # Add a row to the database table
            # Unpack etfs_prices and create a new row
            new_row = HistoricalDataEtfs(
                date=etfs_prices[0],
                etf1_price=(etfs_prices[1]),
                etf2_price=(etfs_prices[2]),
                etf3_price=(etfs_prices[3]),
                etf4_price=(etfs_prices[4]),
                etf5_price=(etfs_prices[5]),
                etf6_price=(etfs_prices[6])
            )
            session.add(new_row)

            '''
            for i in range(len(etfs_prices)):
                setattr(db_table, 'column' + str(i+1), etfs_prices[i])
                session.add(db_table)

            session.commit()
            '''
        else:
            logging.warning("Variable etfs_prices is None. Skipping database update.", exc_info=True)

    except Exception as e:
        # Handle the exception (e.g., log the error, send email notification)
        function_name = inspect.currentframe().f_code.co_name
        logging.error(f'An error occurred in {function_name}: {e}', exc_info=True)
        update_error_email(e)



def get_etfs_yields(session):
    """ Compute etfs yields """
    # Query for list of etfs ids
    etfs_ids = [id for (id) in session.query(Etfs.id).all()]
    # Query db for etfs historical data and calculate yields [5, 10, 20, 30, 40 years]
    # - declare a list of tuples to store values
    etfs_yields = []

    for (id,) in etfs_ids:
        column_name = f"etf{id}_price"
        etf_prices = session.query(getattr(HistoricalDataEtfs, column_name)).all()

        num_prices = len(etf_prices)
        periods = [60, 120, 240, 360, 480]
        years_in_periods = [5, 10, 20, 30, 40]
        temp_yields = []

        for period, years in zip(periods, years_in_periods):
            if num_prices > period:
                ''' etf_yield = round((((etf_prices[-1][0] - etf_prices[-period][0]) / etf_prices[-period][0]))*100, 2)'''
                # Compute CAGR - compound annual growth rate
                etf_yield = round(((etf_prices[-1][0] / etf_prices[-period][0]) ** (1 / years) - 1) * 100, 2)
                temp_yields.append(etf_yield)
            else:
                temp_yields.append('0')

        etfs_yields.append(temp_yields)

    # Return a list of tuples with yeilds for each etf
    return etfs_yields


def update_etfs_yields(etfs_yields, session):
    """ Update Etfs table """
    try:
        etfs = session.query(Etfs).all()

        for etf, yield_tuple in zip(etfs, etfs_yields):
            etf.yield5, etf.yield10, etf.yield20, etf.yield30, etf.yield40 = yield_tuple

        session.commit()
    except Exception as e:
        # Handle the exception (e.g., log the error, send email notification)
        function_name = inspect.currentframe().f_code.co_name
        logging.error(f'An error occurred in {function_name}: %s', e, exc_info=True)
        update_error_email(e)


def get_portfolio_returns(session):
    """ Compute portfolios returns """
    # Query for list of portfolio ids
    portfolios_ids = [id for (id,) in session.query(Portfolios.id).all()]

    # Create a list of touples to store portfolios returns
    portfolios_returns = []

    # Loop trough portfolios (and etfs) calculating yields
    for id in portfolios_ids:
        # Query db for etf details (etf_id and percentage)
        portfolio_info = (
            session.query(PortfolioComposition.etf_id, PortfolioComposition.percentage)
            .filter(PortfolioComposition.portfolio_id == id)
            .all()
        )

        # Query db for etfs yields and compute returns [5, 10, 20, 30, 40years]
        portfolio_yields = []

        years_in_periods = [5, 10, 20, 30, 40]

        for period in years_in_periods:
            period_return = 0

            for etf_id, percentage in portfolio_info:
                column = getattr(Etfs, f'yield{period}')
                etf_yield = session.query(column).filter(Etfs.id == etf_id).all()

                # Check if a value is None
                if etf_yield[0][0] != 0:
                    period_return += round(etf_yield[0][0] * percentage, 2)
                else:
                    # Break the loop when None value is encountered
                    period_return = 0
                    break

            portfolio_yields.append(period_return)

        portfolios_returns.append(portfolio_yields)

    # Return a list of tuples with yeilds for each etf
    return portfolios_returns


def update_portfolios_returns(portfolios_returns, session):
    """ Update portfolios table """
    try:
        portfolios = session.query(Portfolios).all()

        for portfolio, return_tuple in zip(portfolios, portfolios_returns):
            portfolio.return5, portfolio.return10, portfolio.return20, portfolio.return30, portfolio.return40 = return_tuple

        session.commit()
    except Exception as e:
        # Handle the exception (e.g., log the error, send email notification)
        function_name = inspect.currentframe().f_code.co_name
        logging.error(f'An error occurred in {function_name}: %s', e, exc_info=True)
        update_error_email(e)


def get_inflation(session):
    """ Compute inflation """
    # Query for list of currencies
    currencies_list = [currency for (currency,) in session.query(InflationHistoricalPeriods.currency).all()]

    # Create a list of touples to store inflation for currencies
    currencies_inflation = []

    # Loop trough currencies calculating rates in set periods [5, 10, 20, 30, 40years]
    for currency in currencies_list:
        # List of looped currency inflation rates in periods
        inflation_periods = []

        column_name = f"{currency}_inflation_rate"
        currency_inflation_rates = session.query(getattr(InflationRates, column_name)).all()

        num_rates = len(currency_inflation_rates)
        years_in_periods = [5, 10, 20, 30, 40]

        for years in years_in_periods:

            if num_rates > years:
                # Computing the sum of 'years' last values
                start_index = max(0, len(currency_inflation_rates) - years)
                sum_of_rates = sum(rate for (rate,) in currency_inflation_rates[start_index:])
                inflation_periods.append(sum_of_rates)
            else:
                inflation_periods.append('0')

        currencies_inflation.append(inflation_periods)

    # Return a list of tuples with inflation rates for each currency
    return currencies_inflation


def update_inflation(currencies_inflation, session):
    """ Update inflation_historical_periods table """
    try:
        periods = session.query(InflationHistoricalPeriods).all()

        for period, inflation_tuple in zip(periods, currencies_inflation):
            period.inflation5, period.inflation10, period.inflation20, period.inflation30, period.inflation40 = inflation_tuple

        session.commit()
    except Exception as e:
        # Handle the exception (e.g., log the error, send email notification)
        function_name = inspect.currentframe().f_code.co_name
        logging.error(f'An error occurred in {function_name}: %s', e, exc_info=True)
        update_error_email(e)

def get_portfolios_results(session):
    """ Compute portfolios historical results """
    # Query for list of portfolio ids
    portfolios_ids = [id for (id,) in session.query(Portfolios.id).all()]

    # Create a list of touples to store portfolios historical results
    portfolios_results = []

    # Loop trough portfolios calculating historical results
    for portfolio_id in portfolios_ids:
        # Query db for etf details (etf_id and percentage)
        portfolio_info = (
            session.query(PortfolioComposition.etf_id, PortfolioComposition.percentage)
            .filter(PortfolioComposition.portfolio_id == portfolio_id)
            .all()
        )

        portfolio_results = []

        # Loop trough etfs calculating historical results
        for etf_id, percentage in portfolio_info:
            column = getattr(HistoricalDataEtfs, f'etf{etf_id}_price')
            etf_results = session.query(column).all()

            if not portfolio_results:
                portfolio_results = [round(result[0] * percentage, 2) for result in etf_results]
            else:
                portfolio_results = [round(a + b[0] * percentage, 2) for a, b in zip(portfolio_results, etf_results)]

        portfolios_results.append(portfolio_results)

    # Return a list of lists with results for each etf
    return portfolios_results


def get_portfolios_drawdown(portfolios_results):
    """ Compute portfolios maximum drawdown """
    """ based on: https://seekingalpha.com/instablog/42079636-kayode-omotosho/5377452-computing-maximum-drawdown-of-stocks-in-python """
    portfolios_drawdown = []

    for portfolio in portfolios_results:
        # Convert the list of floats to a pandas Series
        portfolio_series = pd.Series(portfolio)

        # Compute monthly returns
        portfolio_returns = portfolio_series.pct_change()

        # Compute the wealth index -> cumulative portfolio return over time
        wealth_index = 1000*(1+portfolio_returns[1:]).cumprod()

        # Compute the previous peak -> cumulative maximum of the wealth index
        previous_peaks = wealth_index.cummax()

        # Compute drawdown
        drawdown = round((wealth_index - previous_peaks)/previous_peaks, 2)

        portfolios_drawdown.append(drawdown)

    return portfolios_drawdown


def update_portfolios_drawdown(portfolios_drawdown, session):
    """ Update portfolios table """
    try:
        # Retrieve portfolios from the database
        portfolios = session.query(Portfolios).all()

        # Loop through portfolios and drawdown values
        for portfolio, drawdown in zip(portfolios, portfolios_drawdown):
            # Calculate the maximum drawdown value from the drawdown list
            max_drawdown = max(drawdown)

            # Update the max_drawdown5 attribute with the calculated maximum drawdown value
            portfolio.max_drawdown5 = max_drawdown

        # Commit the changes to the database
        session.commit()
    except Exception as e:
        # Handle the exception (e.g., log the error, send email notification)
        function_name = inspect.currentframe().f_code.co_name
        logging.error(f'An error occurred in {function_name}: %s', e, exc_info=True)
        update_error_email(e)


def send_email(title, email_content):
    """ Send e-mails via SendGrid """
    message = Mail(
        from_email='error@simple-investing.com',
        to_emails=admin_email,
        subject='{}'.format(title),
        html_content='{}'.format(email_content))
    try:
        sendgrid_client = SendGridAPIClient(sendgrid_api_key)
        response = sendgrid_client.send(message)
        print(response.status_code)
    except Exception as e:
        function_name = inspect.currentframe().f_code.co_name
        logging.error(f'An error occurred in {function_name}: %s', e, exc_info=True)
        return False

    return True


def update_error_email(e):
    # Handle any errors that occurred
    print(f"An error occurred: {e}")
    # Send email notification to admin
    title = 'SimpleInvesting - Database Update Error in your app'
    function_name = inspect.currentframe().f_code.co_name
    message = (f'<strong>The {function_name} script failed to Update data. An error occured: {e}.</strong>')
    send_email(title, message)


def data_retrival_yf(ticker_yf, today):
    # Retrieve data using Yahoo Finance (last row is the latest data)
    # Get the last day of the previous month
    last_day_of_previous_month = today.replace(day=1) - datetime.timedelta(days=1)

    # Get the first day of the previous month
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    # Fetch historical price data using yfinance for the previous month
    etf_prices_df = yf.download(ticker_yf, start=first_day_of_previous_month, end=last_day_of_previous_month)

    # Extract the adjusted close price for the last day of the previous month
    yf_price = etf_prices_df['Adj Close'].iloc[-1]

    return yf_price


def data_retrival_av(ticker_av):
    # Retrieve data using AlphaVantage API (second row is last month adjusted close data)
    url = 'https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol={}&apikey={}&datatype=csv'.format(
        ticker_av, alphavantage_api_key)
    response = requests.get(url)

    # Check if the request was successful
    response.raise_for_status()

    # Process AlphaVantage data
    etf_prices_df = pd.read_csv(StringIO(response.text))
    av_price = (etf_prices_df['adjusted close'].iloc[1])

    return av_price

