"""Utility for parsing and normalizing keyword configurations."""

from typing import Any

def parse_keywords(config: dict[str, Any]) -> list[dict[str, str]]:
    """
    Parse a dictionary of categorized keywords into a normalized, deduplicated list.
    
    Expected input format:
    {
        "generic_keywords": ["term1", "term2"],
        "language_keywords": ["term3"],
        ...
    }
    
    Returns:
    [
        {"term": "term1", "category": "generic"},
        {"term": "term2", "category": "generic"},
        {"term": "term3", "category": "language"}
    ]
    
    Deduplication preserves the first category encountered for a term.
    """
    normalized_terms = {}
    
    # Sort keys for deterministic behavior during deduplication
    for key in sorted(config.keys()):
        if key == "seed_usernames":
            continue
            
        value = config[key]
        if isinstance(value, list):
            # Extract category name, e.g., "generic_keywords" -> "generic"
            # If no underscore, use the whole key.
            category = key.split("_")[0] if "_" in key else key
            
            for term in value:
                if not isinstance(term, str):
                    continue
                term_clean = term.strip()
                if not term_clean:
                    continue
                    
                # Deterministic deduplication based on exact term string
                if term_clean not in normalized_terms:
                    normalized_terms[term_clean] = {
                        "term": term_clean,
                        "category": category
                    }
                    
    return list(normalized_terms.values())
