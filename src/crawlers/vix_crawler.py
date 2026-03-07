import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from src.crawlers.base import BaseCrawler

class VIXCrawler(BaseCrawler):
    """
    Fetch VIX indices for both US and Taiwan markets.
    """
    
    # VIX symbols mapping
    VIX_SYMBOLS = {
        'vix': '^VIX',        # US VIX Index
        'tvix': '0050.TW',    # Taiwan VIX Index (using 0050 as proxy for now)
    }
    
    def fetch_data(self, symbol: str = "vix", start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """
        Fetch VIX data for specified symbol (vix or tvix).
        
        Args:
            symbol: 'vix' for US VIX, 'tvix' for Taiwan VIX
            start_date: Start date for historical data
            end_date: End date for historical data
        
        Returns:
            DataFrame with columns: ['date', 'name', 'value', 'status']
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()
        
        symbol_lower = symbol.lower()
        if symbol_lower not in self.VIX_SYMBOLS:
            self.logger.error(f"Unknown VIX symbol: {symbol}")
            return pd.DataFrame()
        
        yahoo_symbol = self.VIX_SYMBOLS[symbol_lower]
        self.logger.info(f"Fetching {symbol.upper()} data from Yahoo Finance")
        
        try:
            # Fetch data
            data = yf.download(yahoo_symbol, start=start_date, end=end_date, progress=False)
            
            if data.empty:
                self.logger.warning(f"No data retrieved for {yahoo_symbol}")
                return pd.DataFrame()
            
            # Reset index to make date a column
            data = data.reset_index()
            data.rename(columns={'Date': 'date'}, inplace=True)
            
            # Use Close price as the VIX value
            df = pd.DataFrame({
                'name': symbol_lower,
                'date': pd.to_datetime(data['date']).dt.date,
                'value': data['Close'].round(2),
                'status': self._get_status(data['Close'].values, symbol_lower)
            })
            
            self.logger.info(f"Successfully fetched {len(df)} records for {symbol.upper()}")
            return df
        
        except Exception as e:
            self.logger.error(f"Error fetching {symbol.upper()}: {e}")
            return pd.DataFrame()
    
    def _get_status(self, values, symbol: str) -> pd.Series:
        """
        Determine status based on VIX levels.
        For VIX/TVIX: Low (<20) = 'low', Medium (20-30) = 'medium', High (>30) = 'high'
        """
        avg_value = values.mean()
        
        if avg_value < 20:
            status = 'low'
        elif avg_value < 30:
            status = 'medium'
        else:
            status = 'high'
        
        return pd.Series([status] * len(values), index=range(len(values)))
