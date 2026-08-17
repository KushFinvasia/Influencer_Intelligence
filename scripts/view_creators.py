"""View all discovered creators in a consolidated single table with custom columns.

Columns:
Platform | Name | Followers | Bucket | Email | Phone | Category | Language | Broker | Website | Social Media Handles
"""

import csv
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.analytics.content_format import (
    classify_instagram_format,
    classify_youtube_format,
)

DB_PATH = PROJECT_ROOT / "creator_intel.db"
EXPORTS_DIR = PROJECT_ROOT / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

CSV_FILE = EXPORTS_DIR / "creators_table.csv"
HTML_FILE = EXPORTS_DIR / "creators_table.html"


def format_metric(val: float | int | None) -> str:
    """Format performance numbers (e.g. 1.2M, 320K, 272)."""
    if val is None:
        return "-"
    if val >= 1_000_000:
        s = f"{val / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{s}M"
    elif val >= 1_000:
        s = f"{val / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}K"
    elif val >= 10:
        return f"{val:.0f}"
    else:
        return f"{val:.1f}".rstrip("0").rstrip(".") if (val % 1 != 0) else f"{int(val)}"


def get_bucket_label(followers: int | None) -> str:
    """Assign audience tier bucket."""
    if not followers or followers < 10_000:
        return "< 10K"
    elif followers < 300_000:
        return "10K–300K"
    elif followers < 1_000_000:
        return "300K–1M"
    else:
        return "1M+"


def extract_clean_handle(platform: str, url: str) -> str:
    """Extract a clean handle or domain label from URL."""
    if not url:
        return platform.capitalize()
    
    url = url.strip().rstrip("/")
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        netloc = parsed.netloc.lower().lstrip("www.")

        if platform == "telegram":
            # t.me/coachsagarsinha -> @coachsagarsinha
            parts = path.split("/")
            return f"@{parts[-1]}" if parts and parts[-1] else "@Telegram"
        elif platform in ("twitter", "x"):
            parts = path.split("/")
            return f"@{parts[-1]}" if parts and parts[-1] else "@X"
        elif platform == "instagram":
            parts = path.split("/")
            return f"@{parts[0]}" if parts and parts[0] else "@Instagram"
        elif platform == "linkedin":
            parts = path.split("/")
            return f"in/{parts[-1]}" if parts and parts[-1] else "LinkedIn"
        elif platform == "whatsapp":
            return "WhatsApp"
        elif platform == "facebook":
            parts = path.split("/")
            return f"fb/{parts[0]}" if parts and parts[0] else "Facebook"
        elif platform == "website":
            return netloc or "Website"
    except Exception:
        pass
    return platform.capitalize()


def fetch_creators_table_data():
    """Fetch consolidated creator records matching the user requested schema."""
    if not DB_PATH.exists():
        print(f"Error: Database file not found at {DB_PATH}")
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = """
    SELECT 
        c.id,
        c.name,
        c.email,
        c.phone,
        c.website,
        c.primary_category,
        c.creator_type,
        c.primary_language,
        c.influencer_score,
        c.audience_bucket,
        c.is_relevant,
        c.targets_india,
        p.platform,
        p.followers,
        p.profile_url
    FROM creators c
    LEFT JOIN platform_profiles p ON c.id = p.creator_id
    ORDER BY c.influencer_score DESC NULLS LAST, p.followers DESC NULLS LAST
    """

    rows = c.execute(query).fetchall()
    results = []

    for r in rows:
        cid = r["id"]

        # Detected brokers
        brokers = [
            b[0]
            for b in c.execute(
                "SELECT DISTINCT broker_name FROM broker_associations WHERE creator_id = ?",
                (cid,),
            ).fetchall()
        ]
        broker_str = ", ".join(brokers) if brokers else "-"

        # Structured Social links
        social_rows = c.execute(
            "SELECT platform, url, value FROM social_links WHERE creator_id = ?",
            (cid,),
        ).fetchall()

        structured_socials = []
        text_socials = []
        website_candidates = []

        for s in social_rows:
            plt = s[0].lower()
            url_val = s[1] or s[2] or ""
            if not url_val:
                continue

            if plt in ("telegram", "twitter", "x", "instagram", "whatsapp", "linkedin", "facebook", "youtube"):
                label = extract_clean_handle(plt, url_val)
                structured_socials.append({
                    "platform": plt,
                    "url": url_val,
                    "label": label,
                })
                text_socials.append(f"{plt}: {url_val}")
            elif plt == "website":
                website_candidates.append(url_val)

        social_str = ", ".join(text_socials) if text_socials else "-"

        # Phone fallback from social_links
        phone = r["phone"]
        if not phone:
            p_row = c.execute(
                "SELECT value FROM social_links WHERE creator_id = ? AND platform = ? LIMIT 1",
                (cid, "phone"),
            ).fetchone()
            if p_row:
                phone = p_row[0]

        # Website resolution (clean domain)
        website = r["website"]
        if not website and website_candidates:
            website = website_candidates[0]
        if not website:
            w_row = c.execute(
                "SELECT value FROM social_links WHERE creator_id = ? AND platform = ? LIMIT 1",
                (cid, "website"),
            ).fetchone()
            if w_row:
                website = w_row[0]

        # Email fallback from social_links
        email = r["email"]
        if not email:
            e_row = c.execute(
                "SELECT value FROM social_links WHERE creator_id = ? AND platform = ? LIMIT 1",
                (cid, "email"),
            ).fetchone()
            if e_row:
                email = e_row[0]

        # Platform Performance Metrics (Latest timestamped snapshot from instagram_metrics or youtube_metrics)
        platform_lower = (r["platform"] or "youtube").lower()
        
        posts_analyzed = 0
        views_analyzed = 0
        likes_analyzed = 0
        comments_analyzed = 0
        engagement_eligible_videos = 0
        shorts_ratio = None
        avg_views_raw = None
        med_views_raw = None
        avg_likes_raw = None
        med_likes_raw = None
        avg_comm_raw = None
        med_comm_raw = None
        eng_rate_raw = None
        metrics_time = None

        if platform_lower == "instagram":
            try:
                im_row = c.execute(
                    """
                    SELECT 
                        posts_analyzed,
                        views_analyzed,
                        likes_analyzed,
                        comments_analyzed,
                        average_views,
                        median_views,
                        average_likes,
                        median_likes,
                        average_comments,
                        median_comments,
                        engagement_rate,
                        metrics_calculated_at
                    FROM instagram_metrics
                    WHERE creator_id = ?
                    ORDER BY metrics_calculated_at DESC
                    LIMIT 1
                    """,
                    (cid,),
                ).fetchone()

                if im_row:
                    posts_analyzed = im_row[0]
                    views_analyzed = im_row[1]
                    likes_analyzed = im_row[2]
                    comments_analyzed = im_row[3]
                    avg_views_raw = im_row[4]
                    med_views_raw = im_row[5]
                    avg_likes_raw = im_row[6]
                    med_likes_raw = im_row[7]
                    avg_comm_raw = im_row[8]
                    med_comm_raw = im_row[9]
                    eng_rate_raw = im_row[10]
                    metrics_time = im_row[11]
            except sqlite3.OperationalError:
                pass
        else:
            try:
                ym_row = c.execute(
                    """
                    SELECT 
                        videos_analyzed,
                        views_analyzed,
                        likes_analyzed,
                        comments_analyzed,
                        average_views,
                        median_views,
                        average_likes,
                        median_likes,
                        average_comments,
                        median_comments,
                        engagement_rate,
                        engagement_eligible_videos,
                        shorts_ratio,
                        metrics_calculated_at
                    FROM youtube_metrics
                    WHERE creator_id = ?
                    ORDER BY metrics_calculated_at DESC
                    LIMIT 1
                    """,
                    (cid,),
                ).fetchone()

                if ym_row:
                    posts_analyzed = ym_row[0]
                    views_analyzed = ym_row[1]
                    likes_analyzed = ym_row[2]
                    comments_analyzed = ym_row[3]
                    avg_views_raw = ym_row[4]
                    med_views_raw = ym_row[5]
                    avg_likes_raw = ym_row[6]
                    med_likes_raw = ym_row[7]
                    avg_comm_raw = ym_row[8]
                    med_comm_raw = ym_row[9]
                    eng_rate_raw = ym_row[10]
                    engagement_eligible_videos = ym_row[11]
                    shorts_ratio = ym_row[12]
                    metrics_time = ym_row[13]
            except sqlite3.OperationalError:
                pass

        # Content Format Classification
        if platform_lower == "instagram":
            try:
                media_rows = c.execute(
                    """
                    SELECT LOWER(p.media_type), COUNT(*)
                    FROM posts p
                    JOIN platform_profiles pp ON p.platform_profile_id = pp.id
                    WHERE pp.creator_id = ?
                    GROUP BY LOWER(p.media_type)
                    """,
                    (cid,),
                ).fetchall()
                media_counts = {row[0]: row[1] for row in media_rows if row[0]}
            except sqlite3.OperationalError:
                media_counts = {}
            fmt_res = classify_instagram_format(media_counts, total_posts=posts_analyzed)
        else:
            fmt_res = classify_youtube_format(shorts_ratio, videos_analyzed=posts_analyzed)

        followers_val = r["followers"] or 0
        followers_str = format_metric(followers_val)
        bucket_str = get_bucket_label(followers_val)
        platform_name = (r["platform"] or "YouTube").capitalize()

        results.append(
            {
                "id": cid,
                "platform": platform_name,
                "name": (r["name"] or "N/A").strip(),
                "followers_raw": followers_val,
                "followers": followers_str,
                "bucket": bucket_str,
                "content_format": fmt_res.format_type.value,
                "format_label": fmt_res.label,
                "format_filter": fmt_res.filter_group,
                "format_breakdown": fmt_res.breakdown_text,
                "email": email or "-",
                "phone": phone or "-",
                "category": r["primary_category"] or "-",
                "language": r["primary_language"] or "-",
                "broker": broker_str,
                "website": website or "-",
                "social_handles": social_str,
                "structured_socials": structured_socials,
                "score": f"{r['influencer_score']:.1f}" if r["influencer_score"] is not None else "0.0",
                "profile_url": r["profile_url"] or "",
                "is_relevant": bool(r["is_relevant"]) if r["is_relevant"] is not None else True,
                "targets_india": bool(r["targets_india"]) if r["targets_india"] is not None else True,
                # Performance metrics
                "posts_analyzed": posts_analyzed,
                "views_analyzed": views_analyzed,
                "likes_analyzed": likes_analyzed,
                "comments_analyzed": comments_analyzed,
                "engagement_eligible_videos": engagement_eligible_videos,
                "shorts_ratio": shorts_ratio,
                "avg_views_raw": avg_views_raw,
                "avg_views": format_metric(avg_views_raw),
                "median_views": format_metric(med_views_raw),
                "avg_likes": format_metric(avg_likes_raw),
                "median_likes": format_metric(med_likes_raw),
                "avg_comments": format_metric(avg_comm_raw),
                "median_comments": format_metric(med_comm_raw),
                "engagement_rate": f"{eng_rate_raw:.2f}%" if eng_rate_raw is not None else "-",
                "metrics_calculated_at": metrics_time or "-",
            }
        )

    conn.close()
    return results


def export_csv(creators):
    """Export formatted table to CSV."""
    fieldnames = [
        "platform", "name", "followers", "bucket", "content_format", "format_breakdown",
        "avg_views", "median_views", "avg_likes", "median_likes",
        "avg_comments", "median_comments", "engagement_rate",
        "posts_analyzed", "views_analyzed",
        "email", "phone", "category", "language", "broker", "website", "social_handles"
    ]

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for c in creators:
            writer.writerow(c)

    print(f"[+] CSV exported: {CSV_FILE}")


def export_html(creators):
    """Export sleek interactive HTML dashboard with search, category/broker filter, and rich badges."""
    
    # Collect unique brokers & categories for dropdown filters
    all_brokers = sorted({b.strip() for r in creators for b in r["broker"].split(",") if b.strip() and b.strip() != "-"})
    all_categories = sorted({r["category"].strip() for r in creators if r["category"] and r["category"] != "-"})

    table_rows = []
    for r in creators:
        email_cell = f'<a href="mailto:{r["email"]}" class="email-link" title="{r["email"]}">{r["email"]}</a>' if r["email"] != "-" else '<span class="text-muted">-</span>'
        phone_cell = f'<a href="tel:{r["phone"]}" class="phone-link">{r["phone"]}</a>' if r["phone"] != "-" else '<span class="text-muted">-</span>'
        
        # Website cell with clean pill
        if r["website"] != "-":
            clean_host = urlparse(r["website"]).netloc.lstrip("www.") or r["website"][:25]
            website_cell = f'<a href="{r["website"]}" target="_blank" rel="noopener" class="site-badge" title="{r["website"]}">🌐 {clean_host} ↗</a>'
        else:
            website_cell = '<span class="text-muted">-</span>'

        channel_link = f' <a href="{r["profile_url"]}" target="_blank" rel="noopener" class="link-btn" title="Open YouTube Profile">↗</a>' if r["profile_url"] else ""
        
        cat_badge = f'<span class="badge badge-cat">{r["category"]}</span>' if r["category"] != "-" else '<span class="text-muted">-</span>'
        
        # Broker badges
        if r["broker"] != "-":
            b_badges = []
            for b in r["broker"].split(","):
                b_name = b.strip()
                b_badges.append(f'<span class="badge badge-broker">{b_name}</span>')
            broker_badge = " ".join(b_badges)
        else:
            broker_badge = '<span class="text-muted">-</span>'

        bucket_badge = f'<span class="badge badge-bucket">{r["bucket"]}</span>'
        format_badge = f'<span class="badge badge-fmt badge-fmt-{r["format_filter"]}" title="{r["format_breakdown"]}">{r["format_label"]}</span>' if r["format_label"] != "-" else '<span class="text-muted">-</span>'

        # Performance Analytics Cell
        if r.get("posts_analyzed", 0) > 0:
            views_info = f'<div class="perf-metric">👁️ <strong>{r["avg_views"]}</strong> <span class="perf-sub">(Med: {r["median_views"]})</span></div>' if r["avg_views"] != "-" else '<div class="perf-sub">No video views</div>'
            likes_info = f'<div class="perf-metric">❤️ <strong>{r["avg_likes"]}</strong> <span class="perf-sub">(Med: {r["median_likes"]})</span></div>' if r["avg_likes"] != "-" else ''
            comments_info = f'<div class="perf-metric">💬 <strong>{r["avg_comments"]}</strong> <span class="perf-sub">(Med: {r["median_comments"]})</span></div>' if r["avg_comments"] != "-" else ''
            if r["platform"].lower() == "youtube":
                elig = r.get("engagement_eligible_videos", 0)
                sample_info = f'<div class="perf-sample">{r["posts_analyzed"]} videos analyzed ({elig} eligible)</div>'
            else:
                sample_info = f'<div class="perf-sample">{r["posts_analyzed"]} posts analyzed ({r["views_analyzed"]} vids)</div>'
            perf_cell = f'<div class="perf-cell">{views_info}{likes_info}{comments_info}{sample_info}</div>'
        else:
            perf_cell = '<span class="text-muted">-</span>'

        # Engagement Rate Cell
        if r.get("engagement_rate") and r["engagement_rate"] != "-":
            eng_cell = f'<span class="badge badge-eng">{r["engagement_rate"]}</span>'
        else:
            eng_cell = '<span class="text-muted">-</span>'

        # Social badges
        social_badges = []
        if r.get("structured_socials"):
            for s in r["structured_socials"]:
                plt = s["platform"]
                badge_cls = f"social-pill pill-{plt}"
                icon = {
                    "telegram": "✈️",
                    "instagram": "📸",
                    "twitter": "𝕏",
                    "x": "𝕏",
                    "linkedin": "💼",
                    "whatsapp": "💬",
                    "facebook": "📘",
                    "youtube": "▶️"
                }.get(plt, "🔗")
                social_badges.append(
                    f'<a href="{s["url"]}" target="_blank" rel="noopener" class="{badge_cls}" title="{plt.capitalize()}: {s["url"]}">{icon} {s["label"]}</a>'
                )
            social_cell = '<div class="social-flex">' + "".join(social_badges) + '</div>'
        else:
            social_cell = '<span class="text-muted">-</span>'

        table_rows.append(f"""
        <tr data-category="{r["category"]}" data-broker="{r["broker"]}" data-bucket="{r["bucket"]}" data-platform="{r["platform"]}" data-format="{r["format_filter"]}">
            <td><span class="platform-tag platform-{r["platform"].lower()}">{r["platform"]}</span></td>
            <td><strong class="creator-name">{r["name"]}</strong>{channel_link}</td>
            <td data-order="{r["followers_raw"]}"><span class="followers-num">{r["followers"]}</span></td>
            <td>{bucket_badge}</td>
            <td>{format_badge}</td>
            <td>{perf_cell}</td>
            <td>{eng_cell}</td>
            <td>{email_cell}</td>
            <td>{phone_cell}</td>
            <td>{cat_badge}</td>
            <td><span class="lang-tag">{r["language"]}</span></td>
            <td>{broker_badge}</td>
            <td>{website_cell}</td>
            <td>{social_cell}</td>
        </tr>
        """)

    broker_options = "".join([f'<option value="{b}">{b}</option>' for b in all_brokers])
    cat_options = "".join([f'<option value="{c}">{c}</option>' for c in all_categories])

    total_with_broker = sum(1 for r in creators if r["broker"] != "-")
    total_contacts = sum(1 for r in creators if r["email"] != "-" or r["phone"] != "-")
    total_longform = sum(1 for r in creators if r.get("format_filter") == "longform")
    total_shortform = sum(1 for r in creators if r.get("format_filter") in ("shortform", "carousels", "images"))

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Financial Influencer & Creator Intelligence Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #141c2e;
            --card-border: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-sub: #64748b;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --primary-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
            --row-hover: #1b253b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{ background-color: var(--bg-color); color: var(--text-main); padding: 25px; min-height: 100vh; }}
        .container {{ max-width: 1750px; margin: 0 auto; }}
        
        /* Header & Stats */
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 15px; }}
        .title-group h1 {{ font-size: 26px; font-weight: 800; background: var(--primary-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -0.5px; }}
        .title-group p {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 24px; }}
        .stat-card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 16px 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }}
        .stat-title {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}
        .stat-value {{ font-size: 24px; font-weight: 800; color: #fff; margin-top: 4px; display: flex; align-items: baseline; gap: 6px; }}
        .stat-desc {{ font-size: 11.5px; color: var(--text-sub); margin-top: 2px; }}

        /* Filter Controls */
        .controls-bar {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 14px 18px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 20px; }}
        .search-box {{ flex: 1; min-width: 260px; position: relative; }}
        .search-input {{ width: 100%; padding: 10px 14px 10px 36px; border-radius: 8px; background: #0f172a; border: 1px solid var(--card-border); color: #fff; font-size: 13.5px; outline: none; transition: 0.2s; }}
        .search-input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }}
        .search-icon {{ position: absolute; left: 12px; top: 50%; transform: translateY(-50%); font-size: 13px; color: var(--text-muted); }}

        .filter-select {{ padding: 10px 14px; border-radius: 8px; background: #0f172a; border: 1px solid var(--card-border); color: #e2e8f0; font-size: 13px; outline: none; cursor: pointer; }}
        .filter-select:focus {{ border-color: var(--accent); }}

        .export-btn {{ padding: 10px 18px; border-radius: 8px; background: linear-gradient(135deg, #0284c7, #2563eb); border: none; color: #fff; font-weight: 600; font-size: 13px; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; transition: 0.2s; }}
        .export-btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}

        /* Table Card */
        .table-card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 14px; overflow: hidden; box-shadow: 0 10px 35px rgba(0,0,0,0.35); }}
        .table-responsive {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
        th {{ background: #0d1424; padding: 13px 14px; color: var(--text-muted); font-weight: 700; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.6px; border-bottom: 1px solid var(--card-border); cursor: pointer; user-select: none; white-space: nowrap; transition: color 0.15s; }}
        th:hover {{ color: var(--accent); }}
        td {{ padding: 12px 14px; border-bottom: 1px solid rgba(30, 41, 59, 0.7); vertical-align: middle; }}
        tr:hover td {{ background-color: var(--row-hover); }}
        
        .creator-name {{ font-weight: 700; color: #f1f5f9; font-size: 13.5px; }}
        .platform-tag {{ display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .platform-youtube {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .platform-instagram {{ background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3); }}
        
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
        .badge-cat {{ background: rgba(2, 132, 199, 0.18); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.25); }}
        .badge-broker {{ background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); font-weight: 700; }}
        .badge-bucket {{ background: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.25); }}
        .badge-eng {{ background: rgba(234, 179, 8, 0.18); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.35); font-weight: 700; }}

        /* Content Format Badges */
        .badge-fmt {{ font-weight: 700; display: inline-flex; align-items: center; gap: 3px; }}
        .badge-fmt-longform {{ background: rgba(59, 130, 246, 0.18); color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.35); }}
        .badge-fmt-shortform {{ background: rgba(236, 72, 153, 0.18); color: #f472b6; border: 1px solid rgba(244, 114, 182, 0.35); }}
        .badge-fmt-hybrid {{ background: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.35); }}
        .badge-fmt-carousels {{ background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.35); }}
        .badge-fmt-images {{ background: rgba(245, 158, 11, 0.18); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.35); }}
        
        .perf-cell {{ display: flex; flex-direction: column; gap: 3px; min-width: 140px; }}
        .perf-metric {{ font-size: 12px; color: #f1f5f9; }}
        .perf-sub {{ font-size: 11px; color: var(--text-muted); }}
        .perf-sample {{ font-size: 10px; color: var(--text-sub); margin-top: 2px; }}

        .link-btn {{ color: var(--accent); text-decoration: none; font-size: 12px; font-weight: bold; margin-left: 4px; }}
        .followers-num {{ font-weight: 800; color: #f8fafc; font-size: 13px; }}
        .text-muted {{ color: var(--text-sub); }}
        .lang-tag {{ font-size: 12px; color: #cbd5e1; }}
        
        /* Website & Social Badges */
        .site-badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 3px 9px; border-radius: 6px; background: rgba(14, 165, 233, 0.12); border: 1px solid rgba(14, 165, 233, 0.3); color: #38bdf8; text-decoration: none; font-size: 11.5px; font-weight: 600; transition: 0.15s; }}
        .site-badge:hover {{ background: rgba(14, 165, 233, 0.25); }}
        
        .email-link {{ color: #93c5fd; text-decoration: none; font-size: 12px; }}
        .email-link:hover {{ text-decoration: underline; }}
        .phone-link {{ color: #86efac; text-decoration: none; font-size: 12px; }}
        
        .social-flex {{ display: flex; flex-wrap: wrap; gap: 5px; max-width: 320px; }}
        .social-pill {{ display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px; border-radius: 5px; font-size: 11px; font-weight: 600; text-decoration: none; transition: 0.15s; }}
        .social-pill:hover {{ transform: translateY(-1px); }}
        
        .pill-telegram {{ background: rgba(0, 136, 204, 0.18); color: #38bdf8; border: 1px solid rgba(0, 136, 204, 0.35); }}
        .pill-instagram {{ background: rgba(225, 48, 108, 0.18); color: #f472b6; border: 1px solid rgba(225, 48, 108, 0.35); }}
        .pill-twitter, .pill-x {{ background: rgba(255, 255, 255, 0.12); color: #f1f5f9; border: 1px solid rgba(255, 255, 255, 0.25); }}
        .pill-linkedin {{ background: rgba(10, 102, 194, 0.18); color: #60a5fa; border: 1px solid rgba(10, 102, 194, 0.35); }}
        .pill-whatsapp {{ background: rgba(37, 211, 102, 0.18); color: #4ade80; border: 1px solid rgba(37, 211, 102, 0.35); }}
        .pill-facebook {{ background: rgba(24, 119, 242, 0.18); color: #93c5fd; border: 1px solid rgba(24, 119, 242, 0.35); }}
        .pill-youtube {{ background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.35); }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Top Header -->
        <div class="header">
            <div class="title-group">
                <h1>Financial Influencer Intelligence Platform</h1>
                <p>Consolidated Creator Directory with Format Classification, Verified Contacts, Brokers & Performance Analytics</p>
            </div>
            <a href="creators_table.csv" download class="export-btn">📥 Export to CSV</a>
        </div>

        <!-- Metric Stat Cards -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">Total Creators</div>
                <div class="stat-value">{len(creators)}</div>
                <div class="stat-desc">Consolidated profiles</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">🎬 Longform Creators</div>
                <div class="stat-value">{total_longform} <span style="font-size: 13px; font-weight: normal; color: var(--text-sub);">({(total_longform/len(creators)*100):.0f}%)</span></div>
                <div class="stat-desc">&ge;80% YouTube Long-form</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">📱 Short-Form / Reels</div>
                <div class="stat-value">{total_shortform} <span style="font-size: 13px; font-weight: normal; color: var(--text-sub);">({(total_shortform/len(creators)*100):.0f}%)</span></div>
                <div class="stat-desc">Shorts, Reels & Slides</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">With Broker Assoc.</div>
                <div class="stat-value">{total_with_broker} <span style="font-size: 13px; font-weight: normal; color: var(--text-sub);">({(total_with_broker/len(creators)*100):.0f}%)</span></div>
                <div class="stat-desc">Zerodha, AngelOne, Upstox, etc.</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">With Contact Info</div>
                <div class="stat-value">{total_contacts}</div>
                <div class="stat-desc">Direct Email or Phone</div>
            </div>
        </div>

        <!-- Filter Controls -->
        <div class="controls-bar">
            <div class="search-box">
                <span class="search-icon">🔍</span>
                <input type="text" id="searchInput" class="search-input" placeholder="Search name, format, category, language, broker, handle, website..." onkeyup="applyFilters()">
            </div>

            <select id="formatFilter" class="filter-select" onchange="applyFilters()">
                <option value="">All Content Formats</option>
                <option value="longform">🎬 Longform (YouTube)</option>
                <option value="shortform">📱 Short-Form / Reels</option>
                <option value="hybrid">⚖️ Hybrid / Mixed</option>
                <option value="carousels">📑 Educational Carousels</option>
                <option value="images">🖼️ Image Posts</option>
            </select>

            <select id="brokerFilter" class="filter-select" onchange="applyFilters()">
                <option value="">All Brokers</option>
                {broker_options}
            </select>

            <select id="catFilter" class="filter-select" onchange="applyFilters()">
                <option value="">All Categories</option>
                {cat_options}
            </select>

            <select id="bucketFilter" class="filter-select" onchange="applyFilters()">
                <option value="">All Follower Tiers</option>
                <option value="1M+">1M+ Followers</option>
                <option value="300K–1M">300K–1M Followers</option>
                <option value="10K–300K">10K–300K Followers</option>
                <option value="< 10K">&lt; 10K Followers</option>
            </select>

            <select id="platformFilter" class="filter-select" onchange="applyFilters()">
                <option value="">All Platforms</option>
                <option value="YouTube">YouTube</option>
                <option value="Instagram">Instagram</option>
            </select>
        </div>

        <!-- Main Consolidated Table -->
        <div class="table-card">
            <div class="table-responsive">
                <table id="creatorsTable">
                    <thead>
                        <tr>
                            <th onclick="sortTable(0)">Platform ↕</th>
                            <th onclick="sortTable(1)">Name ↕</th>
                            <th onclick="sortTable(2)">Followers ↕</th>
                            <th onclick="sortTable(3)">Tier ↕</th>
                            <th onclick="sortTable(4)">Format ↕</th>
                            <th>Performance (Views / Likes / Comments)</th>
                            <th>Eng. Rate</th>
                            <th onclick="sortTable(7)">Email ↕</th>
                            <th onclick="sortTable(8)">Phone ↕</th>
                            <th onclick="sortTable(9)">Category ↕</th>
                            <th onclick="sortTable(10)">Language ↕</th>
                            <th onclick="sortTable(11)">Broker ↕</th>
                            <th onclick="sortTable(12)">Website ↕</th>
                            <th>Social Media Handles</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(table_rows)}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function applyFilters() {{
            const search = document.getElementById('searchInput').value.toLowerCase();
            const format = document.getElementById('formatFilter').value.toLowerCase();
            const broker = document.getElementById('brokerFilter').value.toLowerCase();
            const category = document.getElementById('catFilter').value.toLowerCase();
            const bucket = document.getElementById('bucketFilter').value.toLowerCase();
            const platform = document.getElementById('platformFilter').value.toLowerCase();

            const rows = document.querySelectorAll('#creatorsTable tbody tr');
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                const rowFormat = (row.dataset.format || '').toLowerCase();
                const rowBroker = (row.dataset.broker || '').toLowerCase();
                const rowCat = (row.dataset.category || '').toLowerCase();
                const rowBucket = (row.dataset.bucket || '').toLowerCase();
                const rowPlat = (row.dataset.platform || '').toLowerCase();

                const matchSearch = !search || text.includes(search);
                const matchFormat = !format || rowFormat === format;
                const matchBroker = !broker || rowBroker.includes(broker);
                const matchCat = !category || rowCat === category;
                const matchBucket = !bucket || rowBucket === bucket;
                const matchPlat = !platform || rowPlat === platform;

                row.style.display = (matchSearch && matchFormat && matchBroker && matchCat && matchBucket && matchPlat) ? '' : 'none';
            }});
        }}

        function sortTable(colIndex) {{
            const table = document.getElementById('creatorsTable');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const isAsc = table.dataset.sortCol == colIndex && table.dataset.sortOrder === 'asc';
            
            rows.sort((a, b) => {{
                const aCell = a.children[colIndex];
                const bCell = b.children[colIndex];
                const aVal = aCell.getAttribute('data-order') || aCell.innerText.trim();
                const bVal = bCell.getAttribute('data-order') || bCell.innerText.trim();
                
                const numA = parseFloat(aVal.replace(/[^0-9.-]+/g,""));
                const numB = parseFloat(bVal.replace(/[^0-9.-]+/g,""));
                
                if (!isNaN(numA) && !isNaN(numB)) {{
                    return isAsc ? numB - numA : numA - numB;
                }}
                return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
            }});

            table.dataset.sortCol = colIndex;
            table.dataset.sortOrder = isAsc ? 'desc' : 'asc';
            rows.forEach(r => tbody.appendChild(r));
        }}
    </script>
</body>
</html>
"""
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[+] HTML Table exported: {HTML_FILE}")


def main():
    creators = fetch_creators_table_data()
    export_csv(creators)
    export_html(creators)
    print(f"\n[OK] Successfully processed {len(creators)} creators into single consolidated table!")


if __name__ == "__main__":
    main()
