"""LLM prompt templates for creator classification and relevance gating.

Each prompt constrains the LLM to return ONLY values from the config files.
All prompts require structured JSON output with reasoning and evidence.
"""

from __future__ import annotations

from app.config.settings import (
    get_brokers_config,
    get_categories_config,
    get_creator_types_config,
    get_languages_config,
)


def build_relevance_prompt() -> str:
    """Build system prompt for financial domain relevance gating."""
    return """You are a strict domain auditor for an Indian Financial Influencer & Stock Market Creator database.

Your task is to determine whether the given channel/profile is GENUINELY a dedicated Financial / Stock Market / Trading / Investing / Personal Finance creator.

TARGET CRITERIA (is_financial_creator = true):
- Stock market trading (F&O, Intraday, Options, Swing)
- Long-term investing, Equity research, Multibaggers, IPO analysis
- Personal finance, Mutual funds, SIP, Tax saving, Budgeting
- Crypto / Forex trading
- Financial education, Demat tutorials, Broker reviews

NON-FINANCIAL / IRRELEVANT (is_financial_creator = false):
- General mainstream news media, national broadcasting networks (e.g. The Lallantop, Aaj Tak, NDTV, ANI News, ABP News, Zee News, News18)
- Political commentary / general socio-economic debates (e.g. Dhruv Rathee, political vloggers)
- General motivation / life coaching (unless specifically financial)
- Tech reviews, gadget unboxing, coding/software tutorials
- General education / science animation (e.g. TED-Ed, general UPSC/IAS coaching)
- Comedy, movies, Bollywood, cricket, gaming, entertainment, daily vlogs
- Channels that only occasionally mention inflation, budget, or general economy among 90% non-financial news.

Return ONLY valid JSON in this exact format:
{
  "is_financial_creator": false,
  "relevance_score": 0.15,
  "detected_genre": "general_news",
  "reasoning": "Channel is a mainstream general news agency covering national politics and current affairs, not a dedicated financial creator."
}"""


def build_category_prompt() -> str:
    """Build system prompt for category classification."""
    config = get_categories_config()
    categories = config.get("categories", [])
    categories_list = ", ".join(categories)

    return f"""You are a classification expert for Indian stock market content creators.

Analyze the provided profile information and classify the creator into content categories.

ALLOWED CATEGORIES (you MUST only use these):
{categories_list}

RULES:
1. Choose a primary_category (the dominant content focus).
2. List ALL relevant categories with estimated content_percentage (must sum to ~100).
3. Provide a confidence score (0.0 to 1.0) for each category.
4. Include reasoning explaining your classification decision.
5. Include evidence — specific phrases, titles, or patterns that support your decision.

Return ONLY valid JSON in this exact format:
{{
  "primary_category": "F&O",
  "categories": [
    {{"name": "F&O", "content_percentage": 60, "confidence": 0.92}},
    {{"name": "Equity", "content_percentage": 25, "confidence": 0.85}},
    {{"name": "IPO", "content_percentage": 15, "confidence": 0.78}}
  ],
  "reasoning": "Your explanation here",
  "evidence": ["specific phrase 1", "video title pattern"]
}}"""


def build_language_prompt() -> str:
    """Build system prompt for language detection."""
    config = get_languages_config()
    languages = config.get("languages", [])
    languages_list = ", ".join(languages)

    return f"""You are a language detection expert for Indian content creators.

Analyze the provided profile information and determine the primary language.

ALLOWED LANGUAGES (you MUST only use these):
{languages_list}

RULES:
1. Determine the primary language used in the content.
2. If the creator uses a mix (e.g., Hindi + English), use "Mixed".
3. Provide a confidence score (0.0 to 1.0).
4. Include reasoning explaining your detection.
5. Use "Mixed" only when there is genuinely a significant mix (not just occasional English words in Hindi).

Return ONLY valid JSON in this exact format:
{{
  "primary_language": "Hindi",
  "confidence": 0.95,
  "reasoning": "All video titles are in Hindi, bio uses Devanagari script"
}}"""


def build_creator_type_prompt() -> str:
    """Build system prompt for creator type classification."""
    config = get_creator_types_config()
    creator_types = config.get("creator_types", [])
    types_list = ", ".join(creator_types)

    return f"""You are an expert at classifying Indian stock market content creators.

Analyze the provided profile information and determine the creator type.

ALLOWED CREATOR TYPES (you MUST only use these):
{types_list}

DEFINITIONS:
- Educator: Teaches concepts, provides courses, tutorials
- Trader: Actively trades and shares trades/setups
- Investor: Focuses on long-term investing, portfolio building
- Analyst: Provides market analysis, research reports, stock picks
- News: Covers dedicated financial/market news, earnings, quarterly results
- Personal Finance: Covers budgeting, savings, insurance, tax planning
- Broker Representative: Works for/promotes a specific broker
- Influencer: General stock market content creator, lifestyle focus
- Community Builder: Runs communities, groups, challenges

RULES:
1. Choose exactly ONE creator type.
2. Provide a confidence score (0.0 to 1.0).
3. Include reasoning.

Return ONLY valid JSON in this exact format:
{{
  "creator_type": "Educator",
  "confidence": 0.88,
  "reasoning": "Profile focuses on teaching trading concepts with structured courses"
}}"""


def build_broker_verification_prompt() -> str:
    """Build system prompt for broker verification (only called if rule-based detection is uncertain)."""
    config = get_brokers_config()
    broker_names = [b["name"] for b in config.get("brokers", [])]
    brokers_list = ", ".join(broker_names)

    return f"""You are an expert at identifying broker associations for Indian stock market content creators.

Analyze the provided profile information and determine if the creator is associated with any broker.

ALLOWED BROKERS (you MUST only use these):
{brokers_list}

RELATIONSHIP TYPES:
- affiliate: Has a referral/affiliate link
- referral: Promotes referral codes
- brand_ambassador: Official brand ambassador
- sponsored: Creates sponsored content for the broker
- past_partner: Was previously associated
- mention_only: Just mentions the broker casually

RULES:
1. If you identify a broker association, specify the broker name exactly as listed above.
2. Determine the relationship type.
3. If no broker association is found, set broker_name to "none".
4. Provide a confidence score (0.0 to 1.0).
5. Include reasoning and evidence.

Return ONLY valid JSON in this exact format:
{{
  "broker_name": "Zerodha",
  "relationship_type": "affiliate",
  "confidence": 0.88,
  "reasoning": "Bio contains Zerodha referral link and multiple videos are Zerodha tutorials",
  "evidence": ["referral link in bio", "Zerodha tutorial series"]
}}"""
