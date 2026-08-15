import streamlit as st
import re
from datetime import datetime, timezone
from googleapiclient.discovery import build


# =========================================================
# PAGE SETUP
# =========================================================

st.set_page_config(
    page_title="YouTube Video Diagnostic",
    page_icon="📊",
    layout="wide"
)

st.title("📊 YouTube Video Diagnostic")
st.write(
    "Analyze your video's CTR, impressions, retention, and engagement "
    "to find what is helping or hurting its performance."
)


# =========================================================
# API KEY
# =========================================================

# IMPORTANT:
# Put your API key in Streamlit Secrets instead of directly
# inside this file.
#
# .streamlit/secrets.toml
#
# YOUTUBE_API_KEY = "YOUR_NEW_API_KEY"

try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    st.error(
        "YouTube API key not found. Add YOUTUBE_API_KEY to "
        "your Streamlit secrets."
    )
    st.stop()


# =========================================================
# VIDEO URL
# =========================================================

video_url = st.text_input(
    "Paste YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)


# =========================================================
# MANUAL METRICS
# =========================================================

st.subheader("Your YouTube Analytics")

col1, col2, col3 = st.columns(3)

with col1:
    user_ctr = st.number_input(
        "CTR (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1
    )

with col2:
    user_impressions = st.number_input(
        "Impressions",
        min_value=0,
        value=0,
        step=100
    )

with col3:
    user_retention = st.number_input(
        "Average Percentage Viewed (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1
    )


# =========================================================
# EXTRACT VIDEO ID
# =========================================================

def extract_video_id(url):

    patterns = [
        r"(?:v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


# =========================================================
# GET VIDEO DATA
# =========================================================

def get_video_data(video_id):

    youtube = build(
        "youtube",
        "v3",
        developerKey=API_KEY
    )

    request = youtube.videos().list(
        part="snippet,statistics",
        id=video_id
    )

    response = request.execute()

    if not response.get("items"):
        return None

    item = response["items"][0]

    title = item["snippet"]["title"]
    channel_title = item["snippet"]["channelTitle"]
    channel_id = item["snippet"]["channelId"]

    thumbnail = item["snippet"]["thumbnails"]["high"]["url"]

    published_at = item["snippet"]["publishedAt"]

    views = int(
        item["statistics"].get("viewCount", 0)
    )

    likes = int(
        item["statistics"].get("likeCount", 0)
    )

    # Get subscriber count
    channel_request = youtube.channels().list(
        part="statistics",
        id=channel_id
    )

    channel_response = channel_request.execute()

    subscribers = 0

    if channel_response.get("items"):

        subscribers = int(
            channel_response["items"][0]["statistics"]
            .get("subscriberCount", 0)
        )

    return {
        "title": title,
        "channel_title": channel_title,
        "thumbnail": thumbnail,
        "published_at": published_at,
        "views": views,
        "likes": likes,
        "subscribers": subscribers
    }


# =========================================================
# DIAGNOSTIC ENGINE
# =========================================================

def diagnose_video(
    ctr,
    impressions,
    retention,
    views,
    likes
):

    score = 100
    diagnostics = []

    # -----------------------------------------------------
    # CTR / PACKAGING
    # -----------------------------------------------------

    if impressions < 2000:

        if ctr >= 8:

            diagnostics.append({
                "category": "Packaging",
                "status": "good",
                "message": (
                    f"CTR is {ctr:.1f}% with only "
                    f"{impressions:,} impressions. "
                    "The early packaging signal is strong, "
                    "but the sample is still small."
                ),
                "impact": 0
            })

        elif ctr >= 5:

            diagnostics.append({
                "category": "Packaging",
                "status": "okay",
                "message": (
                    f"CTR is {ctr:.1f}%. The thumbnail/title "
                    "combination is getting a reasonable number "
                    "of clicks, but there is room to improve."
                ),
                "impact": 8
            })

            score -= 8

        else:

            diagnostics.append({
                "category": "Packaging",
                "status": "bad",
                "message": (
                    f"CTR is only {ctr:.1f}% on "
                    f"{impressions:,} impressions. "
                    "The thumbnail or title may not be "
                    "generating enough curiosity."
                ),
                "impact": 20
            })

            score -= 20

    elif impressions < 100000:

        if ctr >= 7:

            diagnostics.append({
                "category": "Packaging",
                "status": "good",
                "message": (
                    f"CTR is {ctr:.1f}% across "
                    f"{impressions:,} impressions. "
                    "Packaging is performing strongly."
                ),
                "impact": 0
            })

        elif ctr >= 4.5:

            diagnostics.append({
                "category": "Packaging",
                "status": "okay",
                "message": (
                    f"CTR is {ctr:.1f}% across "
                    f"{impressions:,} impressions. "
                    "Packaging is acceptable, but a stronger "
                    "thumbnail/title could increase clicks."
                ),
                "impact": 10
            })

            score -= 10

        else:

            diagnostics.append({
                "category": "Packaging",
                "status": "bad",
                "message": (
                    f"CTR is {ctr:.1f}% despite "
                    f"{impressions:,} impressions. "
                    "Packaging is likely limiting growth."
                ),
                "impact": 20
            })

            score -= 20

    else:

        if ctr >= 5:

            diagnostics.append({
                "category": "Packaging",
                "status": "good",
                "message": (
                    f"CTR is {ctr:.1f}% despite "
                    f"{impressions:,} impressions. "
                    "That is a strong packaging signal."
                ),
                "impact": 0
            })

        elif ctr >= 3:

            diagnostics.append({
                "category": "Packaging",
                "status": "okay",
                "message": (
                    f"CTR is {ctr:.1f}% with "
                    f"{impressions:,} impressions. "
                    "The video is reaching a broad audience, "
                    "but packaging could be sharper."
                ),
                "impact": 10
            })

            score -= 10

        else:

            diagnostics.append({
                "category": "Packaging",
                "status": "bad",
                "message": (
                    f"CTR is only {ctr:.1f}% after "
                    f"{impressions:,} impressions. "
                    "The thumbnail/title combination is "
                    "probably the biggest weakness."
                ),
                "impact": 25
            })

            score -= 25


    # -----------------------------------------------------
    # RETENTION
    # -----------------------------------------------------

    if retention >= 50:

        diagnostics.append({
            "category": "Retention",
            "status": "good",
            "message": (
                f"Average percentage viewed is "
                f"{retention:.1f}%. Viewers are staying engaged."
            ),
            "impact": 0
        })

    elif retention >= 40:

        diagnostics.append({
            "category": "Retention",
            "status": "okay",
            "message": (
                f"Average percentage viewed is "
                f"{retention:.1f}%. Retention is acceptable, "
                "but the opening and pacing could improve."
            ),
            "impact": 10
        })

        score -= 10

    elif retention >= 30:

        diagnostics.append({
            "category": "Retention",
            "status": "bad",
            "message": (
                f"Average percentage viewed is only "
                f"{retention:.1f}%. A significant number of "
                "viewers are leaving before the video finishes."
            ),
            "impact": 20
        })

        score -= 20

    else:

        diagnostics.append({
            "category": "Retention",
            "status": "bad",
            "message": (
                f"Average percentage viewed is only "
                f"{retention:.1f}%. Retention is a major weakness. "
                "Focus on the first minute, pacing, and removing "
                "unnecessary sections."
            ),
            "impact": 30
        })

        score -= 30


    # -----------------------------------------------------
    # LIKE ENGAGEMENT
    # -----------------------------------------------------

    like_rate = 0

    if views > 0:

        like_rate = (likes / views) * 100

        if like_rate >= 5:

            diagnostics.append({
                "category": "Engagement",
                "status": "good",
                "message": (
                    f"Like rate is {like_rate:.2f}%. "
                    "Viewer engagement is strong."
                ),
                "impact": 0
            })

        elif like_rate >= 2:

            diagnostics.append({
                "category": "Engagement",
                "status": "okay",
                "message": (
                    f"Like rate is {like_rate:.2f}%. "
                    "Engagement is reasonable."
                ),
                "impact": 3
            })

            score -= 3

        else:

            diagnostics.append({
                "category": "Engagement",
                "status": "bad",
                "message": (
                    f"Like rate is only {like_rate:.2f}%. "
                    "The video may not be creating enough engagement."
                ),
                "impact": 8
            })

            score -= 8


    # -----------------------------------------------------
    # FIND BIGGEST PROBLEM
    # -----------------------------------------------------

    biggest_problem = None
    biggest_impact = 0

    for diagnostic in diagnostics:

        if diagnostic["impact"] > biggest_impact:

            biggest_impact = diagnostic["impact"]
            biggest_problem = diagnostic["category"]


    if biggest_problem == "Packaging":

        priority = (
            "Thumbnail/title is the biggest opportunity. "
            "Consider improving the focal point, contrast, "
            "clarity, and curiosity of the packaging."
        )

    elif biggest_problem == "Retention":

        priority = (
            "Retention is the biggest opportunity. "
            "Focus on the opening, remove slow sections, "
            "and get to the main premise faster."
        )

    elif biggest_problem == "Engagement":

        priority = (
            "Engagement is the biggest opportunity. "
            "Give viewers more reasons to comment, like, "
            "or participate."
        )

    else:

        priority = (
            "No major weakness detected. "
            "The video's core metrics are performing reasonably well."
        )


    # -----------------------------------------------------
    # FINAL SCORE
    # -----------------------------------------------------

    score = max(0, min(100, score))

    if score >= 85:
        overall = "🟢 Excellent"

    elif score >= 70:
        overall = "🟢 Strong"

    elif score >= 55:
        overall = "🟡 Average"

    elif score >= 40:
        overall = "🟠 Needs Improvement"

    else:
        overall = "🔴 Needs Major Improvement"


    return score, overall, diagnostics, priority


# =========================================================
# ANALYZE BUTTON
# =========================================================

if st.button(
    "🔍 Analyze Video",
    type="primary",
    use_container_width=True
):

    if not video_url:

        st.error("Please paste a YouTube video URL.")

        st.stop()


    video_id = extract_video_id(video_url)

    if not video_id:

        st.error(
            "I couldn't find a valid YouTube video ID in that URL."
        )

        st.stop()


    with st.spinner("Getting YouTube video data..."):

        try:

            data = get_video_data(video_id)

        except Exception as e:

            st.error(
                f"YouTube API error: {e}"
            )

            st.stop()


    if not data:

        st.error(
            "Video not found. Check the URL and make sure "
            "the video exists."
        )

        st.stop()


    # =====================================================
    # VIDEO INFORMATION
    # =====================================================

    st.divider()

    st.header(f"🎬 {data['title']}")

    st.caption(
        f"Channel: {data['channel_title']} • "
        f"{data['subscribers']:,} subscribers"
    )


    col1, col2 = st.columns([1, 2])


    with col1:

        st.image(
            data["thumbnail"],
            use_container_width=True
        )


    with col2:

        st.metric(
            "Total Views",
            f"{data['views']:,}"
        )

        st.metric(
            "Total Likes",
            f"{data['likes']:,}"
        )


    # =====================================================
    # DIAGNOSIS
    # =====================================================

    score, overall, diagnostics, priority = diagnose_video(
        ctr=user_ctr,
        impressions=user_impressions,
        retention=user_retention,
        views=data["views"],
        likes=data["likes"]
    )


    st.divider()

    st.header("📊 Video Diagnosis")


    # Score
    st.subheader(
        f"{overall} — {score}/100"
    )


    # Main recommendation
    st.info(
        f"🎯 **Main thing to improve:** {priority}"
    )


    # Individual diagnostics
    st.subheader("Detailed Analysis")


    for diagnostic in diagnostics:

        category = diagnostic["category"]
        message = diagnostic["message"]
        status = diagnostic["status"]

        if status == "good":

            st.success(
                f"**{category}** — {message}"
            )

        elif status == "okay":

            st.warning(
                f"**{category}** — {message}"
            )

        else:

            st.error(
                f"**{category}** — {message}"
            )


    # =====================================================
    # RAW METRICS
    # =====================================================

    st.divider()

    st.subheader("📈 Your Metrics")

    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:
        st.metric(
            "CTR",
            f"{user_ctr:.1f}%"
        )

    with metric2:
        st.metric(
            "Impressions",
            f"{user_impressions:,}"
        )

    with metric3:
        st.metric(
            "Retention",
            f"{user_retention:.1f}%"
        )

    with metric4:

        like_rate = 0

        if data["views"] > 0:
            like_rate = (
                data["likes"] /
                data["views"]
            ) * 100

        st.metric(
            "Like Rate",
            f"{like_rate:.2f}%"
        )


st.divider()

st.caption(
    "Note: These diagnostic thresholds are heuristics, not official "
    "YouTube benchmarks. Performance varies by audience, topic, "
    "video length, and traffic source."
)
