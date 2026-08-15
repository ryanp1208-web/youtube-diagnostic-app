import streamlit as st
import re
import time
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube Video Doctor",
    page_icon="🩺",
    layout="wide"
)


# ============================================================
# SECURITY / CONFIG
# ============================================================

# Put this in Streamlit Cloud Secrets:
#
# YOUTUBE_API_KEY = "YOUR_KEY_HERE"
#
# NEVER put the real API key directly into this file.

try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    API_KEY = ""


# ============================================================
# SESSION SECURITY
# ============================================================

if "analysis_times" not in st.session_state:
    st.session_state.analysis_times = []

if "last_analysis_key" not in st.session_state:
    st.session_state.last_analysis_key = None

if "last_analysis_time" not in st.session_state:
    st.session_state.last_analysis_time = 0


MAX_ANALYSES_PER_HOUR = 10
COOLDOWN_SECONDS = 10


def check_rate_limit(analysis_key):
    """Limit excessive use from one browser session."""

    now = time.time()

    # Remove timestamps older than one hour
    st.session_state.analysis_times = [
        t for t in st.session_state.analysis_times
        if now - t < 3600
    ]

    # Cooldown
    if now - st.session_state.last_analysis_time < COOLDOWN_SECONDS:
        remaining = int(
            COOLDOWN_SECONDS -
            (now - st.session_state.last_analysis_time)
        )
        return False, f"Please wait {remaining} seconds before analyzing again."

    # Hourly limit
    if len(st.session_state.analysis_times) >= MAX_ANALYSES_PER_HOUR:
        return False, (
            "You've reached the limit of 10 analyses per hour "
            "for this browser session. Try again later."
        )

    # Duplicate request
    if analysis_key == st.session_state.last_analysis_key:
        return False, (
            "You already analyzed this video. "
            "The previous result is still on this page."
        )

    return True, ""


def record_analysis(analysis_key):
    now = time.time()

    st.session_state.analysis_times.append(now)
    st.session_state.last_analysis_time = now
    st.session_state.last_analysis_key = analysis_key


# ============================================================
# YOUTUBE HELPERS
# ============================================================

def extract_video_id(url):
    """Extract a YouTube video ID from common URL formats."""

    if not url:
        return None

    patterns = [
        r"(?:youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # Also allow users to paste just the ID
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
        return url.strip()

    return None


def parse_duration(duration):
    """Convert ISO 8601 YouTube duration to seconds."""

    if not duration:
        return 0

    match = re.match(
        r"PT"
        r"(?:(\d+)H)?"
        r"(?:(\d+)M)?"
        r"(?:(\d+)S)?",
        duration
    )

    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds}s"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m"

    if secs > 0:
        return f"{minutes}m {secs}s"

    return f"{minutes}m"


def get_video_type(seconds):
    """
    YouTube Shorts can be up to 3 minutes.
    This is a duration-based heuristic rather than
    an official Shorts classification.
    """

    if seconds <= 180:
        return "Shorts / short-form"

    return "Long-form video"


def time_since_published(published):
    try:
        published_dt = datetime.fromisoformat(
            published.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)
        delta = now - published_dt

        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return "Just now"

        minutes = total_seconds // 60

        if minutes < 60:
            return f"{minutes} minutes ago"

        hours = minutes // 60

        if hours < 24:
            return f"{hours} hours ago"

        days = hours // 24

        if days < 7:
            return f"{days} days ago"

        weeks = days // 7

        if weeks < 5:
            return f"{weeks} weeks ago"

        months = days // 30

        if months < 12:
            return f"{months} months ago"

        years = days // 365

        return f"{years} years ago"

    except Exception:
        return "Unknown"


# ============================================================
# CACHED YOUTUBE REQUESTS
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_video(video_id):
    """
    Cached for one hour.

    This is important because repeatedly analyzing
    the same video won't repeatedly hit the YouTube API.
    """

    if not API_KEY:
        return None

    youtube = build(
        "youtube",
        "v3",
        developerKey=API_KEY,
        cache_discovery=False
    )

    request = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=video_id
    )

    response = request.execute()

    if not response.get("items"):
        return None

    return response["items"][0]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_recent_uploads(channel_id):
    """Fetch recent uploads using the channel's uploads playlist."""

    if not API_KEY:
        return []

    youtube = build(
        "youtube",
        "v3",
        developerKey=API_KEY,
        cache_discovery=False
    )

    channel_response = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()

    if not channel_response.get("items"):
        return []

    uploads_playlist = (
        channel_response["items"][0]
        ["contentDetails"]
        ["relatedPlaylists"]
        ["uploads"]
    )

    playlist_response = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist,
        maxResults=8
    ).execute()

    results = []

    for item in playlist_response.get("items", []):
        snippet = item.get("snippet", {})

        results.append({
            "title": snippet.get("title", "Untitled"),
            "published": snippet.get("publishedAt", ""),
            "video_id": (
                snippet.get("resourceId", {})
                .get("videoId", "")
            )
        })

    return results


# ============================================================
# DIAGNOSTIC ENGINE
# ============================================================

def calculate_diagnosis(
    ctr,
    impressions,
    retention,
    views,
    likes,
    published,
    duration_seconds
):

    problems = []
    positives = []
    actions = []

    # --------------------------------------------------------
    # CTR
    # --------------------------------------------------------

    if ctr <= 0:
        pass

    elif impressions < 2000:

        if ctr >= 8:
            positives.append(
                "Your CTR is strong for a video with a small impression pool."
            )

        elif ctr >= 5:
            positives.append(
                "Your CTR is acceptable, but YouTube has not pushed the video very far yet."
            )

        else:
            problems.append(
                "CTR is weak while the video is still in a small impression pool."
            )
            actions.append(
                "Test a stronger thumbnail concept and a clearer title."
            )

    elif impressions >= 100000:

        if ctr >= 6:
            positives.append(
                "Your CTR is strong even at large distribution."
            )

        elif ctr >= 3.5:
            problems.append(
                "CTR is mediocre at large scale."
            )
            actions.append(
                "Consider improving the thumbnail/title package before changing the video itself."
            )

        else:
            problems.append(
                "CTR is weak despite significant distribution."
            )
            actions.append(
                "The packaging is probably limiting further clicks."
            )

    else:

        if ctr >= 7:
            positives.append(
                "Strong packaging: your CTR is performing well."
            )

        elif ctr >= 5:
            positives.append(
                "CTR is in a reasonable range."
            )

        elif ctr >= 3.5:
            problems.append(
                "CTR is somewhat weak."
            )
            actions.append(
                "Try a more immediately understandable thumbnail and title."
            )

        else:
            problems.append(
                "CTR is low."
            )
            actions.append(
                "Prioritize thumbnail and title improvements."
            )

    # --------------------------------------------------------
    # RETENTION
    # --------------------------------------------------------

    if retention > 0:

        if retention >= 50:
            positives.append(
                "Retention is excellent."
            )

        elif retention >= 40:
            positives.append(
                "Retention is solid."
            )

        elif retention >= 30:
            problems.append(
                "Retention is somewhat weak."
            )
            actions.append(
                "Tighten the opening and remove slow sections."
            )

        else:
            problems.append(
                "Retention is low."
            )
            actions.append(
                "The opening likely isn't paying off the thumbnail/title promise quickly enough."
            )

    # --------------------------------------------------------
    # VIEWS
    # --------------------------------------------------------

    published_text = time_since_published(published)

    try:
        published_dt = datetime.fromisoformat(
            published.replace("Z", "+00:00")
        )

        hours_old = max(
            1,
            (
                datetime.now(timezone.utc) -
                published_dt
            ).total_seconds() / 3600
        )

        view_velocity = views / hours_old

    except Exception:
        view_velocity = 0

    # --------------------------------------------------------
    # LIKES
    # --------------------------------------------------------

    if views > 0 and likes > 0:

        like_rate = (likes / views) * 100

        if like_rate >= 4:
            positives.append(
                "Viewer engagement through likes is strong."
            )

        elif like_rate < 1:
            problems.append(
                "Like engagement is relatively low."
            )

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    score = 50

    if ctr >= 7:
        score += 15
    elif ctr >= 5:
        score += 8
    elif ctr > 0 and ctr < 3.5:
        score -= 15

    if retention >= 50:
        score += 20
    elif retention >= 40:
        score += 10
    elif retention > 0 and retention < 30:
        score -= 15

    if impressions >= 100000 and ctr >= 5:
        score += 5

    if views > 0 and likes > 0:
        like_rate = (likes / views) * 100

        if like_rate >= 4:
            score += 5
        elif like_rate < 1:
            score -= 5

    score = max(0, min(100, score))

    if score >= 80:
        health = "Excellent"
    elif score >= 65:
        health = "Healthy"
    elif score >= 50:
        health = "Mixed"
    else:
        health = "Needs attention"

    # --------------------------------------------------------
    # WHAT IS HURTING?
    # --------------------------------------------------------

    if not problems:
        problems.append(
            "No major problem is obvious from the metrics provided."
        )

    # --------------------------------------------------------
    # WHAT I'D DO
    # --------------------------------------------------------

    if not actions:
        actions.append(
            "Keep the current packaging and focus on making the next video equally compelling."
        )

    return {
        "score": score,
        "health": health,
        "problems": problems,
        "positives": positives,
        "actions": actions,
        "view_velocity": view_velocity,
        "published_text": published_text
    }


# ============================================================
# TITLE DIAGNOSTIC
# ============================================================

def title_diagnosis(title):

    title = title.strip()

    if len(title) < 25:
        return "Your title is quite short. Consider adding enough context to make the premise obvious."

    if len(title) <= 65:
        return "Your title length is in a generally useful range."

    if len(title) <= 80:
        return "Your title is fairly long. Consider making it more concise."

    return "Your title is very long. A shorter, sharper version may communicate the premise faster."


# ============================================================
# HEADER
# ============================================================

st.title("🩺 YouTube Video Doctor")

st.caption(
    "Analyze CTR, impressions, retention, engagement, packaging, "
    "view velocity, and video age."
)


# ============================================================
# API KEY CHECK
# ============================================================

if not API_KEY:

    st.error(
        "YouTube API key is not configured. "
        "Add YOUTUBE_API_KEY to Streamlit Secrets."
    )

    st.stop()


# ============================================================
# URL INPUT
# ============================================================

video_url = st.text_input(
    "Paste your YouTube video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)


# ============================================================
# ANALYTICS INPUT
# ============================================================

st.subheader("📊 Your YouTube Analytics")

col1, col2, col3 = st.columns(3)

with col1:
    ctr = st.number_input(
        "CTR (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1
    )

with col2:
    impressions = st.number_input(
        "Impressions",
        min_value=0,
        value=0,
        step=100
    )

with col3:
    retention = st.number_input(
        "Average Percentage Viewed (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

analyze = st.button(
    "🔎 Analyze Video",
    type="primary",
    use_container_width=True
)


if analyze:

    # --------------------------------------------------------
    # URL CHECK
    # --------------------------------------------------------

    video_id = extract_video_id(video_url)

    if not video_id:
        st.error(
            "I couldn't recognize that YouTube URL. "
            "Try pasting the normal YouTube video link."
        )
        st.stop()

    # --------------------------------------------------------
    # RATE LIMIT
    # --------------------------------------------------------

    analysis_key = f"{video_id}:{ctr}:{impressions}:{retention}"

    allowed, message = check_rate_limit(analysis_key)

    if not allowed:

        if "already analyzed" in message.lower():
            st.info(message)
        else:
            st.warning(message)

        st.stop()

    # --------------------------------------------------------
    # YOUTUBE REQUEST
    # --------------------------------------------------------

    try:

        with st.spinner("Checking the video..."):

            video = fetch_video(video_id)

        if not video:
            st.error(
                "That video couldn't be found or isn't accessible."
            )
            st.stop()

        record_analysis(analysis_key)

    except HttpError as error:

        st.error(
            "YouTube API error. Your API quota may have been "
            "reached or the API key may have a configuration issue."
        )

        st.stop()

    except Exception as error:

        st.error(
            "Something went wrong while contacting YouTube."
        )

        st.stop()

    # --------------------------------------------------------
    # VIDEO DATA
    # --------------------------------------------------------

    snippet = video.get("snippet", {})
    statistics = video.get("statistics", {})
    content = video.get("contentDetails", {})

    title = snippet.get("title", "Untitled")
    channel_title = snippet.get("channelTitle", "Unknown channel")
    channel_id = snippet.get("channelId", "")

    thumbnail = (
        snippet.get("thumbnails", {})
        .get("high", {})
        .get("url")
    )

    published = snippet.get(
        "publishedAt",
        ""
    )

    views = int(
        statistics.get(
            "viewCount",
            0
        )
    )

    likes = int(
        statistics.get(
            "likeCount",
            0
        )
    )

    duration_seconds = parse_duration(
        content.get("duration", "")
    )

    video_type = get_video_type(
        duration_seconds
    )

    duration_text = format_duration(
        duration_seconds
    )

    # --------------------------------------------------------
    # DIAGNOSIS
    # --------------------------------------------------------

    diagnosis = calculate_diagnosis(
        ctr=ctr,
        impressions=impressions,
        retention=retention,
        views=views,
        likes=likes,
        published=published,
        duration_seconds=duration_seconds
    )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title_check = title_diagnosis(title)

    # ========================================================
    # VIDEO HEADER
    # ========================================================

    st.divider()

    st.header(title)

    st.caption(
        f"Channel: **{channel_title}**"
    )

    if video_type == "Shorts / short-form":

        st.info(
            f"📱 **{video_type}**"
        )

    else:

        st.info(
            f"🎬 **{video_type}**"
        )

    # ========================================================
    # VIDEO INFO
    # ========================================================

    info1, info2, info3 = st.columns(3)

    with info1:

        if thumbnail:
            st.image(
                thumbnail,
                use_container_width=True
            )

    with info2:

        st.metric(
            "Video Length",
            duration_text
        )

        st.metric(
            "Published",
            diagnosis["published_text"]
        )

    with info3:

        st.metric(
            "View Velocity",
            f"{diagnosis['view_velocity']:.1f}/hour"
        )

        if views > 0:

            like_rate = (
                likes / views
            ) * 100

            st.metric(
                "Like Rate",
                f"{like_rate:.2f}%"
            )

    # ========================================================
    # CURRENT PERFORMANCE
    # ========================================================

    st.subheader("📊 Current Performance")

    p1, p2, p3, p4 = st.columns(4)

    with p1:
        st.metric(
            "Views",
            f"{views:,}"
        )

    with p2:
        st.metric(
            "Likes",
            f"{likes:,}"
        )

    with p3:
        st.metric(
            "CTR",
            f"{ctr:.1f}%"
        )

    with p4:
        st.metric(
            "Impressions",
            f"{impressions:,}"
        )

    if retention > 0:

        st.metric(
            "Average Percentage Viewed",
            f"{retention:.1f}%"
        )

    # ========================================================
    # HEALTH
    # ========================================================

    st.divider()

    st.subheader("🩺 Video Health")

    h1, h2 = st.columns(2)

    with h1:

        st.metric(
            "Diagnostic Score",
            f"{diagnosis['score']}/100"
        )

    with h2:

        st.metric(
            "Overall Health",
            diagnosis["health"]
        )

    # ========================================================
    # WHAT'S WORKING
    # ========================================================

    if diagnosis["positives"]:

        st.subheader("🟢 What's Working")

        for item in diagnosis["positives"]:
            st.success(item)

    # ========================================================
    # WHAT'S HURTING
    # ========================================================

    st.subheader("🚨 What's Hurting")

    for item in diagnosis["problems"]:
        st.error(item)

    # ========================================================
    # WHAT I'D DO
    # ========================================================

    st.subheader("🎯 What I'd Do")

    for item in diagnosis["actions"]:
        st.info(item)

    # ========================================================
    # TITLE CHECK
    # ========================================================

    st.subheader("📝 Title Quick Check")

    if len(title) > 65:

        st.warning(title_check)

    elif len(title) < 25:

        st.info(title_check)

    else:

        st.success(title_check)

    # ========================================================
    # RECENT UPLOADS
    # ========================================================

    if channel_id:

        st.divider()

        st.subheader("🆕 Recent Uploads")

        try:

            recent = fetch_recent_uploads(
                channel_id
            )

            if recent:

                for item in recent:

                    published_date = item["published"]

                    try:

                        dt = datetime.fromisoformat(
                            published_date.replace(
                                "Z",
                                "+00:00"
                            )
                        )

                        date_text = dt.strftime(
                            "%Y-%m-%d"
                        )

                    except Exception:

                        date_text = ""

                    st.write(
                        f"• **{item['title']}**"
                        f" — {date_text}"
                    )

        except Exception:

            st.info(
                "Recent uploads couldn't be loaded."
            )

    # ========================================================
    # DISCLAIMER
    # ========================================================

    st.divider()

    st.caption(
        "Diagnostic scores are heuristic estimates, not official "
        "YouTube benchmarks. CTR and retention vary substantially "
        "by topic, audience, traffic source, video length, and distribution."
    )
