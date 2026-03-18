import requests
import sys
import os
import datetime as dt
import pandas as pd
from io import StringIO
import yfinance as yf
import json


api_key = 'KXVHJOM0F0IHP28J'
''' os.getenv('ALPHAVANTAGE_API_KEY') '''
print(api_key)

today = dt.date.today()



# Get the filename from the command line arguments
# ticker = sys.argv[1]

ticker = "4GLD.DEX"

url = 'https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol={}&apikey={}&datatype=csv'.format(
    ticker, api_key)
print(url)

response = requests.get(url)
print(response.text)



ticker_yf = "SXR8.DE"

# Retrieve data using Yahoo Finance (last row is the latest data)
# Get the last day of the previous month
last_day_of_previous_month = today.replace(day=1) - dt.timedelta(days=1)

# Get the first day of the previous month
first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

# Fetch historical price data using yfinance for the previous month
etf_prices_df = yf.download(ticker_yf, start=first_day_of_previous_month, end=last_day_of_previous_month)

# Extract the adjusted close price for the last day of the previous month
yf_price = etf_prices_df['Adj Close'].iloc[-1]

print(yf_price)

