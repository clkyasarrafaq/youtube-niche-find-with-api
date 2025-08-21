import streamlit as st
import requests
from datetime import datetime, timedelta

# YouTube API Key
API_KEY = "AIzaSyBV9ZSqfqlxW2H6Z-HsPJxEwQ7bt3qhcKc"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Streamlit App Title
st.title("YouTube Viral Topics Tool")

# Input Fields
days = st.number_input("Enter Days to Search (1-30):", min_value=1, max_value=30, value=5)

# List of broader keywords
keywords = [
    "Affair Relationship Stories", "Reddit Update", "Reddit Relationship Advice", "Reddit Relationship",
    "Reddit Cheating", "AITA Update", "Open Marriage", "Open Relationship", "X BF Caught",
    "Stories Cheat", "X GF Reddit", "AskReddit Surviving Infidelity", "GurlCan Reddit",
    "Cheating Story Actually Happened", "Cheating Story Real", "True Cheating Story",
    "Reddit Cheating Story", "R/Surviving Infidelity", "Surviving Infidelity",
    "Reddit Marriage", "Wife Cheated I Can't Forgive", "Reddit AP", "Exposed Wife",
    "Cheat Exposed"
]

# Fetch Data Button
if st.button("Fetch Data"):
    try:
        # Calculate date range
        start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
        all_results = []

        # Iterate over the list of keywords
        for keyword in keywords:
            st.write(f"Searching for keyword: {keyword}")

            # Define search parameters
            search_params = {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "publishedAfter": start_date,
                "maxResults": 5,
                "key": API_KEY,
            }

            # Fetch video data
            response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
            data = response.json()

            # Check if "items" key exists
            if "items" not in data or not data["items"]:
                st.warning(f"No videos found for keyword: {keyword}")
                continue

            video_ids = [video["id"]["videoId"] for video in data["items"] if "id" in video and "videoId" in video["id"]]
            channel_ids = [video['snippet']['channelId'] for video in data["items"] if 'snippet' in video and 'channelId' in video['snippet']]

            if not video_ids or not channel_ids:
                st.warning(f"Skipping keyword: {keyword} due to missing video/channel data.")
                continue

            # Fetch video statistics
            video_params = {'part': 'statistics', 'id': ','.join(video_ids), 'key': API_KEY}
            video_response = requests.get(YOUTUBE_VIDEO_URL, params=video_params)
            video_stats = video_response.json().get('items', [])

            if not video_stats:
                st.warning(f"Failed to fetch video statistics for keyword: {keyword}")
                continue

            # Fetch channel statistics
            channel_params = {'part': 'statistics', 'id': ','.join(channel_ids), 'key': API_KEY}
            channel_response = requests.get(YOUTUBE_CHANNEL_URL, params=channel_params)
            channel_data = channel_response.json().get('items', [])

            if not channel_data:
                st.warning(f"Failed to fetch channel statistics for keyword: {keyword}")
                continue

            channel_stats = {channel['id']: channel['statistics'] for channel in channel_data}

            # Collect results
            for video, stat in zip(data["items"], video_stats):
                title = video["snippet"].get("title", "N/A")
                description = video["snippet"].get("description", "N/A")
                url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
                view_count = int(stat["statistics"].get("viewCount", 0))
                channel_id = video["snippet"]["channelId"]
                subs = int(channel_stats.get(channel_id, {}).get("subscriberCount", 0))

                if subs < 3000:  # Only include channels with fewer than 3,000 subscribers
                    all_results.append({
                        "Title": title,
                        "Description": description,
                        "URL": url,
                        "Views": view_count,
                        "Subscribers": subs
                    })

        # Display results
        if all_results:
            # Sort results by views in descending order
            all_results.sort(key=lambda x: x["Views"], reverse=True)
            st.success(f"Found {len(all_results)} results across all keywords!")
            for result in all_results:
                st.markdown(f"**Title:** {result['Title']}\n"
                            f"**Description:** {result['Description']}\n"
                            f"**URL:** {result['URL']}\n"
                            f"**Views:** {result['Views']}\n"
                            f"**Subscribers:** {result['Subscribers']}\n"
                            "---")
        else:
            st.warning("No results found for channels with fewer than 3,000 subscribers.")

    except Exception as e:
        st.error(f"An error occurred: {e}")
