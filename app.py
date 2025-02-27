import streamlit as st
import math
import json
import isodate
from googleapiclient.discovery import build

# Set page configuration for dark theme
st.set_page_config(
    page_title="YouTube Video Search Dashboard",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS for dark mode
st.markdown("""
<style>
    /* Dark mode colors */
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* Card styling */
    div.stButton > button {
        background-color: #4c6ef5;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 10px 24px;
        font-weight: bold;
        width: 100%;
    }
    
    div.stButton > button:hover {
        background-color: #364fc7;
    }
    
    /* Fix background for sidebar */
    [data-testid=stSidebar] {
        background-color: #1e2538;
    }
    
    /* Metric container */
    .metric-container {
        background-color: #1e2538;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    
    /* Remove padding from containers */
    div.block-container {
        padding-top: 1rem;
    }

    /* Card container style */
    .video-card {
        background-color: #1e2538;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.3rem; /* Reduced bottom margin for tighter vertical spacing */
    }
    .video-thumbnail {
        width: 100%;
        border-radius: 5px;
        margin-bottom: 0.5rem;
    }
    .video-title {
        color: #fafafa;
        margin-bottom: 0.5rem;
        font-weight: bold;
        font-size: 1.1rem;
    }
    .video-meta {
        color: #fafafa;
        margin-bottom: 0.2rem;
        font-size: 0.9rem;
    }
    .outlier-pill {
        color: white;
        border-radius: 12px;
        padding: 5px 10px;
        font-weight: bold;
    }
    .video-link {
        color: #4c6ef5;
        text-decoration: none;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

def parse_duration(duration_str):
    """Parse ISO 8601 duration to seconds."""
    try:
        duration = isodate.parse_duration(duration_str)
        return duration.total_seconds()
    except Exception:
        return 0

def format_number(num):
    """Format large numbers for display."""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    else:
        return str(num)

def format_duration(seconds):
    """Format duration in seconds to a more readable H/M/S string."""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

def get_outlier_color(multiplier):
    """Determine the color for the outlier multiplier based on VidIQ's brackets."""
    if multiplier < 2:
        return "black"
    elif multiplier < 5:
        return "#4c6ef5"  # blue
    elif multiplier < 10:
        return "purple"
    else:
        return "red"

def load_channels(file_path="channels.json"):
    """
    Loads channel data from a JSON file.
    Expected JSON format:
    {
      "channels": [
        {"id": "CHANNEL_ID", "name": "Channel Name"},
        ...
      ]
    }
    """
    with open(file_path, "r") as f:
        data = json.load(f)
    return data.get("channels", [])

def build_card_html(video, channel_avg_views):
    """Constructs HTML for a single video card, including an Engagement Rate metric."""
    color = get_outlier_color(video['outlier_multiplier'])
    outlier_html = f"<span class='outlier-pill' style='background-color:{color};'>{video['outlier_multiplier']:.1f}x</span>"
    avg_views = channel_avg_views.get(video["channel_id"], 0)
    
    card_html = f"""
    <div class="video-card">
        <img src="{video['thumbnail']}" class="video-thumbnail" />
        <div class="video-title">{video['title']}</div>
        <div class="video-meta">{video['channel']} • {video['published_at']}</div>
        <div class="video-meta">
            <strong>Views:</strong> {format_number(video['view_count'])} |
            <strong>Duration:</strong> {format_duration(video['duration'])}
        </div>
        <div class="video-meta">
            <strong>Outlier Score:</strong> {outlier_html} |
            <strong>Channel Avg:</strong> {format_number(int(avg_views))}
        </div>
        <div class="video-meta">
            <strong>Engagement Rate:</strong> {video['engagement_rate']:.1f}%
        </div>
        <div class="video-meta">
            <a href="{video['url']}" class="video-link">Watch Video</a>
        </div>
    </div>
    """
    return card_html

def main():
    # Sidebar for inputs
    with st.sidebar:
        st.title("YouTube Search")
        st.write("")
        st.markdown("SEARCH KEYWORD")
        keyword = st.text_input("", placeholder="Enter keyword...", label_visibility="collapsed")
        st.write("")
        st.markdown("VIDEO TYPE")
        video_type = st.selectbox("", options=["All", "Short (< 3 mins)", "Long (>= 3 mins)"], label_visibility="collapsed")
        st.write("")
        st.markdown("SORT BY")
        sort_option = st.selectbox("", options=["Outlier Score", "View Count"], label_visibility="collapsed")
        st.write("")
        st.markdown("MINIMUM OUTLIER MULTIPLIER")
        min_outlier_multiplier = st.slider("", min_value=0.0, max_value=20.0, value=2.0, step=0.1, label_visibility="collapsed")
        st.write("")
        search_button = st.button("Search Videos")

    # Main title
    st.title("YouTube Video Dashboard")
    
    if search_button:
        if not keyword:
            st.sidebar.error("Please enter a search keyword.")
            return
        
        search_info = st.empty()
        search_info.info("Searching for videos in Finance channels...")
        
        try:
            API_KEY = st.secrets["YOUTUBE_API_KEY"]
            youtube = build("youtube", "v3", developerKey=API_KEY)
            
            # Load channels from JSON (only finance channels)
            channels = load_channels("channels.json")
            if not channels:
                search_info.error("No channels found in channels.json. Please update your file.")
                return
            
            # Get each channel's average views (total_views / total_videos)
            channel_avg_views = {}
            for ch in channels:
                channel_id = ch["id"]
                channel_response = youtube.channels().list(
                    part="statistics",
                    id=channel_id
                ).execute()
                if channel_response.get("items"):
                    stats = channel_response["items"][0]["statistics"]
                    total_views = int(stats.get("viewCount", 0))
                    total_videos = int(stats.get("videoCount", 0))
                    avg_views = total_views / total_videos if total_videos > 0 else 0
                    channel_avg_views[channel_id] = avg_views
                else:
                    channel_avg_views[channel_id] = 0
            
            all_video_ids = []
            # Search for videos channel by channel
            for ch in channels:
                channel_id = ch["id"]
                search_response = youtube.search().list(
                    part="snippet",
                    q=keyword,
                    channelId=channel_id,
                    type="video",
                    maxResults=50
                ).execute()
                items = search_response.get("items", [])
                all_video_ids.extend([item["id"]["videoId"] for item in items])
            
            if not all_video_ids:
                search_info.error("No videos found across the listed channels.")
                return
            
            # Retrieve details in chunks of 50
            details_responses = []
            def chunk_list(lst, size=50):
                for i in range(0, len(lst), size):
                    yield lst[i : i + size]
            for chunk in chunk_list(all_video_ids, 50):
                details_response = youtube.videos().list(
                    part="contentDetails,statistics,snippet",
                    id=",".join(chunk)
                ).execute()
                details_responses.append(details_response)
            
            detail_items = []
            for resp in details_responses:
                detail_items.extend(resp.get("items", []))
            
            results = []
            keyword_lower = keyword.lower()
            for item in detail_items:
                video_id = item["id"]
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})
                contentDetails = item.get("contentDetails", {})
                
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                tags = snippet.get("tags", [])
                channel_title = snippet.get("channelTitle", "")
                channel_id = snippet.get("channelId", "")
                thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                published_at = snippet.get("publishedAt", "")
                
                # Check for keyword in title, description, or tags (case-insensitive)
                if (keyword_lower not in title.lower() and
                    keyword_lower not in description.lower() and
                    not any(keyword_lower in tag.lower() for tag in tags)):
                    continue
                
                # Retrieve stats
                view_count = int(statistics.get("viewCount", 0))
                like_count = int(statistics.get("likeCount", 0)) if "likeCount" in statistics else 0
                comment_count = int(statistics.get("commentCount", 0)) if "commentCount" in statistics else 0
                
                # Calculate outlier multiplier
                if channel_id in channel_avg_views and channel_avg_views[channel_id] > 0:
                    multiplier = view_count / channel_avg_views[channel_id]
                else:
                    multiplier = 0
                
                if multiplier <= min_outlier_multiplier:
                    continue
                
                # Video duration filter
                duration_str = contentDetails.get("duration", "PT0S")
                duration_seconds = parse_duration(duration_str)
                if video_type == "Short (< 3 mins)" and duration_seconds >= 180:
                    continue
                if video_type == "Long (>= 3 mins)" and duration_seconds < 180:
                    continue
                
                # Calculate engagement rate
                if view_count > 0:
                    engagement_rate = ((like_count + comment_count) / view_count) * 100
                else:
                    engagement_rate = 0.0
                
                results.append({
                    "video_id": video_id,
                    "title": title,
                    "channel": channel_title,
                    "channel_id": channel_id,
                    "description": description,  # Not displayed in the card
                    "view_count": view_count,
                    "duration": duration_seconds,
                    "outlier_multiplier": multiplier,
                    "thumbnail": thumbnail,
                    "published_at": published_at[:10],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "engagement_rate": engagement_rate
                })
            
            # Sort results based on the chosen sort option
            if sort_option == "View Count":
                results = sorted(results, key=lambda x: x["view_count"], reverse=True)
            else:
                results = sorted(results, key=lambda x: x["outlier_multiplier"], reverse=True)
            
            # Show only the top 10
            results = results[:10]
            search_info.empty()
            
            if not results:
                st.error("No videos match the criteria.")
            else:
                # Show "Search Results" heading
                st.header("Search Results")
                
                # Show "Videos Found" metric below the heading
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                st.markdown("VIDEOS FOUND")
                st.markdown(f"<h2>{len(results)}</h2>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # Display results in a 3-column layout with a smaller gap
                for i in range(0, len(results), 3):
                    columns = st.columns(3, gap="small")
                    for j in range(3):
                        if i + j < len(results):
                            video = results[i + j]
                            card_html = build_card_html(video, channel_avg_views)
                            with columns[j]:
                                st.markdown(card_html, unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
