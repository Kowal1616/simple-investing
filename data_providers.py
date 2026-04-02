import os
import logging
import requests
import datetime
import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, List
import pandas_datareader.data as web


class BaseDataProvider(ABC):
    """
    Abstract base class for all market data providers.
    Ensures a consistent interface for fetching prices.
    """
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_price(self, ticker: str) -> Optional[float]:
        """
        Fetch the price for a given ticker.
        Should return a float if successful, or None if an error occurs.
        """
        pass


class ProviderA(BaseDataProvider):
    """Primary market data provider (REST API, adjusted close)."""

    def get_name(self) -> str:
        return "Provider-A"

    def get_price(self, ticker: str) -> Optional[float]:
        api_key = os.getenv('DATA_PROVIDER_A_KEY')
        if not api_key:
            logging.error(f"Error: Missing API key for [{self.get_name()}]. Skipping this source.")
            return None

        today = datetime.date.today()
        end_date = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = end_date.replace(day=1)

        base_url = os.getenv('DATA_PROVIDER_A_HOST', 'https://api.marketdata.example.com')
        # EODHD Mapping: German stocks/ETFs use .XETRA suffix
        if ticker.endswith('.DE'):
            provider_ticker = ticker.replace('.DE', '.XETRA')
        else:
            provider_ticker = ticker
        
        url = f"{base_url}/eod/{provider_ticker}?api_token={api_key}&fmt=json&from={start_date}&to={end_date}&period=m"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                price = data[-1].get('adjusted_close')
                if price is not None and float(price) > 0:
                    return float(price)
            return None
        except Exception as e:
            logging.error(f"Failed to fetch data from {self.get_name()}: {e}")
            return None


class ProviderB(BaseDataProvider):
    """Secondary market data provider (REST API, end-of-day prices)."""

    def get_name(self) -> str:
        return "Provider-B"

    def get_price(self, ticker: str) -> Optional[float]:
        api_key = os.getenv('DATA_PROVIDER_B_KEY')
        if not api_key:
            logging.error(f"Error: Missing API key for [{self.get_name()}]. Skipping this source.")
            return None

        today = datetime.date.today()
        end_date = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = end_date.replace(day=1)

        base_url = os.getenv('DATA_PROVIDER_B_HOST', 'https://api.marketdata2.example.com')
        # Robust URL construction: if base_url ends with /v1, don't repeat it
        if base_url.rstrip('/').endswith('/v1'):
            base_url = base_url.rstrip('/').replace('/v1', '')
        
        # Marketstack Mapping: German stocks/ETFs use .XETRA suffix
        if ticker.endswith('.DE'):
            provider_ticker = ticker.replace('.DE', '.XETRA')
        else:
            provider_ticker = ticker
            
        url = f"{base_url.rstrip('/')}/v1/eod?access_key={api_key}&symbols={provider_ticker}&date_from={start_date}&date_to={end_date}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and 'data' in data and len(data['data']) > 0:
                # Sorted descending by default; index 0 is the most recent record in range
                price = data['data'][0].get('adj_close') or data['data'][0].get('close')
                if price is not None and float(price) > 0:
                    return float(price)
            return None
        except Exception as e:
            logging.error(f"Failed to fetch data from {self.get_name()}: {e}")
            return None


class ProviderC(BaseDataProvider):
    """Tertiary market data provider (open-source library fallback)."""

    def get_name(self) -> str:
        return "Provider-C"

    def get_price(self, ticker: str) -> Optional[float]:
        try:
            today = datetime.date.today()
            end_date = today.replace(day=1) - datetime.timedelta(days=1)
            start_date = end_date.replace(day=1)

            df = web.DataReader(ticker, 'stooq', start=start_date, end=end_date)
            if not df.empty:
                # Index is typically descending dates; iloc[0] is the most recent
                last_price = df['Close'].iloc[0]
                if pd.notnull(last_price) and float(last_price) > 0:
                    return float(last_price)

            logging.warning(f"Skipping source {self.get_name()} for {ticker}: empty or zero response.")
            return None
        except Exception as e:
            # Handles cases like provider downtime or API/selector changes
            logging.error(f"Failed to fetch data from {self.get_name()} (provider outage / API change): {e}")
            return None


class FinancialDataService:
    """
    Aggregates data from multiple independent market data providers
    and returns a consensus price (arithmetic mean of valid responses).
    """

    def __init__(self):
        self.providers: List[BaseDataProvider] = [
            ProviderA(),
            ProviderB(),
            ProviderC(),
        ]

    def get_consensus_price(self, ticker: str) -> Optional[float]:
        """
        Fetches the price from all configured providers.
        Returns the arithmetic mean of all successfully retrieved prices.
        Logs a warning if divergence between sources exceeds 5%.
        """
        prices = []
        for provider in self.providers:
            price = provider.get_price(ticker)
            if price is not None:
                prices.append(price)
                logging.info(f"Fetched price {price} for {ticker} from {provider.get_name()}")
            else:
                logging.warning(f"Skipping source {provider.get_name()} for {ticker} (no data or error).")

        if prices:
            if len(prices) > 1:
                min_price = min(prices)
                max_price = max(prices)
                if min_price > 0 and ((max_price - min_price) / min_price) > 0.05:
                    logging.warning(
                        f"WARNING: Significant price divergence (>5%) detected for {ticker}! "
                        f"Prices: {prices}. Flagging as suspicious, but including in average."
                    )

            consensus = sum(prices) / len(prices)
            logging.info(f"Consensus price for {ticker}: {consensus} (calculated from {len(prices)} successful sources)")
            return round(consensus, 2)

        logging.error(f"All data sources failed for {ticker}.")
        return None
