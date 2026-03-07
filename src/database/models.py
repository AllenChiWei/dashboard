from sqlalchemy import Column, Integer, String, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class MarketData(Base):
    __tablename__ = 'market_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    adjusted_close = Column(Float)
    source = Column(String(50), nullable=False)  # e.g., 'yahoo', 'twse'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Ensure unique records for symbol + date + source
    __table_args__ = (
        UniqueConstraint('symbol', 'date', 'source', name='uq_symbol_date_source'),
    )

    def __repr__(self):
        return f"<MarketData(symbol='{self.symbol}', date='{self.date}', close={self.close})>"

class SentimentData(Base):
    __tablename__ = 'sentiment_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, index=True)  # e.g., 'fear_and_greed', 'vix', 'tvix'
    date = Column(Date, nullable=False, index=True)
    value = Column(Float, nullable=False)
    status = Column(String(50))  # e.g., 'fear', 'neutral', 'greed', 'low', 'high', 'medium'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('name', 'date', name='uq_sentiment_name_date'),
    )

    def __repr__(self):
        return f"<SentimentData(name='{self.name}', date='{self.date}', value={self.value})>"

class VIXData(Base):
    __tablename__ = 'vix_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_name = Column(String(50), nullable=False, index=True)  # e.g., 'vix', 'tvix'
    date = Column(Date, nullable=False, index=True)
    value = Column(Float, nullable=False)
    status = Column(String(50))  # e.g., 'low', 'medium', 'high'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('index_name', 'date', name='uq_vix_name_date'),
    )

    def __repr__(self):
        return f"<VIXData(index_name='{self.index_name}', date='{self.date}', value={self.value})>"

class MarginData(Base):
    __tablename__ = 'margin_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String(50), nullable=False, index=True)  # e.g., 'taiwan'
    date = Column(Date, nullable=False, index=True)
    margin_maintenance_rate = Column(Float, nullable=False)  # Percentage
    short_margin_rate = Column(Float)  # Optional: short margin rate
    status = Column(String(50))  # e.g., 'low_risk', 'medium_risk', 'high_risk'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('market', 'date', name='uq_margin_market_date'),
    )

    def __repr__(self):
        return f"<MarginData(market='{self.market}', date='{self.date}', rate={self.margin_maintenance_rate})>"
