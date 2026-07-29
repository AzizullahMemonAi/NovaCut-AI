import asyncio
import os
import httpx
from app.config import settings

# High Quality Royalty-Free Stock Video Fallback Library (9:16 & 16:9 MP4s)
FALLBACK_STOCK_VIDEOS = {
    "money": "https://assets.mixkit.co/videos/preview/mixkit-counting-dollar-bills-close-up-41544-large.mp4",
    "dollar": "https://assets.mixkit.co/videos/preview/mixkit-counting-dollar-bills-close-up-41544-large.mp4",
    "business": "https://assets.mixkit.co/videos/preview/mixkit-hands-of-a-man-working-on-a-laptop-42861-large.mp4",
    "tech": "https://assets.mixkit.co/videos/preview/mixkit-hands-of-a-man-working-on-a-laptop-42861-large.mp4",
    "city": "https://assets.mixkit.co/videos/preview/mixkit-aerial-view-of-city-traffic-at-night-11-large.mp4",
    "nature": "https://assets.mixkit.co/videos/preview/mixkit-forest-stream-in-the-sunlight-529-large.mp4",
    "default": "https://assets.mixkit.co/videos/preview/mixkit-hands-of-a-man-working-on-a-laptop-42861-large.mp4"
}

# In-memory Rate-Limit Shield Cache (Query Normalization & Deduplication)
STOCK_CACHE = {}

async def fetch_stock_video(query: str) -> dict:
    """
    Asynchronously fetches a stock video MP4 URL for B-roll injection.
    Uses normalized query caching to shield against API rate limits.
    """
    norm_query = " ".join(sorted(query.lower().strip().split())) if query else "default"
    
    if norm_query in STOCK_CACHE:
        cached = STOCK_CACHE[norm_query]
        cached["source"] = f"{cached.get('source', 'Stock API')} (Cached)"
        return cached

    pexels_key = getattr(settings, "PEXELS_API_KEY", os.environ.get("PEXELS_API_KEY", ""))
    
    if pexels_key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {"Authorization": pexels_key}
                resp = await client.get(
                    f"https://api.pexels.com/videos/search?query={query}&per_page=1",
                    headers=headers
                )
                if resp.status_code == 200:
                    data = resp.json()
                    videos = data.get("videos", [])
                    if videos:
                        video_files = videos[0].get("video_files", [])
                        hd_files = [f for f in video_files if f.get("quality") == "hd" and f.get("file_type") == "video/mp4"]
                        target = hd_files[0] if hd_files else video_files[0]
                        res = {
                            "query": query,
                            "video_url": target.get("link"),
                            "preview_image": videos[0].get("image"),
                            "source": "Pexels API"
                        }
                        STOCK_CACHE[norm_query] = res
                        return res
                elif resp.status_code == 429:
                    print(f"Pexels API Rate Limit 429 encountered for query '{query}'. Falling back to local HD media shield.")
        except Exception as e:
            print(f"Pexels API fetch warning ({query}): {e}")

    # Fallback matching
    q_lower = query.lower()
    matched_url = FALLBACK_STOCK_VIDEOS["default"]
    for k, url in FALLBACK_STOCK_VIDEOS.items():
        if k in q_lower:
            matched_url = url
            break

    res = {
        "query": query,
        "video_url": matched_url,
        "source": "Stock Footage Shield Library"
    }
    STOCK_CACHE[norm_query] = res
    return res
