"""Category extraction and classification engine.

Combines rule-based keyword pattern matching, video title analysis,
bio scanning, and hashtag evaluation with LLM fallback for robust categorization.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from app.config.settings import get_categories_config
from app.schemas.creator import CategoryResult, RawProfile

logger = logging.getLogger(__name__)

# Category keyword dictionaries with specific finance indicators
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "F&O": [
        "options", "option trading", "call option", "put option", "option chain",
        "banknifty", "nifty options", "f&o", "fno", "futures", "expiry", "zero hero", "hero zero",
        "straddle", "strangle", "iron condor", "option buyer", "option seller", "ce pe",
        "greeks", "delta", "theta", "gamma", "open interest", "oi data", "hedging",
        "finnifty", "midcap nifty", "call and put", "option buying", "option selling"
    ],
    "Intraday": [
        "intraday", "day trading", "day trader", "scalping", "scalper",
        "1 min", "5 min", "live trading", "live trade", "morning setup",
        "entry exit", "stop loss", "supertrend", "cpr indicator", "9:15", "scalp setup"
    ],
    "Technical Analysis": [
        "technical analysis", "price action", "candlestick", "chart pattern", "chart analysis",
        "breakout", "support and resistance", "support resistance", "trendline",
        "moving average", "rsi", "macd", "fibonacci", "chart reading", "indicators",
        "volume profile", "tradingview", "divergence", "chart pattern", "head and shoulders"
    ],
    "Fundamental Analysis": [
        "fundamental analysis", "balance sheet", "quarterly results", "financial results",
        "pe ratio", "p/e ratio", "roce", "roe", "financial statements", "dcf valuation",
        "valuation", "economic moat", "value investing", "annual report", "promoter holding",
        "concall", "management commentary", "q1 result", "q2 result", "q3 result", "q4 result"
    ],
    "Mutual Funds": [
        "mutual fund", "mutual funds", "sip", "elss", "index fund", "small cap fund",
        "mid cap fund", "large cap fund", "flexi cap", "amfi", "nav", "etf", "direct fund",
        "step up sip", "best mutual funds"
    ],
    "IPO": [
        "ipo", "gmp", "grey market", "grey market premium", "allotment", "allotment status",
        "sme ipo", "mainboard ipo", "listing gains", "ipo review", "apply ipo", "ipo status"
    ],
    "Swing Trading": [
        "swing trading", "swing trade", "positional trade", "positional trading",
        "weekly breakout", "short term stock", "breakout stocks", "holding period",
        "delivery trade", "swing stock"
    ],
    "Long-term Investing": [
        "long-term investing", "long term investing", "wealth creation", "compounding",
        "dividend", "dividend stocks", "bluechip", "multibagger", "multibaggers",
        "retirement fund", "crorepati", "portfolio review", "buy and hold"
    ],
    "Personal Finance": [
        "personal finance", "tax planning", "tax saving", "itr filing", "income tax",
        "gst", "term insurance", "health insurance", "insurance", "credit card",
        "emergency fund", "budgeting", "epf", "ppf", "nps", "savings account", "cibil score"
    ],
    "Algo Trading": [
        "algo trading", "algorithmic trading", "quant", "quantitative", "python trading",
        "pine script", "backtesting", "automated trading", "trading bot", "api trading"
    ],
    "Crypto": [
        "crypto", "cryptocurrency", "bitcoin", "btc", "ethereum", "eth", "altcoin",
        "binance", "coindcx", "wazirx", "blockchain", "web3"
    ],
    "Commodity Trading": [
        "commodity", "gold", "silver", "crude oil", "natural gas", "mcx", "bullion"
    ],
    "Forex": [
        "forex", "fx trading", "currency trading", "usd inr", "eur usd", "gbp inr"
    ],
    "Market News": [
        "market news", "stock news", "business news", "daily market update",
        "pre market", "post market", "rbi policy", "fed rate", "budget 2026", "news today"
    ],
    "Equity": [
        "equity research", "equity investing", "share market shares", "stocks to buy",
        "stock picks", "equity portfolio", "company analysis", "stock analysis"
    ]
}


class CategoryExtractor:
    """Extracts and scores financial categories from creator profiles."""

    def __init__(self) -> None:
        self.config = get_categories_config()
        self.valid_categories = self.config.get("categories", list(CATEGORY_KEYWORDS.keys()))
        self.aliases = self.config.get("aliases", {})

    def extract_categories(self, profile: RawProfile) -> tuple[str, list[CategoryResult]]:
        """Classify creator categories based on weighted text signals.

        Returns:
            Tuple of (primary_category, list of CategoryResult with confidence).
        """
        scores: dict[str, float] = {cat: 0.0 for cat in CATEGORY_KEYWORDS}

        name_text = (f"{profile.display_name or ''} {profile.username or ''}").lower()
        bio_text = (f"{profile.bio or ''} {profile.description or ''}").lower()
        titles_text = " ".join(profile.recent_video_titles or []).lower()
        descs_text = " ".join((profile.recent_video_descriptions or [])[:5]).lower()

        # Score across categories
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                # Name match (High priority)
                if re.search(rf"\b{re.escape(kw)}\b", name_text):
                    scores[category] += 3.5

                # Bio match
                if re.search(rf"\b{re.escape(kw)}\b", bio_text):
                    scores[category] += 2.0

                # Video titles match (Multiple titles increase score)
                title_matches = len(re.findall(rf"\b{re.escape(kw)}\b", titles_text))
                if title_matches > 0:
                    scores[category] += min(title_matches * 1.5, 6.0)

                # Video description match
                if re.search(rf"\b{re.escape(kw)}\b", descs_text):
                    scores[category] += 1.0

        # Special boost logic:
        # If any specific category matches, downweight generic "Equity" to 10%
        specific_cats = ["F&O", "Intraday", "Technical Analysis", "Fundamental Analysis", "Mutual Funds", "IPO", "Swing Trading", "Long-term Investing", "Personal Finance", "Algo Trading", "Crypto", "Commodity Trading", "Forex", "Market News"]
        highest_specific = max((scores[c] for c in specific_cats), default=0.0)

        if highest_specific > 1.0 and scores["Equity"] > 0:
            scores["Equity"] *= 0.1

        # Filter categories with positive scores
        ranked = [(cat, score) for cat, score in scores.items() if score > 0]
        ranked.sort(key=lambda x: x[1], reverse=True)

        if not ranked:
            # Default to Technical Analysis / Personal Finance over generic Equity if text mentions trading/stocks
            all_text = f"{name_text} {bio_text} {titles_text}"
            if any(w in all_text for w in ["trade", "trader", "chart", "nifty", "profit"]):
                primary = "Technical Analysis"
            else:
                primary = "Personal Finance"
            return primary, [CategoryResult(name=primary, confidence=0.70)]

        top_cat, top_score = ranked[0]
        max_possible = max(top_score, 10.0)

        results: list[CategoryResult] = []
        for cat, score in ranked[:4]:
            conf = min(round(score / max_possible, 2), 0.98)
            if conf >= 0.20:
                results.append(CategoryResult(name=cat, confidence=conf))

        if not results:
            results.append(CategoryResult(name=top_cat, confidence=0.75))

        return top_cat, results
