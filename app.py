import streamlit as st
import googleapiclient.discovery
import googleapiclient.errors
import pandas as pd
import re
from datetime import datetime, timedelta
import isodate
import numpy as np
from typing import List, Dict, Any

# Set page config
st.set_page_config(
    page_title="YouTube Search with Outlier Score",
    page_icon="🎬",
    layout="wide"
)

# Cache the API client to avoid creating it multiple times
@st.cache_resource
def get_youtube_client(api_key):
    """Create and cache a YouTube API client."""
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

def parse_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration format to seconds."""
    try:
        return int(isodate.parse_duration(duration_str).total_seconds())
    except:
        return 0

def calculate_outlier_score(video_data: Dict[str, Any]) -> float:
    """
    Calculate an outlier score for a video based on its metrics.
    
    Higher scores indicate a video is potentially more interesting/unique.
    
    The formula considers:
    - Views to subscriber ratio
    - Likes to views ratio
    - Comments to views ratio
    - Age of the video (newer videos get a boost)
    - View velocity (views per day)
    """
    # Extract necessary data
    view_count = int(video_data.get('statistics', {}).get('viewCount', 0))
    like_count = int(video_data.get('statistics', {}).get('likeCount', 0))
    comment_count = int(video_data.get('statistics', {}).get('commentCount', 0))
    subscriber_count = int(video_data.get('channel_subscribers', 1))  # Default to 1 to avoid division by zero
    published_at = video_data.get('snippet', {}).get('publishedAt', '')
    
    # Calculate video age in days
    if published_at:
        published_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
        days_since_published = (datetime.now() - published_date).days + 1  # Add 1 to avoid division by zero
    else:
        days_since_published = 1
    
    # Calculate components of the outlier score
    # 1. Views to subscriber ratio (how viral is the video compared to channel size)
    view_sub_ratio = min(view_count / max(subscriber_count, 1), 10)  # Cap at 10x
    
    # 2. Engagement ratios
    like_view_ratio = min(like_count / max(view_count, 1) * 100, 30)  # As percentage, capped at 30%
    comment_view_ratio = min(comment_count / max(view_count, 1) * 1000, 50)  # Scaled and capped
    
    # 3. View velocity (views per day)
    view_velocity = view_count / days_since_published
    
    # 4. Recency boost (videos less than 14 days old get a boost)
    recency_boost = max(0, (14 - min(days_since_published, 14)) / 14) * 3
    
    # Normalize view velocity with log scaling to handle viral videos better
    normalized_velocity = min(np.log10(max(view_velocity, 1)) / 6 * 10, 10)
    
    # Combine components into final score
    outlier_score = (
        view_sub_ratio * 0.35 +          # 35% weight to virality
        like_view_ratio * 0.25 +         # 25% weight to likes ratio
        comment_view_ratio * 0.15 +      # 15% weight to comment engagement
        normalized_velocity * 0.15 +     # 15% weight to view velocity
        recency_boost * 0.1              # 10% weight to recency boost
    )
    
    return round(outlier_score, 2)

def get_channel_statistics(youtube, channel_id: str) -> Dict[str, Any]:
    """Get channel statistics including subscriber count."""
    try:
        request = youtube.channels().list(
            part="statistics",
            id=channel_id
        )
        response = request.execute()
        
        if response.get("items"):
            return int(response["items"][0]["statistics"].get("subscriberCount", 0))
        return 0
    except:
        return 0

def search_youtube(youtube, keyword: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """Search YouTube for videos matching a keyword."""
    try:
        # Search for videos
        search_request = youtube.search().list(
            q=keyword,
            part="id,snippet",
            maxResults=max_results,
            type="video"
        )
        search_response = search_request.execute()
        
        # Extract video IDs
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
        
        if not video_ids:
            return []
        
        # Get detailed video information
        videos_request = youtube.videos().list(
            id=",".join(video_ids),
            part="snippet,contentDetails,statistics"
        )
        videos_response = videos_request.execute()
        
        # Process videos
        videos = []
        for video in videos_response.get("items", []):
            # Get channel subscribers
            channel_id = video["snippet"]["channelId"]
            subscriber_count = get_channel_statistics(youtube, channel_id)
            
            # Add subscriber count to video data
            video["channel_subscribers"] = subscriber_count
            
            # Add video to list
            videos.append(video)
        
        return videos
    
    except googleapiclient.errors.HttpError as e:
        st.error(f"YouTube API error: {e}")
        return []
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return []

def main():
    st.title("YouTube Search with Outlier Score")
    
    # Sidebar for API key input
    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("Enter your YouTube API Key", type="password")
        
        st.subheader("Search Options")
        keyword = st.text_input("Search keyword")
        min_outlier_score = st.slider("Minimum outlier score", 0.0, 10.0, 5.0, 0.1)
        
        st.subheader("Filters")
        video_length = st.radio(
            "Video length",
            options=["All", "Short Form (< 3 min)", "Long Form (≥ 3 min)"]
        )
        
        sort_by = st.radio(
            "Sort results by",
            options=["Outlier Score", "View Count"]
        )
    
    # Main area for search results
    if not api_key:
        st.info("Please enter your YouTube API key in the sidebar to get started.")
        st.markdown("""
        ### How to get a YouTube API Key:
        1. Go to [Google Cloud Console](https://console.cloud.google.com/)
        2. Create a new project
        3. Enable the YouTube Data API v3
        4. Create credentials (API Key)
        5. Copy and paste the API key here
        """)
        return
    
    if not keyword:
        st.info("Enter a search keyword in the sidebar to find videos.")
        return
    
    # Initialize YouTube API client
    youtube = get_youtube_client(api_key)
    
    # Search button
    if st.button("Search Videos"):
        with st.spinner("Searching YouTube videos..."):
            # Search YouTube
            videos = search_youtube(youtube, keyword)
            
            if not videos:
                st.warning("No videos found. Try a different keyword.")
                return
            
            # Process videos
            video_data = []
            for video in videos:
                # Parse duration
                duration_str = video.get("contentDetails", {}).get("duration", "PT0S")
                duration_seconds = parse_duration(duration_str)
                
                # Calculate outlier score
                outlier_score = calculate_outlier_score(video)
                
                # Check if video title or description contains keyword
                title = video.get("snippet", {}).get("title", "").lower()
                description = video.get("snippet", {}).get("description", "").lower()
                keyword_lower = keyword.lower()
                
                matches_keyword = keyword_lower in title or keyword_lower in description
                
                # Only include videos that match keyword and have sufficient outlier score
                if matches_keyword and outlier_score >= min_outlier_score:
                    # Format duration
                    minutes, seconds = divmod(duration_seconds, 60)
                    hours, minutes = divmod(minutes, 60)
                    if hours > 0:
                        duration_formatted = f"{hours}h {minutes}m {seconds}s"
                    else:
                        duration_formatted = f"{minutes}m {seconds}s"
                    
                    # Add to video data
                    video_data.append({
                        "Video ID": video.get("id", ""),
                        "Title": video.get("snippet", {}).get("title", ""),
                        "Channel": video.get("snippet", {}).get("channelTitle", ""),
                        "Duration": duration_formatted,
                        "Duration (seconds)": duration_seconds,
                        "View Count": int(video.get("statistics", {}).get("viewCount", 0)),
                        "Like Count": int(video.get("statistics", {}).get("likeCount", 0)),
                        "Comment Count": int(video.get("statistics", {}).get("commentCount", 0)),
                        "Published At": video.get("snippet", {}).get("publishedAt", "")[:10],
                        "Outlier Score": outlier_score,
                        "Thumbnail": video.get("snippet", {}).get("thumbnails", {}).get("medium", {}).get("url", "")
                    })
            
            # Convert to DataFrame
            df = pd.DataFrame(video_data)
            
            if df.empty:
                st.warning(f"No videos found matching the keyword '{keyword}' with an outlier score of at least {min_outlier_score}.")
                return
            
            # Apply video length filter
            if video_length == "Short Form (< 3 min)":
                df = df[df["Duration (seconds)"] < 180]
            elif video_length == "Long Form (≥ 3 min)":
                df = df[df["Duration (seconds)"] >= 180]
            
            # Sort results
            if sort_by == "Outlier Score":
                df = df.sort_values(by="Outlier Score", ascending=False)
            else:  # View Count
                df = df.sort_values(by="View Count", ascending=False)
            
            # Take top 10 results
            df = df.head(10)
            
            # Display results
            st.subheader(f"Top {len(df)} Results")
            
            # Display videos as cards
            for i, row in df.iterrows():
                with st.container():
                    cols = st.columns([1, 2])
                    with cols[0]:
                        st.image(row["Thumbnail"], use_column_width=True)
                    
                    with cols[1]:
                        st.markdown(f"### [{row['Title']}](https://www.youtube.com/watch?v={row['Video ID']})")
                        st.markdown(f"**Channel:** {row['Channel']}")
                        
                        metrics_cols = st.columns(4)
                        with metrics_cols[0]:
                            st.metric("Duration", row["Duration"])
                        with metrics_cols[1]:
                            st.metric("Views", f"{row['View Count']:,}")
                        with metrics_cols[2]:
                            st.metric("Likes", f"{row['Like Count']:,}")
                        with metrics_cols[3]:
                            st.metric("Outlier Score", row["Outlier Score"])
                        
                        st.markdown(f"**Published:** {row['Published At']}")
                    
                    st.markdown("---")

if __name__ == "__main__":
    main()
