import requests
import pandas as pd
from datetime import date, timedelta
from bs4 import BeautifulSoup
from src.crawlers.base import BaseCrawler

class TaiwanMaginCrawler(BaseCrawler):
    """
    Fetch Taiwan stock margin maintenance rate from Taiwan Stock Exchange (TWSE).
    Data source: https://www.twse.com.tw/
    """
    
    # TWSE API endpoint for margin information
    TWSE_MARGIN_API = "https://www.twse.com.tw/exchangeReport/MI_5MINS"
    
    def fetch_data(self, symbol: str = "margin_rate", start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """
        Fetch Taiwan stock margin maintenance rate.
        
        Args:
            symbol: Fixed to 'margin_rate'
            start_date: Start date for historical data
            end_date: End date for historical data
        
        Returns:
            DataFrame with columns: ['date', 'name', 'value', 'status']
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()
        
        self.logger.info("Fetching Taiwan margin maintenance rate from TWSE")
        
        try:
            # Fetch latest margin data
            params = {
                'response': 'json',
                'date': date.today().strftime('%Y%m%d')
            }
            
            response = requests.get(self.TWSE_MARGIN_API, params=params, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                self.logger.warning(f"TWSE API returned status code: {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            
            if 'data' not in data or not data['data']:
                self.logger.warning("No margin data found in response")
                return pd.DataFrame()
            
            # Parse the latest data point
            latest_data = data['data'][-1] if data['data'] else None
            
            if not latest_data:
                return pd.DataFrame()
            
            # Extract margin maintenance rate (通常是第2或3個欄位)
            # TWSE format: [date, time, 融資餘額, 融資限額, 融資維持率, 融券餘額, 融券限額, 融券維持率]
            margin_rate = float(latest_data[4].replace('%', '')) if len(latest_data) > 4 else None
            
            if margin_rate is None:
                self.logger.warning("Could not extract margin rate from TWSE data")
                return pd.DataFrame()
            
            df = pd.DataFrame([{
                'name': 'taiwan_margin_rate',
                'date': date.today(),
                'value': margin_rate,
                'status': self._get_status(margin_rate)
            }])
            
            self.logger.info(f"Successfully fetched Taiwan margin rate: {margin_rate}%")
            return df
        
        except requests.RequestException as e:
            self.logger.error(f"Error fetching from TWSE: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error parsing Taiwan margin data: {e}")
            return pd.DataFrame()
    
    def _get_status(self, margin_rate: float) -> str:
        """
        Determine status based on margin rate level.
        Higher rate = more risky
        <200% = 'low_risk', 200-300% = 'medium_risk', >300% = 'high_risk'
        """
        if margin_rate < 200:
            return 'low_risk'
        elif margin_rate < 300:
            return 'medium_risk'
        else:
            return 'high_risk'
