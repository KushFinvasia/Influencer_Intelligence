import sqlite3
import json

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()
c.execute("SELECT username, raw_data FROM platform_profiles WHERE platform = 'instagram' AND raw_data IS NOT NULL")
rows = c.fetchall()

video_posts = 0
total_posts = 0
posts_with_views = 0
sample_video_post = None

for u, r in rows:
    try:
        data = json.loads(r) if isinstance(r, str) else r
        posts = data.get("latestPosts", [])
        if not posts and "data" in data:
            posts = data["data"].get("raw_items", [])
        for p in posts:
            total_posts += 1
            is_vid = p.get("type") == "Video" or p.get("isVideo") or p.get("videoPlayCount") is not None or p.get("videoViewCount") is not None
            if is_vid:
                video_posts += 1
                views = p.get("videoPlayCount") or p.get("videoViewCount") or p.get("viewCount")
                if views is not None:
                    posts_with_views += 1
                    if not sample_video_post:
                        sample_video_post = p
    except Exception:
        pass

print(f"Total posts across all creators: {total_posts}")
print(f"Video / Reel posts: {video_posts}")
print(f"Posts with valid view counts: {posts_with_views}")
if sample_video_post:
    print("Sample Video Post with views:", {
        "id": sample_video_post.get("id"),
        "type": sample_video_post.get("type"),
        "videoViewCount": sample_video_post.get("videoViewCount"),
        "videoPlayCount": sample_video_post.get("videoPlayCount"),
        "likesCount": sample_video_post.get("likesCount"),
        "commentsCount": sample_video_post.get("commentsCount"),
        "timestamp": sample_video_post.get("timestamp"),
    })
