"""
Dashboard AI Agents package.

Exports:
    MarketAnalyst  — synchronous analyst for use in Streamlit pages
    build_context  — helper to assemble market data dict for the analyst
"""

from .market_analyst import MarketAnalyst, build_context

__all__ = ["MarketAnalyst", "build_context"]
