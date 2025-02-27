import streamlit as st
import math
import isodate
import json
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
    
</style>
""", unsafe_allow_html=True)

# Parse ISO 8601 duration to seconds
def parse_duration(duration_str):
    try:
        duration = isodate.parse_duration(duration_str)
        return duration.total_seconds()
    except Exception:
        return 0

# Format large numbers for display
def format_number(num):
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    else:
        return str(num)

# Format duration for display
def format_duration(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

# Determine the color for the outlier multiplier based on VidIQ's brackets
def get_outlier_color(multiplier):
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

    st.title("YouTube Video Dashboard")
    
    # Videos Found metric
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.markdown("VIDEOS FOUND")
        st.markdown("<h2>0</h2>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("Search Results")
    results_container = st.container()
    
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
            for item in detail_items:
                video_id = item["id"]
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})
                contentDetails = item.get("contentDetails", {})
                
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                channel_title = snippet.get("channelTitle", "")
                channel_id = snippet.get("channelId", "")
                thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                published_at = snippet.get("publishedAt", "")
                
                # Extra check for keyword in title/description
                if keyword.lower() not in title.lower() and keyword.lower() not in description.lower():
                    continue
                
                view_count = int(statistics.get("viewCount", 0))
                # Use channel's average views to compute outlier multiplier
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
                
                results.append({
                    "video_id": video_id,
                    "title": title,
                    "channel": channel_title,
                    "channel_id": channel_id,
                    "description": description,
                    "view_count": view_count,
                    "duration": duration_seconds,
                    "outlier_multiplier": multiplier,
                    "thumbnail": thumbnail,
                    "published_at": published_at[:10],
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
            
            # Sort results based on the chosen sort option
            if sort_option == "View Count":
                results = sorted(results, key=lambda x: x["view_count"], reverse=True)
            else:
                results = sorted(results, key=lambda x: x["outlier_multiplier"], reverse=True)
            
            results = results[:10]
            search_info.empty()
            
            if not results:
                st.error("No videos match the criteria.")
            else:
                with col1:
                    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                    st.markdown("VIDEOS FOUND")
                    st.markdown(f"<h2>{len(results)}</h2>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                results_container.empty()
                st.header("Search Results")
                
                for i, video in enumerate(results):
                    with st.expander(f"**{video['title']}**", expanded=True):
                        cols = st.columns([1, 3])
                        with cols[0]:
                            st.image(video['thumbnail'], use_container_width=True)
                        with cols[1]:
                            st.write(f"{video['channel']} • {video['published_at']}")
                            stat_cols = st.columns(4)
                            with stat_cols[0]:
                                st.write("VIEWS")
                                st.write(f"**{format_number(video['view_count'])}**")
                            with stat_cols[1]:
                                st.write("DURATION")
                                st.write(f"**{format_duration(video['duration'])}**")
                            with stat_cols[2]:
                                st.write("OUTLIER SCORE")
                                color = get_outlier_color(video['outlier_multiplier'])
                                # Pill-like component for the outlier multiplier
                                st.markdown(
                                    f"<span style='background-color: {color}; color: white; border-radius: 12px; padding: 5px 10px; font-weight: bold;'>{video['outlier_multiplier']:.1f}x</span>",
                                    unsafe_allow_html=True
                                )
                            with stat_cols[3]:
                                st.write("CHANNEL AVG")
                                avg_views = channel_avg_views.get(video["channel_id"], 0)
                                st.write(f"**{format_number(int(avg_views))}**")
                            if len(video['description']) > 150:
                                st.write(f"{video['description'][:150]}...")
                            else:
                                st.write(video['description'])
                            st.write(f"[Watch Video]({video['url']})")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
