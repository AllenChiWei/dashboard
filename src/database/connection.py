from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import config
from src.database.models import Base
import logging

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance.engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
            cls._instance.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=cls._instance.engine
            )
        return cls._instance

    def init_db(self):
        """Create tables if they don't exist."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully.")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise

    def get_session(self):
        """Get a new session."""
        return self.SessionLocal()

# Global DB instance
db = DatabaseConnection()

def get_db():
    """Dependency for getting DB session."""
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()
