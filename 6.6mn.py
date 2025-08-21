import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

# ============== CONFIG ==============
# Set your API key. Recommend using st.secrets["YOUTUBE_API_KEY"]
API_KEY = "AIzaSyBV9ZSqfqlxW2H6Z-HsPJxEwQ7bt3qhcKc"

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"

# App title
st.title("YouTube Viral Topics Tool (Channel Insights)")

# Inputs
days = st.number_input("Enter Days to Search (1-30):", min_value=1, max_value=30, value=5)
max_results_per_keyword = st.number_input("Max results per keyword (1-50):", min_value=1, max_value=50, value=5)
max_subscribers = st.number_input("Max subscribers to include:", min_value=0, value=10000, step=500)

# Keywords (from your list)
keywords = [
    "Affair Relationship Stories", "Reddit Update", "Reddit Relationship Advice", "Reddit Relationship",
    "Reddit Cheating", "AITA Update", "Open Marriage", "Open Relationship", "X BF Caught",
    "Stories Cheat", "X GF Reddit", "AskReddit Surviving Infidelity", "GurlCan Reddit",
    "Cheating Story Actually Happened", "Cheating Story Real", "True Cheating Story",
    "Reddit Cheating Story", "R/Surviving Infidelity", "Surviving Infidelity",
    "Reddit Marriage", "Wife Cheated I Can't Forgive", "Reddit AP", "Exposed Wife",
    "Cheat Exposed"
]

# Tunables for metrics
LOOKBACK_DAYS = 30               # Monthly window
UPLOADS_TO_FETCH = 50            # How many recent uploads to analyze per channel
AVERAGE_SAMPLE_SIZE = 12         # Last N uploads to average over

def iso_to_dt(s: str) -> datetime:
    # Handles RFC3339 (e.g., 2023-05-01T12:34:56Z)
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def chunkify(lst: List[str], size: int) -> List[List[str]]:
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

def yt_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        st.warning(f"API error {r.status_code} on {url}: {r.text[:200]}")
        return {}
    return r.json()

def fetch_search_hits(start_date_iso: str, max_results: int) -> List[Dict[str, Any]]:
    """Search videos for all keywords and return a list of hits: {video_id, channel_id, keyword}."""
    hits = []
    for kw in keywords:
        params = {
            "part": "snippet",
            "q": kw,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": start_date_iso,
            "maxResults": max_results,
            "key": API_KEY,
        }
        data = yt_get(YOUTUBE_SEARCH_URL, params)
        items = data.get("items", [])
        for it in items:
            v_id = it.get("id", {}).get("videoId")
            ch_id = it.get("snippet", {}).get("channelId")
            if v_id and ch_id:
                hits.append({"video_id": v_id, "channel_id": ch_id, "keyword": kw})
    return hits

def fetch_videos_stats(video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Return {videoId: {viewCount:int, publishedAt:str}}"""
    out = {}
    for batch in chunkify(video_ids, 50):
        params = {
            "part": "statistics,snippet",
            "id": ",".join(batch),
            "key": API_KEY,
        }
        data = yt_get(YOUTUBE_VIDEO_URL, params)
        for it in data.get("items", []):
            vid = it.get("id")
            stats = it.get("statistics", {})
            snip = it.get("snippet", {})
            if not vid:
                continue
            vc = int(stats.get("viewCount", 0)) if "viewCount" in stats else 0
            out[vid] = {
                "viewCount": vc,
                "publishedAt": snip.get("publishedAt")
            }
    return out

def fetch_channels_details(channel_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Return {channelId: channel_object with snippet, statistics, contentDetails}"""
    out = {}
    for batch in chunkify(channel_ids, 50):
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch),
            "key": API_KEY,
        }
        data = yt_get(YOUTUBE_CHANNEL_URL, params)
        for it in data.get("items", []):
            ch_id = it.get("id")
            if ch_id:
                out[ch_id] = it
    return out

def fetch_uploads_playlist_items(playlist_id: str, max_items: int = UPLOADS_TO_FETCH) -> List[Dict[str, Any]]:
    """Return a list of {videoId, videoPublishedAt} (up to max_items)."""
    items = []
    page_token = None
    remaining = max_items
    while remaining > 0:
        page_size = min(50, remaining)
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": page_size,
            "key": API_KEY,
        }
        if page_token:
            params["pageToken"] = page_token
        data = yt_get(YOUTUBE_PLAYLIST_ITEMS_URL, params)
        for it in data.get("items", []):
            cd = it.get("contentDetails", {})
            v_id = cd.get("videoId")
            v_pub = cd.get("videoPublishedAt")
            if v_id and v_pub:
                items.append({"videoId": v_id, "videoPublishedAt": v_pub})
        remaining -= page_size
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items

def best_channel_url(channel_id: str, snippet: Dict[str, Any]) -> str:
    custom = snippet.get("customUrl")
    if custom:
        # customUrl may already start with '@' (handle)
        if custom.startswith("@"):
            return f"https://www.youtube.com/{custom}"
        return f"https://www.youtube.com/c/{custom}"
    return f"https://www.youtube.com/channel/{channel_id}"

def human_age(created_at_iso: str) -> str:
    created = iso_to_dt(created_at_iso)
    now = datetime.now(timezone.utc)
    total_months = (now.year - created.year) * 12 + (now.month - created.month)
    years = total_months // 12
    months = total_months % 12
    parts = []
    if years > 0:
        parts.append(f"{years}y")
    parts.append(f"{months}m")
    return " ".join(parts)

def compute_channel_metrics(ch_id: str,
                            ch_obj: Dict[str, Any],
                            uploads_index: Dict[str, List[str]],
                            video_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    snippet = ch_obj.get("snippet", {})
    stats = ch_obj.get("statistics", {})
    name = snippet.get("title", "N/A")
    subs = int(stats.get("subscriberCount", 0)) if "subscriberCount" in stats else 0
    total_videos = int(stats.get("videoCount", 0)) if "videoCount" in stats else 0
    link = best_channel_url(ch_id, snippet)

    # Collect recent uploads we fetched for this channel
    channel_vid_ids = uploads_index.get(ch_id, [])
    vids = []
    for vid in channel_vid_ids:
        v_info = video_lookup.get(vid)
        if not v_info:
            continue
        pub_at = v_info.get("publishedAt")
        vc = int(v_info.get("viewCount", 0))
        if pub_at:
            vids.append({"viewCount": vc, "publishedAt": iso_to_dt(pub_at)})

    # Popular Views (max views among analyzed uploads)
    popular_views = max((v["viewCount"] for v in vids), default=0)

    # Average Views (last AVERAGE_SAMPLE_SIZE uploads)
    vids_sorted = sorted(vids, key=lambda x: x["publishedAt"], reverse=True)
    avg_sample = vids_sorted[:AVERAGE_SAMPLE_SIZE]
    if avg_sample:
        average_views = int(sum(v["viewCount"] for v in avg_sample) / len(avg_sample))
    else:
        average_views = 0

    # Monthly Views (sum of views for videos published in last 30 days)
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    monthly = [v for v in vids if v["publishedAt"] >= since]
    monthly_views = int(sum(v["viewCount"] for v in monthly))
    monthly_uploads = len(monthly)

    # Upload frequency (monthly count and per week)
    uploads_per_week = round(monthly_uploads / 4.345, 2) if monthly_uploads else 0.0
    upload_freq_str = f"{monthly_uploads}/mo ({uploads_per_week}/wk)"

    # Channel age
    age_str = human_age(snippet.get("publishedAt", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))

    return {
        "Channel Name": name,
        "Channel Link": link,
        "Videos": total_videos,
        "Subs": subs,
        "Monthly Views": monthly_views,
        "Popular Views": popular_views,
        "Average Views": average_views,
        "Upload Freq.": upload_freq_str,
        "Channel Age": age_str,
    }

if st.button("Fetch Data"):
    if not API_KEY or API_KEY == "YOUR_YOUTUBE_API_KEY":
        st.error("Please set your YouTube API key in the code or use st.secrets['YOUTUBE_API_KEY'].")
        st.stop()

    try:
        with st.spinner("Searching videos and compiling channel metrics..."):
            now = datetime.now(timezone.utc)
            start_date = (now - timedelta(days=int(days))).strftime("%Y-%m-%dT%H:%M:%SZ")

            # 1) Search across keywords
            search_hits = fetch_search_hits(start_date, max_results_per_keyword)
            if not search_hits:
                st.warning("No videos found for the given keywords and timeframe.")
                st.stop()

            # 2) Fetch stats for search videos to identify 'focus keyword' per channel
            search_video_ids = list({h["video_id"] for h in search_hits})
            search_video_stats = fetch_videos_stats(search_video_ids)

            # 3) Aggregate per channel: choose the focus keyword by highest search-hit viewCount
            channel_focus: Dict[str, Dict[str, Any]] = {}
            for hit in search_hits:
                ch_id = hit["channel_id"]
                vid = hit["video_id"]
                vc = int(search_video_stats.get(vid, {}).get("viewCount", 0))
                kw = hit["keyword"]
                if ch_id not in channel_focus:
                    channel_focus[ch_id] = {"keyword": kw, "top_view": vc}
                else:
                    if vc > channel_focus[ch_id]["top_view"]:
                        channel_focus[ch_id] = {"keyword": kw, "top_view": vc}

            unique_channels = list(channel_focus.keys())

            # 4) Fetch channel details (snippet, stats, contentDetails.uploads)
            channels = fetch_channels_details(unique_channels)
            if not channels:
                st.warning("Failed to fetch channel details.")
                st.stop()

            # 5) Filter by subscribers
            filtered_channel_ids = []
            for ch_id, ch in channels.items():
                stats = ch.get("statistics", {})
                subs = int(stats.get("subscriberCount", 0)) if "subscriberCount" in stats else 0
                if subs < max_subscribers:
                    filtered_channel_ids.append(ch_id)

            if not filtered_channel_ids:
                st.warning(f"No channels found with fewer than {max_subscribers:,} subscribers.")
                st.stop()

            # 6) Collect uploads playlist items per channel (up to UPLOADS_TO_FETCH)
            uploads_playlist_map: Dict[str, str] = {}
            for ch_id in filtered_channel_ids:
                content = channels.get(ch_id, {}).get("contentDetails", {})
                uploads_id = content.get("relatedPlaylists", {}).get("uploads")
                if uploads_id:
                    uploads_playlist_map[ch_id] = uploads_id

            uploads_index: Dict[str, List[str]] = {ch_id: [] for ch_id in uploads_playlist_map.keys()}
            all_upload_video_ids: List[str] = []

            for ch_id, pl_id in uploads_playlist_map.items():
                pl_items = fetch_uploads_playlist_items(pl_id, UPLOADS_TO_FETCH)
                vid_ids = [it["videoId"] for it in pl_items]
                uploads_index[ch_id] = vid_ids
                all_upload_video_ids.extend(vid_ids)

            # 7) Fetch stats for all collected upload video IDs (batched)
            video_lookup = fetch_videos_stats(list(set(all_upload_video_ids)))

            # 8) Compute metrics per channel
            rows = []
            for ch_id in filtered_channel_ids:
                ch_obj = channels.get(ch_id)
                if not ch_obj:
                    continue
                metrics = compute_channel_metrics(ch_id, ch_obj, uploads_index, video_lookup)
                metrics["Focus Keyword"] = channel_focus.get(ch_id, {}).get("keyword", "N/A")
                rows.append(metrics)

            if not rows:
                st.warning("No results to display after processing.")
                st.stop()

            # 9) Build DataFrame with required columns and sort
            df = pd.DataFrame(rows, columns=[
                "Channel Name",
                "Channel Link",
                "Videos",
                "Subs",
                "Monthly Views",
                "Popular Views",
                "Average Views",
                "Upload Freq.",
                "Channel Age",
                "Focus Keyword"
            ])

            # Sort by Monthly Views desc by default
            df = df.sort_values(by="Monthly Views", ascending=False).reset_index(drop=True)

            # 10) Show results
            st.success(f"Found {len(df)} channels matching your criteria.")
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "Videos": st.column_config.NumberColumn(format="%,d"),
                    "Subs": st.column_config.NumberColumn(format="%,d"),
                    "Monthly Views": st.column_config.NumberColumn(format="%,d"),
                    "Popular Views": st.column_config.NumberColumn(format="%,d"),
                    "Average Views": st.column_config.NumberColumn(format="%,d"),
                }
            )

            # Download CSV
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", data=csv, file_name="youtube_channel_insights.csv", mime="text/csv")

    except Exception as e:
        st.error(f"An error occurred: {e}")
