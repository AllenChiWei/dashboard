import yfinance as yf
import pandas as pd
from datetime import date
from src.crawlers.base import BaseCrawler

class YahooCrawler(BaseCrawler):
    def fetch_data(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Fetch data from Yahoo Finance.
        """
        self.logger.info(f"Fetching {symbol} from {start_date} to {end_date} via Yahoo Finance")
        
        try:
            df = yf.download(symbol, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                self.logger.warning(f"No data found for {symbol}")
                return pd.DataFrame()

            # yfinance returns MultiIndex if only one ticker is fetched, need to flatten?
            # Actually, yfinance returns Date as index.
            df = df.reset_index()
            
            # Standardize column names
            df.columns = [c.lower() for c in df.columns]
            # yfinance columns are: Date, Open, High, Low, Close, Adj Close, Volume
            # map 'adj close' to 'adjusted_close'
            df.rename(columns={'adj close': 'adjusted_close'}, inplace=True)
            
            # Ensure required columns exist
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close']
            
            # Handling case where yfinance might return different columns (e.g., 'Close' instead of 'Adj Close')
            if 'adjusted_close' not in df.columns and 'close' in df.columns:
                df['adjusted_close'] = df['close']

            # Filter only required columns
            df = df[[c for c in required_cols if c in df.columns]]
            
            self.logger.info(f"Successfully fetched {len(df)} records for {symbol}")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()
