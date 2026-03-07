from abc import ABC, abstractmethod
import pandas as pd
from datetime import date
from src.utils.logger import setup_logger

class BaseCrawler(ABC):
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)

    @abstractmethod
    def fetch_data(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Fetch market data for a given symbol and date range.
        Must return a DataFrame with columns:
        ['date', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close']
        """
        pass
