import pytest
from app.utils.keyword_parser import parse_keywords

def test_parse_keywords_basic():
    config = {
        "generic_keywords": ["stock market", "trading"],
        "broker_keywords": ["zerodha", "upstox"],
    }
    result = parse_keywords(config)
    assert len(result) == 4
    assert {"term": "stock market", "category": "generic"} in result
    assert {"term": "trading", "category": "generic"} in result
    assert {"term": "zerodha", "category": "broker"} in result
    assert {"term": "upstox", "category": "broker"} in result

def test_parse_keywords_deduplication():
    config = {
        "generic_keywords": ["stock market", "trading"],
        "language_keywords": ["stock market"],  # Duplicate
    }
    result = parse_keywords(config)
    assert len(result) == 2
    
    # "generic_keywords" comes before "language_keywords" alphabetically,
    # so the deterministic sort will process generic first and keep it.
    assert {"term": "stock market", "category": "generic"} in result
    assert {"term": "trading", "category": "generic"} in result

def test_parse_keywords_skips_seed_usernames():
    config = {
        "generic_keywords": ["trading"],
        "seed_usernames": ["user1", "user2"],
    }
    result = parse_keywords(config)
    assert len(result) == 1
    assert result[0] == {"term": "trading", "category": "generic"}

def test_parse_keywords_empty_or_invalid():
    config = {
        "generic_keywords": [],
        "language_keywords": ["", "   ", None, 123, "valid"],
    }
    result = parse_keywords(config)
    assert len(result) == 1
    assert result[0] == {"term": "valid", "category": "language"}

def test_parse_keywords_no_underscore_category():
    config = {
        "custom": ["keyword1"],
    }
    result = parse_keywords(config)
    assert len(result) == 1
    assert result[0] == {"term": "keyword1", "category": "custom"}
