import fear_and_greed
import pandas as pd
from datetime import date
from src.crawlers.base import BaseCrawler

class FearGreedCrawler(BaseCrawler):
    def fetch_data(self, symbol: str = "fear_and_greed", start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """
        Fetch Fear & Greed Index from CNN via fear-and-greed package.
        """
        self.logger.info("Fetching Fear & Greed Index from CNN")

        try:
            result = fear_and_greed.get()
            value = round(result.value)
            status = result.description.lower()

            df = pd.DataFrame([{
                'name': 'fear_and_greed',
                'date': date.today(),
                'value': value,
                'status': status
            }])

            self.logger.info(f"Successfully fetched Fear & Greed: {value} ({status})")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching Fear & Greed: {e}")
            return pd.DataFrame()
