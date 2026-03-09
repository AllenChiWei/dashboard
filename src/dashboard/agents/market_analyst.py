"""
MarketAnalyst — synchronous Claude API wrapper suitable for Streamlit.

Uses the anthropic SDK directly (no Agent SDK) because:
  - Streamlit runs in a synchronous context
  - We don't need file/shell tools for market commentary
  - Streaming via st.write_stream works best with a generator

Usage:
    analyst = MarketAnalyst()
    # One-shot auto analysis (returns full text)
    text = analyst.analyze(context)
    # Streaming generator for st.write_stream
    for chunk in analyst.stream(messages):
        ...
"""

import os
from typing import Generator

import anthropic

from .config import MODEL, MAX_TOKENS, THINKING, get_system_prompt, build_auto_prompt


def build_context(
    vix_now: dict | None,
    tw_vix: dict | None,
    fg: dict | None,
    margin_result: dict | None,
    fear_score: float | None,
    fear_label: str = "",
) -> dict:
    """
    Assemble a flat context dict from raw indicator data.
    All values are formatted as strings ready for prompt injection.
    """
    return {
        "vix":        f"{vix_now['value']:.2f}" if vix_now else "N/A",
        "vix_chg":    f"{vix_now['change']:+.2f} ({vix_now['pct']:+.2f}%)" if vix_now else "N/A",
        "tw_vix":     f"{tw_vix['value']:.2f}" if tw_vix else "N/A",
        "tw_vix_chg": f"{tw_vix['change']:+.2f}" if tw_vix else "N/A",
        "fg":         f"{fg['value']:.0f}" if fg else "N/A",
        "fg_desc":    fg["description"] if fg else "",
        "margin":     f"{margin_result['ratio']:.2f}" if margin_result else "N/A",
        "fear_score": f"{fear_score:.1f}" if fear_score is not None else "N/A",
        "fear_label": fear_label,
    }


class MarketAnalyst:
    """Thin wrapper around the Anthropic Messages API for market commentary."""

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. "
                "Add it to your .env file or environment variables."
            )
        self.client = anthropic.Anthropic(api_key=key)
        self.model = MODEL
        self.system = get_system_prompt()

    # ── Auto analysis (blocking, returns full text) ───────────────────────────
    def analyze(self, context: dict) -> str:
        """
        Run a one-shot market analysis from the context dict.
        Returns the full text response (non-streaming).
        """
        prompt = build_auto_prompt(context)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            thinking=THINKING,
            system=self.system,
            messages=[{"role": "user", "content": prompt}],
        )
        return next(
            (b.text for b in response.content if b.type == "text"), ""
        )

    # ── Streaming chat (generator for st.write_stream) ────────────────────────
    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """
        Stream a chat response.
        `messages` is a list of {"role": "user"|"assistant", "content": str}.
        Yields text chunks as they arrive.
        """
        with self.client.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            thinking=THINKING,
            system=self.system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    # ── Context summary for chat system injection ─────────────────────────────
    @staticmethod
    def context_block(context: dict) -> str:
        """Return a compact context string to prepend to the first user message."""
        return (
            f"[當前市場數據] "
            f"US VIX={context.get('vix', 'N/A')} "
            f"TW VIX={context.get('tw_vix', 'N/A')} "
            f"F&G={context.get('fg', 'N/A')}({context.get('fg_desc', '')}) "
            f"融資維持率={context.get('margin', 'N/A')}% "
            f"恐慌指數={context.get('fear_score', 'N/A')}/100({context.get('fear_label', '')})\n\n"
        )
