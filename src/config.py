import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    """Read from st.secrets (Streamlit Cloud) first, then fall back to env vars."""
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)


class Config:
    POSTGRES_USER = _get("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = _get("POSTGRES_PASSWORD", "password")
    POSTGRES_DB = _get("POSTGRES_DB", "financial_db")
    POSTGRES_HOST = _get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = _get("POSTGRES_PORT", "5432")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    LOG_LEVEL = _get("LOG_LEVEL", "INFO")
    FINLAB_API_KEY = _get("FINLAB_API_KEY", "")
    ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY", "")


config = Config()
