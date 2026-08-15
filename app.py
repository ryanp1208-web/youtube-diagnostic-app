import streamlit as st
import re
from datetime import datetime, timezone
from googleapiclient.discovery import build

API_KEY = "AIzaSyCrH_EOswa6DgOh2taq0aGo_gsUtdpT3TE"

st.title("YouTube Video & Thumbnail Diagnostic")

video_url = st.text_input("Paste YouTube Video URL:")

col_input1, col_input2, col_input3 = st.columns(3)
with col_input1:
    user_ctr = st.number_input("Enter CTR (%):", min_value=0.0, max_value=100.0, value=0.0, step=0.1)
with col_input2:
    user_impressions = st.number_input("Enter Impressions:", min_value=0, value=0, step=100)
with col_input3:
    user_retention = st.number_input("Enter Retention (%):", min_value=0.0, max_value=100.0, value=0.0, step=0.1)

def extract_video_id(url):
    regex = r"(?:v=|\/|be\/)([0-9A-Za-z_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

if video_url:
    video_id = extract_video_id(video_url)
    if video_id:
        youtube = build('youtube', 'v3', developerKey=API_KEY)
      request = youtube.videos().list(part="snippet,statistics", id=video_id)
        response = request.execute()
        
        if response['items']:
            item = response['items'][0]
            title = item['snippet']['title']
            channel_title = item['snippet']['channelTitle']
            channel_id = item['snippet']['channelId']
            thumbnail = item['snippet']['thumbnails']['high']['url']
            published_at_str = item['snippet']['publishedAt']
            views = int(item['statistics'].get('viewCount', 0))
            likes = int(item['statistics'].get('likeCount', 0))
            
            # Additional fetch for channel subscriber count
      channel_request = youtube.channels().list(part="statistics", id=channel_id)
            channel_response = channel_request.execute()
            sub_count = 0
            if channel_response['items']:
                sub_count = int(channel_response['items'][0]['statistics'].get('subscriberCount', 0))

           pub_date = datetime.fromisoformat(published_at_str.rstrip('Z'))
            days_old = (datetime.now(timezone.utc) - pub_date).days
            days_text = "Today" if days_old == 0 else f"{days_old} days ago"

            st.subheader(f"Analyzing: {title}")
            st.caption(f"Channel: **{channel_title}** ({sub_count:,} Subscribers)")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.image(thumbnail, use_container_width=True)
            with col2:
                st.metric("Total Views", f"{views:,}")
                st.metric("Total Likes", f"{likes:,}")
                st.metric("Published", days_text)
                if user_ctr > 0:
                    st.metric("Your CTR", f"{user_ctr}%")
                if user_impressions > 0:
                    st.metric("Impressions", f"{user_impressions:,}")
                if user_retention > 0:
                    st.metric("Your Retention", f"{user_retention}%")
            
            st.divider()
            st.subheader("Diagnostic Feedback")
            
            if user_ctr > 0:
                if user_impressions > 0 and user_impressions < 2000:
                    target_high = 8.0
                    target_low = 5.0
                    st.info("ℹ️ **Small Audience Pool (<2k Impressions):** YouTube is showing this mostly to hyper-targeted viewers/subscribers. Your CTR expectation is higher.")
                elif user_impressions >= 100000:
                    target_high = 4.0
                    target_low = 2.5
                    st.info("ℹ️ **Broad Scale Push (100k+ Impressions):** YouTube has pushed this deep into Browse feeds. Lower CTR is expected and normal at this scale.")
                else:
                    target_high = 6.0
                    target_low = 3.5
                    st.info("ℹ️ **Moderate Scale Push:** Video is reaching a general audience pool.")

                if user_ctr >= target_high:
                    st.success(f"✅ **Strong Packaging!** Your CTR of {user_ctr}% is performing great for {channel_title} at this scale ({user_impressions:,} impressions).")
                elif user_ctr >= target_low:
                    st.warning(f"⚠️ **Average Packaging:** Your CTR ({user_ctr}%) is decent, but sharpening thumbnail text or bumping contrast could unlock more clicks.")
                else:
                    st.error(f"🚨 **Underperforming Thumbnail:** A {user_ctr}% CTR at {user_impressions:,} impressions means the thumbnail isn't grabbing attention.")
                    st.write("**Fixes to test immediately:**")
                    st.write("- **Focus:** Ensure 1 clear focal point (face/object) rather than multi-element scenes.")
                    st.write("- **Text:** Limit thumbnail text to 2–3 words max (don't repeat the title verbatim).")
                    st.write("- **Contrast:** Increase color saturation and subject framing so it stands out on mobile size.")
            else:
                st.info("💡 Enter your CTR and Impressions above for full packaging analysis.")

            if user_retention > 0:
                if user_retention < 40.0:
                    st.error("🚨 **Low Retention (Under 40%):** Viewers drop off early. Trim intros and pay off the thumbnail promise faster.")
                else:
                    st.success("✅ **Solid Retention (Above 40%):** Viewers are staying engaged.")
        else:
            st.error("Video not found. Please check the URL.")
