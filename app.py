import streamlit as st
import math
import isodate
from googleapiclient.discovery import build

# Custom formula for outlier score calculation.
def calculate_outlier_score(view_count, like_count, duration_seconds):
    # Calculate duration in minutes.
    duration_minutes = duration_seconds / 60.0
    # Sample formula: high view/like counts and shorter videos get a higher score.
    score = (math.log(view_count + 1) + 2 * math.log(like_count + 1)) / (duration_minutes + 1)
    return score

# Parse ISO 8601 duration to seconds.
def parse_duration(duration_str):
    try:
        duration = isodate.parse_duration(duration_str)
        return duration.total_seconds()
    except Exception as e:
        return 0

def main():
    st.title("YouTube Video Search with Outlier Score")
    
    # Input for search keyword.
    keyword = st.text_input("Enter search keyword")
    
    # Video type filter.
    video_type = st.selectbox("Select Video Type", options=["All", "Short (< 3 mins)", "Long (>= 3 mins)"])
    
    # Sorting option.
    sort_option = st.selectbox("Sort Results By", options=["View Count", "Outlier Score"])
    
    if st.button("Search"):
        if not keyword:
            st.error("Please enter a search keyword.")
            return
        
        # Get your YouTube API key from Streamlit secrets.
        # Make sure to add your key as YOUTUBE_API_KEY in the Streamlit Cloud secrets.
        API_KEY = st.secrets["YOUTUBE_API_KEY"]
        youtube = build("youtube", "v3", developerKey=API_KEY)
        
        # Search for videos matching the keyword.
        search_response = youtube.search().list(
            part="snippet",
            q=keyword,
            type="video",
            maxResults=50  # Fetch more results to filter later.
        ).execute()
        
        # Extract video IDs.
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
        if not video_ids:
            st.write("No videos found.")
            return
        
        # Retrieve video details (statistics, contentDetails, and snippet).
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
            # Ensure the keyword is present in the title or description (case insensitive).
            if keyword.lower() not in title.lower() and keyword.lower() not in description.lower():
                continue
            
            # Get view and like counts.
            view_count = int(statistics.get("viewCount", 0))
            like_count = int(statistics.get("likeCount", 0)) if "likeCount" in statistics else 0
            
            # Get the video duration in seconds.
            duration_str = contentDetails.get("duration", "PT0S")
            duration_seconds = parse_duration(duration_str)
            
            # Calculate the outlier score.
            outlier_score = calculate_outlier_score(view_count, like_count, duration_seconds)
            if outlier_score <= 5:
                continue
            
            # Apply the video type filter.
            if video_type == "Short (< 3 mins)" and duration_seconds >= 180:
                continue
            if video_type == "Long (>= 3 mins)" and duration_seconds < 180:
                continue
            
            results.append({
                "video_id": video_id,
                "title": title,
                "description": description,
                "view_count": view_count,
                "like_count": like_count,
                "duration": duration_seconds,
                "outlier_score": outlier_score,
                "url": f"https://www.youtube.com/watch?v={video_id}"
            })
        
        # Sort results based on the selected option.
        if sort_option == "View Count":
            results = sorted(results, key=lambda x: x["view_count"], reverse=True)
        else:
            results = sorted(results, key=lambda x: x["outlier_score"], reverse=True)
        
        # Show only the top 10 videos.
        results = results[:10]
        
        if not results:
            st.write("No videos match the criteria.")
        else:
            for video in results:
                st.markdown(f"### [{video['title']}]({video['url']})")
                st.write(f"**Views:** {video['view_count']} | **Outlier Score:** {video['outlier_score']:.2f} | **Duration:** {int(video['duration'])} seconds")
                st.write(video["description"])
                st.markdown("---")

if __name__ == "__main__":
    main()
