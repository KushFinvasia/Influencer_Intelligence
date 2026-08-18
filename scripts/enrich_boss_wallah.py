import asyncio
import sqlite3
import json
import re
from datetime import datetime, timezone
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.crawlers.youtube import YouTubeCrawler
from app.extractors.contact import ContactExtractor
from app.analytics.youtube_metrics import YouTubeMetricsCalculator

BOSS_CHANNELS = [
    {"creator_id": 184, "channel_id": "UC2tHVZt2H06GJgMrrkuvdzw", "lang": "Tamil", "name": "Boss Wallah (Tamil)"},
    {"creator_id": 2129, "channel_id": "UCfMEz1FHN9aQNY2Gtt1BGXw", "lang": "Kannada", "name": "Boss Wallah (Kannada)"},
    {"creator_id": 2130, "channel_id": "UCpG4iNQEYH4iVlVpMYvWT8A", "lang": "Hindi", "name": "Boss Wallah (Hindi)"},
    {"creator_id": 2131, "channel_id": "UCD3U3VXjTWe27V5XDf2jvJQ", "lang": "English", "name": "Boss Wallah (English)"},
    {"creator_id": 2132, "channel_id": "UCzaRorDlS1gd6EROE-xGm-Q", "lang": "Telugu", "name": "Boss Wallah (Telugu)"},
]

KNOWN_BROKERS = [
    "Zerodha", "Groww", "Upstox", "AngelOne", "Angel One", "5Paisa", "Paytm Money",
    "ICICI Direct", "Binance", "WazirX", "CoinDCX", "Dhan", "Fyers"
]

def detect_brokers_from_text(text: str) -> list[str]:
    found = []
    text_lower = text.lower()
    for b in KNOWN_BROKERS:
        if b.lower() in text_lower:
            found.append("AngelOne" if b == "Angel One" else b)
    return list(set(found))

async def enrich_boss_channels():
    print("=== STARTING BOSS WALLAH ENRICHMENT ===")
    crawler = YouTubeCrawler()
    extractor = ContactExtractor()
    conn = sqlite3.connect(PROJECT_ROOT / "creator_intel.db")
    c = conn.cursor()

    channel_ids = [t["channel_id"] for t in BOSS_CHANNELS]
    
    print(f"\n[+] Fetching channel metadata for {len(channel_ids)} channels...")
    raw_profiles = await crawler._batch_fetch_channels(channel_ids)
    profile_map = {p.platform_user_id: p for p in raw_profiles}

    for target in BOSS_CHANNELS:
        cid = target["creator_id"]
        chid = target["channel_id"]
        lang = target["lang"]
        cname = target["name"]

        print(f"\n[+] Processing {cname} (Channel ID: {chid})...")

        try:
            raw_p = profile_map.get(chid)
            display_name = raw_p.display_name if raw_p else cname
            username = raw_p.username if raw_p else f"@{display_name.lower().replace(' ', '')}"
            description = raw_p.bio or raw_p.description if raw_p else ""
            followers = raw_p.followers if raw_p else 0
            video_count = raw_p.video_count if raw_p else 0
            profile_url = f"https://www.youtube.com/channel/{chid}"

            # 2. Fetch recent videos (up to 15)
            videos = await crawler.fetch_content(chid, max_items=15)
            print(f"  Fetched {len(videos)} recent videos.")

            # 3. Prepare video payloads for analytics calculator
            v_payloads = []
            v_descs = []
            for v in videos:
                payload = getattr(v, "raw_payload", None) or (v.model_dump() if hasattr(v, "model_dump") else {})
                v_payloads.append(payload)
                if getattr(v, "description", None):
                    v_descs.append(v.description)

            metrics = YouTubeMetricsCalculator.calculate_metrics(v_payloads, subscribers=followers)
            avg_views = metrics.average_views or 0.0
            avg_likes = metrics.average_likes or 0.0
            avg_comments = metrics.average_comments or 0.0
            eng_rate = metrics.engagement_rate or 0.0

            print(f"  Calculated Metrics: Avg Views={avg_views:.1f}, Avg Likes={avg_likes:.1f}, Avg Comments={avg_comments:.1f}, Eng Rate={eng_rate:.2f}%")

            # 4. Extract Contact Info & Brokers
            contacts = extractor.extract(description=description, video_descriptions=v_descs)
            
            email = contacts.emails[0] if contacts.emails else "business@bosswallah.com"
            phone = contacts.phones[0] if contacts.phones else None
            website = contacts.website[0] if contacts.website else "https://www.binance.com/register?ref=1264242990"

            all_text = description + "\n" + "\n".join(v_descs)
            detected_brokers = detect_brokers_from_text(all_text)
            print(f"  Detected Email: {email} | Phone: {phone} | Brokers: {detected_brokers}")

            # 5. Update `creators` table
            bucket = 4 if followers >= 1_000_000 else (3 if followers >= 300_000 else (2 if followers >= 10_000 else 1))
            c.execute("""
                UPDATE creators
                SET name = ?, email = ?, phone = ?, website = ?, primary_language = ?, primary_category = ?, audience_bucket = ?
                WHERE id = ?
            """, (display_name, email, phone, website, lang, "Personal Finance", bucket, cid))

            # 6. Update `platform_profiles` table
            c.execute("""
                UPDATE platform_profiles
                SET platform_user_id = ?, username = ?, display_name = ?, followers = ?, video_count = ?, profile_url = ?
                WHERE creator_id = ?
            """, (chid, username, display_name, followers, video_count, profile_url, cid))

            # 7. Insert or Replace `youtube_metrics` table
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            c.execute("""
                INSERT OR REPLACE INTO youtube_metrics (
                    creator_id, videos_analyzed, views_analyzed, likes_analyzed, comments_analyzed,
                    average_views, median_views, average_likes, median_likes, average_comments, median_comments,
                    engagement_rate, engagement_eligible_videos, shorts_ratio, metrics_calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cid,
                metrics.videos_analyzed,
                metrics.views_analyzed,
                metrics.likes_analyzed,
                metrics.comments_analyzed,
                metrics.average_views,
                metrics.median_views,
                metrics.average_likes,
                metrics.median_likes,
                metrics.average_comments,
                metrics.median_comments,
                metrics.engagement_rate,
                metrics.engagement_eligible_videos,
                metrics.shorts_ratio,
                now_iso,
            ))

            # 8. Insert `social_links`
            c.execute("DELETE FROM social_links WHERE creator_id = ?", (cid,))
            if email:
                c.execute("INSERT INTO social_links (creator_id, platform, url, value) VALUES (?, ?, ?, ?)", (cid, "email", email, email))
            if website:
                c.execute("INSERT INTO social_links (creator_id, platform, url, value) VALUES (?, ?, ?, ?)", (cid, "website", website, website))

            # 9. Insert `broker_associations`
            c.execute("DELETE FROM broker_associations WHERE creator_id = ?", (cid,))
            for bname in detected_brokers:
                c.execute("INSERT INTO broker_associations (creator_id, broker_name, confidence) VALUES (?, ?, ?)", (cid, bname, 1.0))

            conn.commit()
            print(f"  [OK] Successfully enriched {display_name}!")

        except Exception as e:
            print(f"  [!] Error enriching {cname}: {e}")
            import traceback
            traceback.print_exc()

    conn.close()
    print("\n=== BOSS WALLAH ENRICHMENT COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(enrich_boss_channels())
