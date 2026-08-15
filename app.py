import streamlit as st
import re
from googleapiclient.discovery import build

# Replace with a free YouTube Data API key from Google Cloud Console
API_KEY = "YOUR_YOUTUBE_API_KEY"

st.title("YouTube Video Auto-Diagnostic")

# Input field for video URL
video_url = st.text_input("Paste YouTube Video URL:")

def extract_video_id(url):
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

if video_url:
    video_id = extract_video_id(video_url)
    if video_id and API_KEY != "YOUR_YOUTUBE_API_KEY":
        youtube = build('youtube', 'v3', developerKey=API_KEY)
        
        # Fetch public video stats
        request = youtube.videos().list(part="snippet,statistics", id=video_id)
        response = request.execute()
        
        if response['items']:
            item = response['items'][0]
            title = item['snippet']['title']
            thumbnail = item['snippet']['thumbnails']['high']['url']
            views = item['statistics'].get('viewCount', 0)
            likes = item['statistics'].get('likeCount', 0)
            
            # Display auto-fetched data
            st.subheader(f"Analyzing: {title}")
            st.image(thumbnail, width=300)
            st.metric("Total Views", views)
            st.metric("Total Likes", likes)
    else:
        st.warning("Please enter a valid URL or configure your API Key.")
