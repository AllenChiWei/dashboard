#!/usr/bin/env python
"""
Test script to verify all crawlers and database operations.
This script tests:
1. VIX Crawler (US VIX and Taiwan TVIX)
2. Taiwan Margin Crawler
3. Fear & Greed Crawler
4. Data storage in database
"""

import sys
from datetime import date, timedelta
from src.database.connection import db
from src.crawlers.vix_crawler import VIXCrawler
from src.crawlers.taiwan_margin_crawler import TaiwanMaginCrawler
from src.crawlers.fear_greed_crawler import FearGreedCrawler
from src.crawlers.yahoo_crawler import YahooCrawler
from src.etl.pipeline import (
    run_vix_etl, 
    run_margin_etl, 
    run_sentiment_etl,
    run_etl,
    run_all_etl
)
from src.utils.logger import setup_logger

logger = setup_logger("Test_Crawlers")

def test_vix_crawler():
    """Test VIX crawler"""
    logger.info("=" * 50)
    logger.info("Testing VIX Crawler...")
    logger.info("=" * 50)
    
    crawler = VIXCrawler()
    
    # Test US VIX
    logger.info("Testing US VIX...")
    df_vix = crawler.fetch_data('vix', 
                                start_date=date.today() - timedelta(days=7),
                                end_date=date.today())
    if not df_vix.empty:
        logger.info(f"✓ US VIX: Fetched {len(df_vix)} records")
        logger.info(f"  Latest: {df_vix.iloc[-1].to_dict()}")
    else:
        logger.warning("✗ No data fetched for US VIX")
    
    # Test Taiwan TVIX
    logger.info("\nTesting Taiwan TVIX...")
    df_tvix = crawler.fetch_data('tvix',
                                 start_date=date.today() - timedelta(days=7),
                                 end_date=date.today())
    if not df_tvix.empty:
        logger.info(f"✓ Taiwan TVIX: Fetched {len(df_tvix)} records")
        logger.info(f"  Latest: {df_tvix.iloc[-1].to_dict()}")
    else:
        logger.warning("✗ No data fetched for Taiwan TVIX")

def test_margin_crawler():
    """Test Taiwan margin crawler"""
    logger.info("\n" + "=" * 50)
    logger.info("Testing Taiwan Margin Crawler...")
    logger.info("=" * 50)
    
    crawler = TaiwanMaginCrawler()
    df = crawler.fetch_data(start_date=date.today() - timedelta(days=7),
                            end_date=date.today())
    if not df.empty:
        logger.info(f"✓ Taiwan Margin Rate: Fetched {len(df)} records")
        logger.info(f"  Latest: {df.iloc[-1].to_dict()}")
    else:
        logger.warning("✗ No data fetched for Taiwan margin rate")

def test_fear_greed_crawler():
    """Test Fear & Greed crawler"""
    logger.info("\n" + "=" * 50)
    logger.info("Testing Fear & Greed Crawler...")
    logger.info("=" * 50)
    
    crawler = FearGreedCrawler()
    df = crawler.fetch_data()
    if not df.empty:
        logger.info(f"✓ Fear & Greed: Fetched {len(df)} records")
        logger.info(f"  Data: {df.iloc[0].to_dict()}")
    else:
        logger.warning("✗ No data fetched for Fear & Greed")

def test_yahoo_crawler():
    """Test Yahoo Finance crawler"""
    logger.info("\n" + "=" * 50)
    logger.info("Testing Yahoo Finance Crawler...")
    logger.info("=" * 50)
    
    crawler = YahooCrawler()
    
    # Test with TSMC (2330.TW)
    logger.info("Testing with TSMC (2330.TW)...")
    df = crawler.fetch_data('2330.TW',
                            start_date=date.today() - timedelta(days=5),
                            end_date=date.today())
    if not df.empty:
        logger.info(f"✓ TSMC: Fetched {len(df)} records")
        logger.info(f"  Latest close: {df.iloc[-1]['close']}")
    else:
        logger.warning("✗ No data fetched for TSMC")

def test_database():
    """Test database connection and table creation"""
    logger.info("\n" + "=" * 50)
    logger.info("Testing Database Connection...")
    logger.info("=" * 50)
    
    try:
        db.init_db()
        logger.info("✓ Database tables created/verified successfully")
        
        # Check database connection
        session = db.get_session()
        session.execute("SELECT 1")
        session.close()
        logger.info("✓ Database connection successful")
        
    except Exception as e:
        logger.error(f"✗ Database error: {e}")
        return False
    
    return True

def test_etl_pipeline():
    """Test ETL pipeline"""
    logger.info("\n" + "=" * 50)
    logger.info("Testing ETL Pipelines...")
    logger.info("=" * 50)
    
    try:
        # Run individual ETLs
        logger.info("\n1. Running VIX ETL...")
        run_vix_etl(start_date=date.today() - timedelta(days=7),
                    end_date=date.today())
        logger.info("✓ VIX ETL completed")
        
        logger.info("\n2. Running Margin ETL...")
        run_margin_etl(start_date=date.today() - timedelta(days=7),
                       end_date=date.today())
        logger.info("✓ Margin ETL completed")
        
        logger.info("\n3. Running Fear & Greed ETL...")
        run_sentiment_etl()
        logger.info("✓ Fear & Greed ETL completed")
        
        logger.info("\n4. Running Market Data ETL...")
        run_etl(['2330.TW', '0050.TW'],
                start_date=date.today() - timedelta(days=5),
                end_date=date.today())
        logger.info("✓ Market Data ETL completed")
        
    except Exception as e:
        logger.error(f"✗ ETL pipeline error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    logger.info("\n╔═══════════════════════════════════════════════════════╗")
    logger.info("║  Financial Dashboard - Crawler & ETL Test Suite       ║")
    logger.info("╚═══════════════════════════════════════════════════════╝\n")
    
    # Run tests
    test_database()
    test_yahoo_crawler()
    test_vix_crawler()
    test_margin_crawler()
    test_fear_greed_crawler()
    test_etl_pipeline()
    
    logger.info("\n" + "=" * 50)
    logger.info("Test Suite Completed!")
    logger.info("=" * 50)
