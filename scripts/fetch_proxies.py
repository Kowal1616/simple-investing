import yfinance as yf
import pandas as pd
import time
import os

proxies = {
    '^GSPC': 'gspc_history.csv',
    '^NDX': 'nasdaq_history.csv',
    'GC=F': 'gold_history.csv',
    'ACWI': 'acwi_history.csv',
    'BND': 'bnd_history.csv'
}

def fetch():
    for ticker, filename in proxies.items():
        if os.path.exists(filename):
            print(f"{filename} exists, skipping.")
            continue
            
        print(f"Fetching {ticker}...")
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="max", interval="1mo")
            if not df.empty:
                df.to_csv(filename)
                print(f"Saved {len(df)} rows for {ticker}")
            else:
                print(f"Empty results for {ticker}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
        
        time.sleep(15) # Safety first

if __name__ == "__main__":
    fetch()
