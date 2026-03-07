import pandas as pd
from datetime import date, timedelta
from typing import List
from sqlalchemy.dialects.postgresql import insert
from src.database.connection import db
from src.database.models import MarketData, SentimentData, VIXData, MarginData
from src.crawlers.yahoo_crawler import YahooCrawler
from src.crawlers.fear_greed_crawler import FearGreedCrawler
from src.crawlers.vix_crawler import VIXCrawler
from src.crawlers.taiwan_margin_crawler import TaiwanMaginCrawler
from src.utils.logger import setup_logger

logger = setup_logger("ETL_Pipeline")

def upsert_market_data(session, df: pd.DataFrame, source: str):
    """
    Upsert data into MarketData table.
    """
    if df.empty:
        return

    # Prepare data for insertion
    records = []
    for _, row in df.iterrows():
        record = {
            'symbol': row['symbol'],
            'date': row['date'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row['volume'],
            'adjusted_close': row.get('adjusted_close'),
            'source': source
        }
        records.append(record)

    # Perform Upsert using PostgreSQL ON CONFLICT clause
    stmt = insert(MarketData).values(records)
    
    # Define update logic on conflict
    update_dict = {
        col: stmt.excluded[col]
        for col in ['open', 'high', 'low', 'close', 'volume', 'adjusted_close']
    }
    
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=['symbol', 'date', 'source'], # Constraint name or unique columns
        set_=update_dict
    )

    try:
        session.execute(upsert_stmt)
        session.commit()
        logger.info(f"Upserted {len(records)} records.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error during upsert: {e}")
        raise

def upsert_sentiment_data(session, df: pd.DataFrame):
    """
    Upsert data into SentimentData table.
    """
    if df.empty:
        return

    records = df.to_dict('records')
    stmt = insert(SentimentData).values(records)
    
    update_dict = {
        col: stmt.excluded[col]
        for col in ['value', 'status']
    }
    
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=['name', 'date'],
        set_=update_dict
    )

    try:
        session.execute(upsert_stmt)
        session.commit()
        logger.info(f"Upserted {len(records)} sentiment records.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error during sentiment upsert: {e}")
        raise

def upsert_vix_data(session, df: pd.DataFrame):
    """
    Upsert data into VIXData table.
    """
    if df.empty:
        return

    records = []
    for _, row in df.iterrows():
        record = {
            'index_name': row['name'],
            'date': row['date'],
            'value': row['value'],
            'status': row.get('status')
        }
        records.append(record)

    stmt = insert(VIXData).values(records)
    
    update_dict = {
        col: stmt.excluded[col]
        for col in ['value', 'status']
    }
    
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=['index_name', 'date'],
        set_=update_dict
    )

    try:
        session.execute(upsert_stmt)
        session.commit()
        logger.info(f"Upserted {len(records)} VIX records.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error during VIX upsert: {e}")
        raise

def upsert_margin_data(session, df: pd.DataFrame):
    """
    Upsert data into MarginData table.
    """
    if df.empty:
        return

    records = []
    for _, row in df.iterrows():
        record = {
            'market': 'taiwan',
            'date': row['date'],
            'margin_maintenance_rate': row['value'],
            'status': row.get('status')
        }
        records.append(record)

    stmt = insert(MarginData).values(records)
    
    update_dict = {
        col: stmt.excluded[col]
        for col in ['margin_maintenance_rate', 'status']
    }
    
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=['market', 'date'],
        set_=update_dict
    )

    try:
        session.execute(upsert_stmt)
        session.commit()
        logger.info(f"Upserted {len(records)} margin records.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error during margin upsert: {e}")
        raise


def run_etl(symbols: List[str], start_date: date = None, end_date: date = None):
    """
    Main ETL function for market data.
    """
    session = db.get_session()
    crawler = YahooCrawler()
    
    if start_date is None:
        start_date = date.today() - timedelta(days=365) # Default 1 year
    if end_date is None:
        end_date = date.today()

    try:
        # Initialize DB (Create tables if not exist)
        db.init_db()

        for symbol in symbols:
            logger.info(f"Processing {symbol}...")
            
            # Fetch Data
            df = crawler.fetch_data(symbol, start_date, end_date)
            
            if not df.empty:
                # Add symbol column if not present (yfinance might not include it in rows if passed single ticker)
                df['symbol'] = symbol
                # Ensure date is date object
                df['date'] = pd.to_datetime(df['date']).dt.date
                
                # Load Data
                upsert_market_data(session, df, source='yahoo')
            
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}")
    finally:
        session.close()

def run_sentiment_etl():
    """
    ETL for Fear & Greed sentiment index.
    """
    session = db.get_session()
    crawler = FearGreedCrawler()
    
    try:
        db.init_db()
        df = crawler.fetch_data()
        if not df.empty:
            upsert_sentiment_data(session, df)
    except Exception as e:
        logger.error(f"Sentiment ETL pipeline failed: {e}")
    finally:
        session.close()

def run_vix_etl(symbols: List[str] = None, start_date: date = None, end_date: date = None):
    """
    ETL for VIX indices (US VIX and Taiwan TVIX).
    
    Args:
        symbols: List of VIX symbols ('vix', 'tvix'). Defaults to both.
        start_date: Start date for historical data
        end_date: End date for historical data
    """
    if symbols is None:
        symbols = ['vix', 'tvix']
    
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()
    
    session = db.get_session()
    crawler = VIXCrawler()
    
    try:
        db.init_db()
        for symbol in symbols:
            logger.info(f"Processing {symbol.upper()}...")
            df = crawler.fetch_data(symbol, start_date, end_date)
            if not df.empty:
                upsert_vix_data(session, df)
    except Exception as e:
        logger.error(f"VIX ETL pipeline failed: {e}")
    finally:
        session.close()

def run_margin_etl(start_date: date = None, end_date: date = None):
    """
    ETL for Taiwan margin maintenance rate.
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()
    
    session = db.get_session()
    crawler = TaiwanMaginCrawler()
    
    try:
        db.init_db()
        df = crawler.fetch_data(start_date=start_date, end_date=end_date)
        if not df.empty:
            upsert_margin_data(session, df)
    except Exception as e:
        logger.error(f"Margin ETL pipeline failed: {e}")
    finally:
        session.close()

def run_all_etl(symbols: List[str] = None, start_date: date = None, end_date: date = None):
    """
    Run all ETL pipelines together.
    """
    logger.info("Starting all ETL pipelines...")
    
    # Default symbols if not provided
    if symbols is None:
        symbols = ["2330.TW", "0050.TW"]  # TSMC and 0050 ETF as examples
    
    # Run all ETLs
    run_etl(symbols, start_date, end_date)
    run_sentiment_etl()
    run_vix_etl(start_date=start_date, end_date=end_date)
    run_margin_etl(start_date=start_date, end_date=end_date)
    
    logger.info("All ETL pipelines completed!")

if __name__ == "__main__":
    # Example: Run all ETLs with default symbols
    TARGET_SYMBOLS = ["2330.TW", "0050.TW", "AAPL", "NVDA"]
    run_all_etl(TARGET_SYMBOLS)

