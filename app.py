import streamlit as st
import math
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
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1e2538;
    }
    
    /* Button styling */
    .stButton>button {
        background-color: #4c6ef5;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 10px 24px;
        font-weight: bold;
        width: 100%;
    }
    
    .stButton>button:hover {
        background-color: #364fc7;
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
    except Exception as e:
        return 0

# Format large numbers for display
def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
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

def main():
    # Sidebar for inputs
    with st.sidebar:
        st.markdown("<h1 style='text-align: center; color: white;'>YouTube Search</h1>", unsafe_allow_html=True)
        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
        
        # Input for search keyword
        st.markdown("<p style='color: #adb5bd;'>SEARCH KEYWORD</p>", unsafe_allow_html=True)
        keyword = st.text_input("", placeholder="Enter keyword...", label_visibility="collapsed")
        
        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
        
        # Video type filter
        st.markdown("<p style='color: #adb5bd;'>VIDEO TYPE</p>", unsafe_allow_html=True)
        video_type = st.selectbox("", options=["All", "Short (< 3 mins)", "Long (>= 3 mins)"], label_visibility="collapsed")
        
        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
        
        # Sorting option
        st.markdown("<p style='color: #adb5bd;'>SORT BY</p>", unsafe_allow_html=True)
        sort_option = st.selectbox("", options=["Outlier Score", "View Count"], label_visibility="collapsed")
        
        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
        
        # Minimum outlier score
        st.markdown("<p style='color: #adb5bd;'>MINIMUM OUTLIER SCORE</p>", unsafe_allow_html=True)
        min_outlier_score = st.slider("", min_value=0.0, max_value=10.0, value=5.0, step=0.1, label_visibility="collapsed")
        
        st.markdown("<div style='height: 30px'></div>", unsafe_allow_html=True)
        
        # Search button
        search_button = st.button("Search Videos")

    # Main content area
    st.markdown("<h1 style='color: white;'>YouTube Video Dashboard</h1>", unsafe_allow_html=True)
    
    # Single metric container for videos found
    metric_container = st.container()
    with metric_container:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("""
            <div style="background-color: #1e2538; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
                <p style="color: #adb5bd; font-size: 14px; margin-bottom: 5px;">VIDEOS FOUND</p>
                <p style="font-size: 24px; font-weight: bold; margin-top: 0;">0</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Results section header
    st.markdown("<h2 style='margin-top: 30px;'>Search Results</h2>", unsafe_allow_html=True)
    
    # Results container
    results_container = st.container()
    
    if search_button:
        if not keyword:
            st.sidebar.error("Please enter a search keyword.")
            return
        
        # Information message while searching
        with results_container:
            search_info = st.info("Searching for videos...")
        
        try:
            # Get YouTube API key from Streamlit secrets
            API_KEY = st.secrets["YOUTUBE_API_KEY"]
            youtube = build("youtube", "v3", developerKey=API_KEY)
            
            # Search for videos matching the keyword
            search_response = youtube.search().list(
                part="snippet",
                q=keyword,
                type="video",
                maxResults=50  # Fetch more results to filter later
            ).execute()
            
            # Extract video IDs
            video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
            if not video_ids:
                search_info.error("No videos found.")
                return
            
            # Retrieve video details (statistics, contentDetails, and snippet)
            details_response = youtube.videos().list(
                part="contentDetails,statistics,snippet",
                id=",".join(video_ids)
            ).execute()
            
            results = []
            
            for item in details_response.get("items", []):
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
            
            # Sort results based on the selected option
            if sort_option == "View Count":
                results = sorted(results, key=lambda x: x["view_count"], reverse=True)
            else:
                results = sorted(results, key=lambda x: x["outlier_score"], reverse=True)
            
            # Show only the top 10 videos
            results = results[:10]
            
            # Remove the search info message
            search_info.empty()
            
            if not results:
                with results_container:
                    st.error("No videos match the criteria.")
            else:
                # Update the videos found metric
                with metric_container:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.markdown(f"""
                        <div style="background-color: #1e2538; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
                            <p style="color: #adb5bd; font-size: 14px; margin-bottom: 5px;">VIDEOS FOUND</p>
                            <p style="font-size: 24px; font-weight: bold; margin-top: 0;">{len(results)}</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Display results using pure Streamlit components
                with results_container:
                    for video in results:
                        # Create a container for each video
                        video_container = st.container()
                        with video_container:
                            # Apply styling to the container
                            st.markdown("""
                            <div style="background-color: #1e2538; border-radius: 10px; padding: 5px; margin-bottom: 20px;">
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Create two columns for thumbnail and content
                            col1, col2 = st.columns([1, 3])
                            
                            with col1:
                                # Display thumbnail
                                st.image(video['thumbnail'], use_column_width=True)
                            
                            with col2:
                                # Title with link
                                st.markdown(f"### [{video['title']}]({video['url']})")
                                
                                # Channel and date
                                st.markdown(f"**{video['channel']}** • {video['published_at']}")
                                
                                # Metrics in columns
                                metric_cols = st.columns(4)
                                with metric_cols[0]:
                                    st.markdown("**VIEWS**")
                                    st.markdown(f"{format_number(video['view_count'])}")
                                    
                                with metric_cols[1]:
                                    st.markdown("**LIKES**")
                                    st.markdown(f"{format_number(video['like_count'])}")
                                    
                                with metric_cols[2]:
                                    st.markdown("**DURATION**")
                                    st.markdown(f"{format_duration(video['duration'])}")
                                    
                                with metric_cols[3]:
                                    st.markdown("**OUTLIER SCORE**")
                                    st.markdown(f"<span style='color: #4c6ef5; font-weight: bold;'>{video['outlier_score']:.1f}</span>", unsafe_allow_html=True)
                                
                                # Description
                                if len(video['description']) > 150:
                                    desc = video['description'][:150] + "..."
                                else:
                                    desc = video['description']
                                st.markdown(desc)
                
        except Exception as e:
            with results_container:
                search_info.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
