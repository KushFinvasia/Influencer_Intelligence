import urllib.request
import xml.etree.ElementTree as ET

def fetch_channel_videos_rss(channel_id: str) -> list[dict]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
            videos = []
            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns)
                t_str = title.text if title is not None else ""
                videos.append({"title": t_str})
            return videos
    except Exception as e:
        return []

# Test on Quick Support (channel ID UCCN3-BVMnr44LIUheSuppw1A) and Switch (channel ID UCjFKMoAk3qhRkW4eOqNm6dw)
quick_vids = fetch_channel_videos_rss("UCN3-BVMnr44LIUheSuppw1A")
print(f"Quick Support Latest Videos ({len(quick_vids)}):")
for v in quick_vids[:5]:
    print(" -", v["title"])

switch_vids = fetch_channel_videos_rss("UCjFKMoAk3qhRkW4eOqNm6dw")
print(f"\nSwitch Latest Videos ({len(switch_vids)}):")
for v in switch_vids[:5]:
    print(" -", v["title"])
