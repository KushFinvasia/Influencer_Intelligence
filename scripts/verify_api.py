"""Verify the backend API with the live scraped creators."""

import httpx

def main():
    base_url = "http://127.0.0.1:8000"
    
    # 1. Health check
    r_health = httpx.get(f"{base_url}/health")
    print(f"[Health Check] Status: {r_health.status_code}, Response: {r_health.json()}")
    
    # 2. Creators listing
    r_creators = httpx.get(f"{base_url}/api/creators?page_size=10")
    print(f"\n[Creators List] Status: {r_creators.status_code}")
    data = r_creators.json()
    print(f"Total Creators in DB: {data.get('total')}")
    print("-" * 85)
    for c in data.get("results", []):
        followers = c.get("followers") or 0
        score = c.get("influencer_score") or 0.0
        cat = c.get("primary_category") or "N/A"
        name = c.get("name") or "Unknown"
        print(f"ID: {c.get('id'):2d} | Name: {name:<35} | Score: {score:5.1f} | Followers: {followers:>10,d} | Category: {cat}")
    print("-" * 85)
    
    # 3. Individual creator detail
    r_detail = httpx.get(f"{base_url}/api/creators/4")
    if r_detail.status_code == 200:
        c = r_detail.json()
        print(f"\n[Creator Detail - ID 4: {c['name']}]")
        print(f" - Primary Category: {c.get('primary_category')}")
        print(f" - Influencer Score: {c.get('influencer_score')}")
        print(f" - Platform Profiles: {[p['platform'] + ':' + str(p['followers']) for p in c.get('platform_profiles', [])]}")
        print(f" - Brokers Detected: {[b['broker_name'] for b in c.get('broker_associations', [])]}")
        print(f" - Social Links: {len(c.get('social_links', []))} links found")

    # 4. Filtered search for F&O
    r_fno = httpx.get(f"{base_url}/api/search?category=F%26O&page_size=5")
    data_fno = r_fno.json()
    print(f"\n[F&O Category Search] Total Matching: {data_fno.get('total')}")
    for c in data_fno.get("results", []):
        print(f" - {c.get('name'):<35} | Score: {c.get('influencer_score'):5.1f} | Followers: {c.get('followers', 0):>10,d}")
        
    # 5. Search by keyword
    r_kw = httpx.get(f"{base_url}/api/search?q=Zerodha&page_size=5")
    data_kw = r_kw.json()
    print(f"\n[Search keyword 'Zerodha'] Total Matching: {data_kw.get('total')}")
    for c in data_kw.get("results", []):
        print(f" - {c.get('name'):<35} | Score: {c.get('influencer_score'):5.1f}")

if __name__ == "__main__":
    main()
