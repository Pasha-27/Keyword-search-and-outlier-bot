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

# Apply custom CSS for dark mode and dashboard styling
st.markdown("""
<style>
    /* Dark mode colors */
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* Main panel styling */
    .main-panel {
        background-color: #151b28;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }
    
    /* Card styling */
    .card {
        background-color: #1e2538;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
    }
    
    /* Metric styling */
    .metric-container {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }
    
    .metric-value {
        font-size: 18px;
        font-weight: bold;
        margin-right: 10px;
    }
    
    .metric-label {
        font-size: 14px;
        color: #adb5bd;
    }
    
    /* Header styling */
    h1, h2, h3 {
        color: #ffffff;
    }
    
    /* Divider */
    hr {
        border-color: #2d3748;
        margin: 20px 0;
    }
    
    /* Custom sidebar styling */
    .css-1d391kg {
        background-color: #151b28;
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
    
    /* Selectbox styling */
    .stSelectbox [data-baseweb=select] {
        background-color: #1e2538;
        border-radius: 5px;
    }
    
    /* Search input styling */
    .stTextInput>div>div>input {
        background-color: #1e2538;
        color: white;
        border-radius: 5px;
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
    
    # Dashboard overview section
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div class='card'>
            <p style='color: #adb5bd; font-size: 14px;'>VIDEOS FOUND</p>
            <p style='font-size: 24px; font-weight: bold;'>0</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class='card'>
            <p style='color: #adb5bd; font-size: 14px;'>AVG VIEWS</p>
            <p style='font-size: 24px; font-weight: bold;'>0</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class='card'>
            <p style='color: #adb5bd; font-size: 14px;'>AVG DURATION</p>
            <p style='font-size: 24px; font-weight: bold;'>0m</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class='card'>
            <p style='color: #adb5bd; font-size: 14px;'>AVG OUTLIER SCORE</p>
            <p style='font-size: 24px; font-weight: bold;'>0.0</p>
        </div>
        """, unsafe_allow_html=True)
    
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
            total_views = 0
            total_duration = 0
            total_outlier_score = 0
            
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
                
                # Update totals for metrics
                total_views += view_count
                total_duration += duration_seconds
                total_outlier_score += outlier_score
                
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
                # Update dashboard metrics
                num_videos = len(results)
                avg_views = total_views / num_videos if num_videos > 0 else 0
                avg_duration = total_duration / num_videos if num_videos > 0 else 0
                avg_outlier_score = total_outlier_score / num_videos if num_videos > 0 else 0
                
                # Update the metrics cards
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.markdown(f"""
                    <div class='card'>
                        <p style='color: #adb5bd; font-size: 14px;'>VIDEOS FOUND</p>
                        <p style='font-size: 24px; font-weight: bold;'>{num_videos}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class='card'>
                        <p style='color: #adb5bd; font-size: 14px;'>AVG VIEWS</p>
                        <p style='font-size: 24px; font-weight: bold;'>{format_number(int(avg_views))}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    st.markdown(f"""
                    <div class='card'>
                        <p style='color: #adb5bd; font-size: 14px;'>AVG DURATION</p>
                        <p style='font-size: 24px; font-weight: bold;'>{format_duration(avg_duration)}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col4:
                    st.markdown(f"""
                    <div class='card'>
                        <p style='color: #adb5bd; font-size: 14px;'>AVG OUTLIER SCORE</p>
                        <p style='font-size: 24px; font-weight: bold;'>{avg_outlier_score:.1f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Display results in a modern card layout
                with results_container:
                    st.markdown("<h2 style='margin-top: 30px;'>Search Results</h2>", unsafe_allow_html=True)
                    for video in results:
                        st.markdown(f"""
                        <div class='card'>
                            <div style='display: flex; flex-direction: row;'>
                                <div style='flex: 0 0 200px; margin-right: 20px;'>
                                    <img src="{video['thumbnail']}" style="width: 100%; border-radius: 5px;">
                                </div>
                                <div style='flex: 1;'>
                                    <h3 style='margin-top: 0;'>
                                        <a href="{video['url']}" target="_blank" style="color: #ffffff; text-decoration: none;">
                                            {video['title']}
                                        </a>
                                    </h3>
                                    <p style='color: #adb5bd; margin-bottom: 15px;'>{video['channel']} • {video['published_at']}</p>
                                    
                                    <div style='display: flex; margin-bottom: 15px;'>
                                        <div style='margin-right: 20px;'>
                                            <span style='color: #adb5bd; font-size: 12px;'>VIEWS</span><br>
                                            <span style='font-weight: bold;'>{format_number(video['view_count'])}</span>
                                        </div>
                                        <div style='margin-right: 20px;'>
                                            <span style='color: #adb5bd; font-size: 12px;'>LIKES</span><br>
                                            <span style='font-weight: bold;'>{format_number(video['like_count'])}</span>
                                        </div>
                                        <div style='margin-right: 20px;'>
                                            <span style='color: #adb5bd; font-size: 12px;'>DURATION</span><br>
                                            <span style='font-weight: bold;'>{format_duration(video['duration'])}</span>
                                        </div>
                                        <div>
                                            <span style='color: #adb5bd; font-size: 12px;'>OUTLIER SCORE</span><br>
                                            <span style='font-weight: bold; color: #4c6ef5;'>{video['outlier_score']:.1f}</span>
                                        </div>
                                    </div>
                                    
                                    <p style='color: #d9d9d9; font-size: 14px;'>{video['description'][:150]}...</p>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        
        except Exception as e:
            with results_container:
                search_info.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
