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
    
    /* Blue text for outlier score */
    .blue-text {
        color: #4c6ef5;
    }
</style>
""", unsafe_allow_html=True)

# Custom formula for outlier score calculation
def calculate_outlier_score(view_count, like_count, duration_seconds):
    # Enhanced formula with additional factors
    duration_minutes = duration_seconds / 60.0
    
    # Base score using views and likes (with log scaling)
    base_score = (math.log(view_count + 1) * 1.5 + math.log(like_count + 1) * 2) 
    
    # Duration factor - shorter videos get higher scores
    duration_factor = math.exp(-duration_minutes / 30) * 5  # exponential decay
    
    # Final score
    final_score = base_score * (0.8 + duration_factor * 0.2)
    
    return final_score

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

def load_channels(file_path="channels.json"):
    """
    Loads channel data from a JSON file.
    The file is expected to have a structure like:
    {
      "channels": [
        {
          "id": "UCabc123",
          "name": "Finance Guru"
        },
        {
          "id": "UCdef456",
          "name": "Money Matters"
        }
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
        
        # Input for search keyword
        st.markdown("SEARCH KEYWORD")
        keyword = st.text_input("", placeholder="Enter keyword...", label_visibility="collapsed")
        
        st.write("")
        
        # Video type filter
        st.markdown("VIDEO TYPE")
        video_type = st.selectbox("", options=["All", "Short (< 3 mins)", "Long (>= 3 mins)"], label_visibility="collapsed")
        
        st.write("")
        
        # Sorting option
        st.markdown("SORT BY")
        sort_option = st.selectbox("", options=["Outlier Score", "View Count"], label_visibility="collapsed")
        
        st.write("")
        
        # Minimum outlier score
        st.markdown("MINIMUM OUTLIER SCORE")
        min_outlier_score = st.slider("", min_value=0.0, max_value=10.0, value=5.0, step=0.1, label_visibility="collapsed")
        
        st.write("")
        
        # Search button
        search_button = st.button("Search Videos")

    # Main content area
    st.title("YouTube Video Dashboard")
    
    # Videos Found metric
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.markdown("VIDEOS FOUND")
        st.markdown("<h2>0</h2>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Results section
    st.header("Search Results")
    results_container = st.container()
    
    if search_button:
        if not keyword:
            st.sidebar.error("Please enter a search keyword.")
            return
        
        # Information message while searching
        search_info = st.empty()
        search_info.info("Searching for videos in Finance channels...")
        
        try:
            # Get YouTube API key from Streamlit secrets
            API_KEY = st.secrets["YOUTUBE_API_KEY"]
            youtube = build("youtube", "v3", developerKey=API_KEY)
            
            # Load finance channels from local JSON
            channels = load_channels("channels.json")
            if not channels:
                search_info.error("No channels found in channels.json. Please update your file.")
                return
            
            all_video_ids = []
            channel_video_map = {}  # Map channel_id -> list of video items from search
            
            # 1) Search each channel individually
            for ch in channels:
                channel_id = ch["id"]
                channel_name = ch.get("name", "Unknown Channel")
                
                # Query the channel with the given keyword
                search_response = youtube.search().list(
                    part="snippet",
                    q=keyword,
                    channelId=channel_id,  # Restrict search to this channel
                    type="video",
                    maxResults=50
                ).execute()
                
                items = search_response.get("items", [])
                # Store results in a dict for later
                channel_video_map[channel_id] = items
                # Collect all video IDs
                all_video_ids.extend([item["id"]["videoId"] for item in items])
            
            if not all_video_ids:
                search_info.error("No videos found across all listed channels.")
                return
            
            # 2) Retrieve details for all collected video IDs
            #    If there are more than 50 IDs, we need to chunk them.
            #    For simplicity, let's chunk in sets of 50.
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
            
            # Flatten items
            detail_items = []
            for resp in details_responses:
                detail_items.extend(resp.get("items", []))
            
            results = []
            # 3) Apply outlier/keyword/short-long filters
            for item in detail_items:
                video_id = item["id"]
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})
                contentDetails = item.get("contentDetails", {})
                
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                channel_title = snippet.get("channelTitle", "")
                thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                published_at = snippet.get("publishedAt", "")
                
                # Ensure the keyword is present in the title or description (case insensitive)
                # This is optional because the "q=keyword" search usually filters. 
                # We keep it to be extra sure:
                if keyword.lower() not in title.lower() and keyword.lower() not in description.lower():
                    continue
                
                # Get view and like counts
                view_count = int(statistics.get("viewCount", 0))
                like_count = int(statistics.get("likeCount", 0)) if "likeCount" in statistics else 0
                comment_count = int(statistics.get("commentCount", 0)) if "commentCount" in statistics else 0
                
                # Get the video duration in seconds
                duration_str = contentDetails.get("duration", "PT0S")
                duration_seconds = parse_duration(duration_str)
                
                # Calculate the outlier score
                outlier_score = calculate_outlier_score(view_count, like_count, duration_seconds)
                if outlier_score <= min_outlier_score:
                    continue
                
                # Apply the video type filter
                if video_type == "Short (< 3 mins)" and duration_seconds >= 180:
                    continue
                if video_type == "Long (>= 3 mins)" and duration_seconds < 180:
                    continue
                
                results.append({
                    "video_id": video_id,
                    "title": title,
                    "channel": channel_title,
                    "description": description,
                    "view_count": view_count,
                    "like_count": like_count,
                    "comment_count": comment_count,
                    "duration": duration_seconds,
                    "outlier_score": outlier_score,
                    "thumbnail": thumbnail,
                    "published_at": published_at[:10],  # Just the date part
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
            
            # 4) Sort results based on the selected option
            if sort_option == "View Count":
                results = sorted(results, key=lambda x: x["view_count"], reverse=True)
            else:
                results = sorted(results, key=lambda x: x["outlier_score"], reverse=True)
            
            # Show only the top 10 videos
            results = results[:10]
            
            # Remove the search info message
            search_info.empty()
            
            if not results:
                st.error("No videos match the criteria.")
            else:
                # Update the videos found metric
                with col1:
                    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                    st.markdown("VIDEOS FOUND")
                    st.markdown(f"<h2>{len(results)}</h2>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # Clear the existing results container
                results_container.empty()
                
                # Re-establish the container with the header
                st.header("Search Results")
                
                # Display each video using pure Streamlit components
                for i, video in enumerate(results):
                    # Create a colored background with st.expander
                    with st.expander(f"**{video['title']}**", expanded=True):
                        # Layout with columns
                        cols = st.columns([1, 3])
                        
                        # Thumbnail in first column
                        with cols[0]:
                            st.image(video['thumbnail'], use_container_width=True)
                            
                        # Video details in second column
                        with cols[1]:
                            # Channel and date
                            st.write(f"{video['channel']} • {video['published_at']}")
                            
                            # Video stats
                            stat_cols = st.columns(4)
                            with stat_cols[0]:
                                st.write("VIEWS")
                                st.write(f"**{format_number(video['view_count'])}**")
                            
                            with stat_cols[1]:
                                st.write("LIKES")
                                st.write(f"**{format_number(video['like_count'])}**")
                            
                            with stat_cols[2]:
                                st.write("DURATION")
                                st.write(f"**{format_duration(video['duration'])}**")
                            
                            with stat_cols[3]:
                                st.write("OUTLIER SCORE")
                                st.markdown(f"<span class='blue-text'><b>{video['outlier_score']:.1f}</b></span>", unsafe_allow_html=True)
                            
                            # Description
                            if len(video['description']) > 150:
                                st.write(f"{video['description'][:150]}...")
                            else:
                                st.write(video['description'])
                                
                            # Link to video
                            st.write(f"[Watch Video]({video['url']})")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
