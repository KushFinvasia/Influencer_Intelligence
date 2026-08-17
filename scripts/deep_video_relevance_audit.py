"""
Deep Video-Based Relevance Auditor & Purge Script
=================================================
Audits every creator in creator_intel.db by analyzing their ACTUAL recent video titles.

Rules:
1. Fetches recent video titles for every creator (using RSS feed for creators missing video titles).
2. Calculates the count and percentage of videos explicitly covering Stock Market, Trading, Investing, Mutual Funds, Equity Research, F&O, Technical Analysis, etc.
3. If a channel has ZERO stock market videos or <15% financial content ratio (e.g. Quick Support coding channel, Switch movie/lifestyle channel, tech/gaming channels), flags them as is_relevant = False and PURGES them from creator_intel.db.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "creator_intel.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("deep_video_audit.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Strict Stock Market / Trading Keywords
STOCK_MARKET_KEYWORDS = [
    "stock", "share", "market", "trading", "trader", "invest", "investor", "investing",
    "nifty", "sensex", "banknifty", "finifty", "f&o", "futures", "options", "call option", "put option",
    "intraday", "swing trade", "demat", "portfolio", "ipo", "equity", "mutual fund", "sip",
    "zerodha", "groww", "angel one", "upstox", "dhan", "fyers", "motilal oswal", "icici direct",
    "technical analysis", "fundamental analysis", "candlestick", "chart pattern", "price action",
    "breakout", "stoploss", "target", "multibagger", "penny stock", "dividend", "yield",
    "bullish", "bearish", "crypto", "bitcoin", "forex", "algo trading", "smallcase",
    "sebi", "bse", "nse", "tax saving", "itr", "financial planning", "wealth management",
    "share market", "stock market", "share bazar", "share bazaar"
]

# Non-Stockmarket / Irrelevant Channel Keywords
NON_STOCK_KEYWORDS = [
    "php", "javascript", "java", "c++", "html", "css", "python tutorial", "coding", "web dev",
    "unboxing", "smartphone", "mobile review", "gadget", "gaming", "pubg", "free fire", "bgmi", "gta",
    "movie review", "bollywood", "song", "dance", "comedy", "roast", "prank", "vlog", "travel vlog",
    "dr. nidhi jha", "intimacy", "orgasm", "relationship", "love triangle", "astrologer",
    "earn money app", "refer and earn app", "paytm cash", "looting", "gameplay"
]


def fetch_rss_videos(channel_id: str) -> list[str]:
    """Fetch recent 15 video titles from YouTube RSS feed without API quota."""
    if not channel_id:
        return []
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            titles = []
            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                if title_elem is not None and title_elem.text:
                    titles.append(title_elem.text)
            return titles
    except Exception:
        return []


def evaluate_channel_relevance(name: str, bio: str, desc: str, video_titles: list[str]) -> tuple[bool, float, str]:
    """Evaluate channel stock market relevance based on actual video titles & description."""
    combined_desc = f"{name or ''} {bio or ''} {desc or ''}".lower()
    
    total_vids = len(video_titles)
    stock_vid_count = 0
    non_stock_vid_count = 0

    if total_vids > 0:
        for t in video_titles:
            t_lower = t.lower()
            if any(kw in t_lower for kw in STOCK_MARKET_KEYWORDS):
                stock_vid_count += 1
            if any(kw in t_lower for kw in NON_STOCK_KEYWORDS):
                non_stock_vid_count += 1

        ratio = stock_vid_count / total_vids

        # If channel has 0 stock market videos out of analyzed videos -> NOT RELEVANT
        if stock_vid_count == 0 and total_vids >= 3:
            return False, 0.95, f"0/{total_vids} videos related to stock market"
        
        # If stock market video ratio is below 15% -> NOT RELEVANT
        if ratio < 0.15 and total_vids >= 5:
            return False, 0.90, f"Only {stock_vid_count}/{total_vids} ({ratio*100:.1f}%) stock market videos"

        # If non-stock keywords dominate and stock vids <= 1 -> NOT RELEVANT
        if non_stock_vid_count >= 3 and stock_vid_count <= 1:
            return False, 0.90, f"Dominated by non-stock content ({non_stock_vid_count} non-stock vs {stock_vid_count} stock)"

        # High ratio of stock market videos -> RELEVANT
        if ratio >= 0.20 or stock_vid_count >= 2:
            return True, min(0.95, 0.70 + ratio * 0.3), f"{stock_vid_count}/{total_vids} ({ratio*100:.1f}%) stock market videos"

    # Fallback to description analysis if video count < 3
    stock_hits = sum(1 for kw in STOCK_MARKET_KEYWORDS if kw in combined_desc)
    non_stock_hits = sum(1 for kw in NON_STOCK_KEYWORDS if kw in combined_desc)

    if stock_hits >= 2 and non_stock_hits == 0:
        return True, 0.85, f"Description has {stock_hits} stock market keywords"
    elif non_stock_hits >= 2 and stock_hits == 0:
        return False, 0.85, f"Description has {non_stock_hits} non-stock keywords"

    # Default for remaining
    return True, 0.60, "Default pass"


def run_video_audit():
    logger.info("Starting Deep Video-Based Relevance Audit across all creators...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT c.id, c.name, pp.platform_user_id, pp.bio, pp.description, pp.raw_data
        FROM creators c
        LEFT JOIN platform_profiles pp ON pp.creator_id = c.id
    """)

    rows = c.fetchall()
    total = len(rows)
    logger.info("Total creators to audit: %d", total)

    to_purge = []
    audited = 0

    for r in rows:
        cid, name, channel_id, bio, desc, rd = r
        video_titles = []

        # Extract stored video titles if available
        if rd:
            try:
                data = json.loads(rd) if isinstance(rd, str) else rd
                v_list = data.get("videos", [])
                for v in v_list:
                    if isinstance(v, dict) and v.get("title"):
                        video_titles.append(v.get("title"))
            except Exception:
                pass

        # If no stored video titles, fetch via RSS feed
        if not video_titles and channel_id and channel_id.startswith("UC"):
            video_titles = fetch_rss_videos(channel_id)

        is_rel, conf, reason = evaluate_channel_relevance(name, bio, desc, video_titles)

        if not is_rel:
            to_purge.append((cid, name, reason))
            safe_name = (name or "").encode('ascii', 'ignore').decode('ascii')
            logger.info("FLAGGED FOR PURGE #%d '%s': %s", cid, safe_name, reason)

        # Update flags in DB
        c.execute("""
            UPDATE creators 
            SET is_relevant = ?, relevance_confidence = ?
            WHERE id = ?
        """, (1 if is_rel else 0, conf, cid))

        audited += 1
        if audited % 100 == 0:
            conn.commit()
            logger.info("Audited %d/%d creators...", audited, total)

    conn.commit()

    logger.info("==========================================")
    logger.info("DEEP VIDEO AUDIT COMPLETE")
    logger.info("Total Audited: %d", total)
    logger.info("Verified Relevant Stock Market Creators: %d", total - len(to_purge))
    logger.info("Irrelevant / Non-Stockmarket Channels Flagged: %d", len(to_purge))
    logger.info("==========================================")

    if to_purge:
        logger.info("Purging %d non-stockmarket creators...", len(to_purge))
        for item in to_purge:
            c.execute("DELETE FROM creators WHERE id = ?", (item[0],))
        conn.commit()
        logger.info("Purged %d non-stockmarket creators from DB!", len(to_purge))

    c.execute("SELECT COUNT(*) FROM creators WHERE is_relevant = 1")
    final_total = c.fetchone()[0]
    logger.info("FINAL VERIFIED CLEAN STOCK MARKET CREATORS: %d", final_total)

    conn.close()


if __name__ == "__main__":
    run_video_audit()
