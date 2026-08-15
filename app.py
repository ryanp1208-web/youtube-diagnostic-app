import re
import statistics
from datetime import datetime, timezone

import streamlit as st
from googleapiclient.discovery import build


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="YouTube Video Doctor",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 YouTube Video Doctor")
st.caption(
    "Analyze your video's performance without AI or paid AI APIs."
)


# ============================================================
# YOUTUBE API
# ============================================================

YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")

if not YOUTUBE_API_KEY:
    st.error("❌ YOUTUBE_API_KEY is missing from Streamlit Secrets.")
    st.stop()


@st.cache_resource
def youtube_client():
    return build(
        "youtube",
        "v3",
        developerKey=YOUTUBE_API_KEY,
    )


# ============================================================
# URL / ID
# ============================================================

def extract_video_id(url):
    if not url:
        return None

    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def url_looks_like_short(url):
    return "/shorts/" in url.lower()


# ============================================================
# DURATION
# ============================================================

def parse_iso_duration(duration):
    """
    Converts YouTube ISO 8601 duration into seconds.

    Examples:
    PT45S       = 45 seconds
    PT5M20S     = 5 minutes 20 seconds
    PT1H12M     = 1 hour 12 minutes
    """

    if not duration:
        return 0

    match = re.match(
        r"PT"
        r"(?:(\d+)H)?"
        r"(?:(\d+)M)?"
        r"(?:(\d+)S)?",
        duration,
    )

    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )


def format_duration(seconds):

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"

    if minutes > 0:
        return f"{minutes}m {secs}s"

    return f"{secs}s"


# ============================================================
# VIDEO AGE
# ============================================================

def calculate_video_age(published_at):

    try:
        published = datetime.fromisoformat(
            published_at.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        difference = now - published

        seconds = max(
            0,
            int(difference.total_seconds())
        )

        return seconds

    except Exception:
        return None


def format_age(seconds):

    if seconds is None:
        return "Unknown"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"

    if hours > 0:
        return f"{hours}h {minutes}m"

    return f"{minutes}m"


# ============================================================
# SHORT DETECTION
# ============================================================

def determine_video_type(
    url,
    duration_seconds,
):

    # Strongest clue available to this app:
    # the URL itself is /shorts/
    if url_looks_like_short(url):

        return {
            "type": "short",
            "confidence": "HIGH",
            "label": "📱 YouTube Short",
        }

    # Otherwise, videos <= 3 minutes are treated as
    # Shorts candidates. This is NOT a guaranteed classification.
    if duration_seconds <= 180:

        return {
            "type": "short_candidate",
            "confidence": "ESTIMATED",
            "label": "📱 Shorts candidate",
        }

    return {
        "type": "long_form",
        "confidence": "HIGH",
        "label": "🎬 Long-form video",
    }


# ============================================================
# GET VIDEO
# ============================================================

@st.cache_data(ttl=300)
def get_video(video_id):

    yt = youtube_client()

    response = yt.videos().list(
        part="snippet,statistics,contentDetails",
        id=video_id,
    ).execute()

    if not response.get("items"):
        return None

    item = response["items"][0]

    snippet = item["snippet"]
    stats = item.get("statistics", {})
    content = item.get("contentDetails", {})

    thumbnails = snippet.get(
        "thumbnails",
        {}
    )

    thumbnail = (
        thumbnails.get("maxres")
        or thumbnails.get("high")
        or thumbnails.get("medium")
        or thumbnails.get("default")
    )

    duration_seconds = parse_iso_duration(
        content.get("duration", "")
    )

    published_at = snippet.get(
        "publishedAt",
        ""
    )

    age_seconds = calculate_video_age(
        published_at
    )

    return {
        "id": video_id,

        "title": snippet.get(
            "title",
            "Unknown title"
        ),

        "channel_title": snippet.get(
            "channelTitle",
            "Unknown channel"
        ),

        "channel_id": snippet.get(
            "channelId",
            ""
        ),

        "published_at": published_at,

        "age_seconds": age_seconds,

        "duration_seconds": duration_seconds,

        "duration": format_duration(
            duration_seconds
        ),

        "thumbnail": (
            thumbnail["url"]
            if thumbnail
            else None
        ),

        "views": int(
            stats.get(
                "viewCount",
                0
            )
        ),

        "likes": int(
            stats.get(
                "likeCount",
                0
            )
        ),

        "comments": int(
            stats.get(
                "commentCount",
                0
            )
        ),
    }


# ============================================================
# RECENT CHANNEL VIDEOS
# ============================================================

@st.cache_data(ttl=300)
def get_recent_videos(
    channel_id,
    limit=20,
):

    yt = youtube_client()

    channel_response = yt.channels().list(
        part="contentDetails",
        id=channel_id,
    ).execute()

    if not channel_response.get("items"):
        return []

    uploads_playlist = (
        channel_response["items"][0]
        ["contentDetails"]
        ["relatedPlaylists"]
        ["uploads"]
    )

    playlist_response = yt.playlistItems().list(
        part="contentDetails,snippet",
        playlistId=uploads_playlist,
        maxResults=limit,
    ).execute()

    ids = []

    for item in playlist_response.get(
        "items",
        []
    ):

        video_id = item[
            "contentDetails"
        ].get("videoId")

        if video_id:
            ids.append(video_id)

    if not ids:
        return []

    details = yt.videos().list(
        part="snippet,statistics,contentDetails",
        id=",".join(ids),
    ).execute()

    videos = []

    for item in details.get(
        "items",
        []
    ):

        stats = item.get(
            "statistics",
            {}
        )

        duration_seconds = parse_iso_duration(
            item.get(
                "contentDetails",
                {}
            ).get(
                "duration",
                ""
            )
        )

        videos.append({
            "id": item["id"],

            "title": item["snippet"].get(
                "title",
                ""
            ),

            "views": int(
                stats.get(
                    "viewCount",
                    0
                )
            ),

            "likes": int(
                stats.get(
                    "likeCount",
                    0
                )
            ),

            "comments": int(
                stats.get(
                    "commentCount",
                    0
                )
            ),

            "published_at": item["snippet"].get(
                "publishedAt",
                ""
            ),

            "duration_seconds": duration_seconds,
        })

    return videos


# ============================================================
# CALCULATIONS
# ============================================================

def engagement_rate(
    views,
    likes,
    comments,
):

    if views <= 0:
        return 0

    return (
        (likes + comments)
        / views
    ) * 100


def calculate_channel_stats(
    current_views,
    videos,
):

    if not videos:
        return None

    values = [
        v["views"]
        for v in videos
        if v["views"] >= 0
    ]

    if not values:
        return None

    average = statistics.mean(values)
    median = statistics.median(values)
    best = max(values)

    sorted_values = sorted(
        values,
        reverse=True,
    )

    top_three = statistics.mean(
        sorted_values[
            :min(3, len(sorted_values))
        ]
    )

    return {
        "average": average,
        "median": median,
        "best": best,
        "top_three": top_three,

        "ratio": (
            current_views / average
            if average > 0
            else 0
        ),

        "count": len(values),
    }


# ============================================================
# SHORTS CHANNEL COMPARISON
# ============================================================

def is_shortish(video):

    return video["duration_seconds"] <= 180


def get_short_comparison(
    current_views,
    recent_videos,
):

    shorts = [
        video
        for video in recent_videos
        if is_shortish(video)
    ]

    if not shorts:
        return None

    values = [
        video["views"]
        for video in shorts
    ]

    average = statistics.mean(values)
    best = max(values)

    return {
        "count": len(values),
        "average": average,
        "best": best,
        "ratio": (
            current_views / average
            if average > 0
            else 0
        ),
    }


# ============================================================
# VELOCITY
# ============================================================

def calculate_velocity(
    views,
    age_seconds,
):

    if not age_seconds or age_seconds <= 0:
        return None

    hours = age_seconds / 3600

    if hours <= 0:
        return None

    return views / hours


def format_velocity(
    views_per_hour,
):

    if views_per_hour is None:
        return "Unknown"

    if views_per_hour >= 1000000:
        return f"{views_per_hour / 1000000:.2f}M/hour"

    if views_per_hour >= 1000:
        return f"{views_per_hour / 1000:.1f}K/hour"

    return f"{views_per_hour:.0f}/hour"


# ============================================================
# HEALTH SCORES
# ============================================================

def ctr_score(
    ctr,
    impressions,
):

    if impressions < 500:

        if ctr >= 8:
            return 75

        if ctr >= 5:
            return 60

        return 40

    if ctr >= 10:
        return 100

    if ctr >= 8:
        return 90

    if ctr >= 6:
        return 80

    if ctr >= 4.5:
        return 65

    if ctr >= 3:
        return 45

    return 25


def retention_score(
    retention,
):

    if retention >= 60:
        return 100

    if retention >= 50:
        return 90

    if retention >= 45:
        return 82

    if retention >= 40:
        return 74

    if retention >= 35:
        return 62

    if retention >= 30:
        return 50

    if retention >= 20:
        return 30

    return 15


def impressions_score(
    impressions,
):

    if impressions >= 100000:
        return 100

    if impressions >= 50000:
        return 95

    if impressions >= 20000:
        return 90

    if impressions >= 10000:
        return 82

    if impressions >= 5000:
        return 72

    if impressions >= 2000:
        return 60

    if impressions >= 1000:
        return 48

    return 30


def engagement_score(
    engagement,
):

    if engagement >= 8:
        return 100

    if engagement >= 5:
        return 90

    if engagement >= 3:
        return 78

    if engagement >= 2:
        return 65

    if engagement >= 1:
        return 50

    return 30


def health_label(score):

    if score >= 90:
        return "🔥 Excellent"

    if score >= 80:
        return "🟢 Strong"

    if score >= 65:
        return "🟡 Decent"

    if score >= 50:
        return "🟠 Needs improvement"

    return "🔴 Weak"


# ============================================================
# TITLE ANALYSIS
# ============================================================

def analyze_title(title):

    score = 100
    checks = []

    length = len(title)

    if length > 80:

        score -= 25

        checks.append(
            "⚠️ Title is very long."
        )

    elif length > 65:

        score -= 10

        checks.append(
            "🟡 Title is somewhat long."
        )

    else:

        checks.append(
            "🟢 Title length looks reasonable."
        )

    if title.isupper() and len(title) > 10:

        score -= 10

        checks.append(
            "⚠️ Entire title is uppercase."
        )

    return {
        "score": max(0, score),
        "checks": checks,
    }


# ============================================================
# BOTTLENECK
# ============================================================

def determine_bottleneck(
    ctr,
    impressions,
    retention,
    channel_stats,
    is_short,
):

    if is_short:

        # Shorts don't rely on the same traditional
        # thumbnail/CTR model as long-form videos.

        if retention < 50:

            return {
                "title": "Retention is the biggest concern",
                "reason": (
                    "For this Short, viewer retention is more "
                    "useful than treating traditional CTR as "
                    "the main diagnosis."
                ),
                "action": (
                    "Improve the opening, pacing, payoff, "
                    "and rewatchability."
                ),
                "type": "retention",
            }

        if channel_stats and channel_stats["ratio"] < 0.6:

            return {
                "title": "Shorts distribution is weak",
                "reason": (
                    "This Short is receiving significantly fewer "
                    "views than your recent comparable uploads."
                ),
                "action": (
                    "Study the topic, opening, pacing, and "
                    "viewer response of your stronger Shorts."
                ),
                "type": "distribution",
            }

        return {
            "title": "Short is showing healthy signals",
            "reason": (
                "There isn't one obvious major weakness "
                "from the data provided."
            ),
            "action": (
                "Keep monitoring its view velocity."
            ),
            "type": "healthy",
        }


    # LONG-FORM

    if impressions < 500:

        return {
            "title": "Not enough data yet",
            "reason": (
                "The video hasn't received enough impressions "
                "to make a reliable packaging diagnosis."
            ),
            "action": (
                "Wait for more data before making major changes."
            ),
            "type": "data",
        }


    if ctr < 4.5 and retention >= 40:

        return {
            "title": "Packaging is the main bottleneck",
            "reason": (
                "People who click appear reasonably interested, "
                "but the click-through rate is weak."
            ),
            "action": (
                "Test the thumbnail/title combination."
            ),
            "type": "packaging",
        }


    if ctr >= 7 and retention < 35:

        return {
            "title": "Retention is the main bottleneck",
            "reason": (
                "People are clicking, but many are leaving."
            ),
            "action": (
                "Improve the opening, pacing, and payoff."
            ),
            "type": "retention",
        }


    if (
        channel_stats
        and channel_stats["ratio"] < 0.6
        and ctr >= 5
    ):

        return {
            "title": "Distribution is the main bottleneck",
            "reason": (
                "CTR is reasonably healthy, but the video is "
                "performing well below your recent view average."
            ),
            "action": (
                "Don't immediately blame the thumbnail. "
                "Monitor impressions and topic performance."
            ),
            "type": "distribution",
        }


    if ctr < 4.5 and retention < 35:

        return {
            "title": "Packaging and retention both need work",
            "reason": (
                "The video is struggling to generate clicks "
                "and keep viewers."
            ),
            "action": (
                "Improve packaging first, then work on the opening."
            ),
            "type": "both",
        }


    return {
        "title": "Performance is mixed",
        "reason": (
            "There isn't one overwhelmingly weak metric."
        ),
        "action": (
            "Focus on whichever metric is furthest below "
            "your normal performance."
        ),
        "type": "mixed",
    }


# ============================================================
# INPUT
# ============================================================

st.subheader("🎬 Analyze a Video")

video_url = st.text_input(
    "Paste your YouTube URL",
    placeholder="https://www.youtube.com/watch?v=..."
)


# ============================================================
# STUDIO METRICS
# ============================================================

st.subheader(
    "📊 YouTube Studio Metrics"
)

st.caption(
    "These are still entered from YouTube Studio because "
    "private analytics such as CTR and impressions require "
    "channel-owner authentication."
)

c1, c2, c3 = st.columns(3)

with c1:

    ctr = st.number_input(
        "CTR (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1,
    )

with c2:

    impressions = st.number_input(
        "Impressions",
        min_value=0,
        value=0,
        step=100,
    )

with c3:

    retention = st.number_input(
        "Average percentage viewed (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1,
    )


# ============================================================
# ANALYZE
# ============================================================

if st.button(
    "🩺 Diagnose Video",
    type="primary",
    use_container_width=True,
):

    video_id = extract_video_id(
        video_url
    )

    if not video_id:

        st.error(
            "❌ Please enter a valid YouTube video URL."
        )

        st.stop()


    with st.spinner(
        "Pulling video information..."
    ):

        try:

            video = get_video(
                video_id
            )

            if not video:

                st.error(
                    "❌ Video could not be found."
                )

                st.stop()


            recent = get_recent_videos(
                video["channel_id"],
                20,
            )

        except Exception as error:

            st.error(
                f"❌ YouTube API error: {error}"
            )

            st.stop()


    # ========================================================
    # VIDEO TYPE
    # ========================================================

    video_type = determine_video_type(
        video_url,
        video["duration_seconds"],
    )

    is_short = video_type["type"] in [
        "short",
        "short_candidate",
    ]


    # ========================================================
    # COMPARISON
    # ========================================================

    other_videos = [
        v
        for v in recent
        if v["id"] != video_id
    ]


    if is_short:

        channel_stats = get_short_comparison(
            video["views"],
            other_videos,
        )

    else:

        channel_stats = calculate_channel_stats(
            video["views"],
            other_videos,
        )


    # ========================================================
    # AGE / VELOCITY
    # ========================================================

    age_seconds = video[
        "age_seconds"
    ]

    velocity = calculate_velocity(
        video["views"],
        age_seconds,
    )


    # ========================================================
    # ENGAGEMENT
    # ========================================================

    engagement = engagement_rate(
        video["views"],
        video["likes"],
        video["comments"],
    )


    # ========================================================
    # BOTTLENECK
    # ========================================================

    bottleneck = determine_bottleneck(
        ctr,
        impressions,
        retention,
        channel_stats,
        is_short,
    )


    # ========================================================
    # TITLE
    # ========================================================

    title_analysis = analyze_title(
        video["title"]
    )


    # ========================================================
    # HEALTH
    # ========================================================

    c_score = ctr_score(
        ctr,
        impressions,
    )

    r_score = retention_score(
        retention,
    )

    i_score = impressions_score(
        impressions,
    )

    e_score = engagement_score(
        engagement,
    )


    if channel_stats:

        ratio = channel_stats["ratio"]

        if ratio >= 1.5:
            channel_score = 100
        elif ratio >= 1:
            channel_score = 80
        elif ratio >= 0.75:
            channel_score = 65
        elif ratio >= 0.5:
            channel_score = 45
        else:
            channel_score = 25

    else:

        channel_score = 50


    # For Shorts, reduce the importance of traditional CTR
    # because this is not a perfect apples-to-apples signal.

    if is_short:

        health = round(
            r_score * 0.35
            + channel_score * 0.30
            + e_score * 0.20
            + i_score * 0.15
        )

    else:

        health = round(
            c_score * 0.30
            + r_score * 0.30
            + i_score * 0.15
            + e_score * 0.10
            + channel_score * 0.15
        )


    # ========================================================
    # HEADER
    # ========================================================

    st.divider()

    st.header(
        video["title"]
    )

    st.caption(
        f"Channel: {video['channel_title']}"
    )


    # ========================================================
    # TYPE
    # ========================================================

    if video_type["type"] == "short":

        st.success(
            "📱 **YouTube Short detected from the URL.**"
        )

    elif video_type["type"] == "short_candidate":

        st.warning(
            "📱 **Shorts candidate:** this video is 3 minutes "
            "or shorter. Its exact Shorts classification "
            "cannot be confirmed from the public API metadata."
        )

    else:

        st.info(
            "🎬 **Long-form mode**"
        )


    # ========================================================
    # THUMBNAIL
    # ========================================================

    left, right = st.columns(
        [1, 2]
    )

    with left:

        if video["thumbnail"]:

            st.image(
                video["thumbnail"],
                use_container_width=True,
            )


    with right:

        # ----------------------------------------------------
        # AUTOMATIC VIDEO INFORMATION
        # ----------------------------------------------------

        st.subheader(
            "⏱️ Video Information"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Video Length",
            video["duration"],
        )

        c2.metric(
            "Age",
            format_age(
                age_seconds
            ),
        )

        c3.metric(
            "Views",
            f"{video['views']:,}",
        )


        if video["published_at"]:

            try:

                published = datetime.fromisoformat(
                    video["published_at"].replace(
                        "Z",
                        "+00:00"
                    )
                )

                st.write(
                    "**Published:** "
                    + published.strftime(
                        "%B %d, %Y at %I:%M %p UTC"
                    )
                )

            except Exception:

                pass


        if velocity is not None:

            st.metric(
                "View Velocity",
                format_velocity(
                    velocity
                ),
            )


    # ========================================================
    # METRICS
    # ========================================================

    st.divider()

    st.header(
        "📊 Current Performance"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Views",
        f"{video['views']:,}",
    )

    c2.metric(
        "Likes",
        f"{video['likes']:,}",
    )

    c3.metric(
        "Comments",
        f"{video['comments']:,}",
    )

    c4.metric(
        "Engagement",
        f"{engagement:.2f}%",
    )


    # ========================================================
    # LONG-FORM / SHORTS METRICS
    # ========================================================

    if is_short:

        st.subheader(
            "📱 Shorts Performance"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Views",
            f"{video['views']:,}",
        )

        c2.metric(
            "Views / Hour",
            format_velocity(
                velocity
            ),
        )

        c3.metric(
            "Retention",
            f"{retention:.1f}%",
        )

        if channel_stats:

            st.info(
                f"Your recent comparable Shorts average "
                f"**{channel_stats['average']:,.0f} views**."
            )

    else:

        st.subheader(
            "🎬 Long-form Performance"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "CTR",
            f"{ctr:.1f}%",
        )

        c2.metric(
            "Impressions",
            f"{impressions:,}",
        )

        c3.metric(
            "Retention",
            f"{retention:.1f}%",
        )


    # ========================================================
    # HEALTH
    # ========================================================

    st.divider()

    st.header(
        "🩺 Video Health"
    )

    st.metric(
        "Health Score",
        f"{health}/100",
    )

    st.subheader(
        health_label(health)
    )


    # ========================================================
    # COMPONENT SCORES
    # ========================================================

    st.subheader(
        "Component Scores"
    )

    if is_short:

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Retention",
            f"{r_score}/100",
        )

        c2.metric(
            "Channel",
            f"{channel_score}/100",
        )

        c3.metric(
            "Engagement",
            f"{e_score}/100",
        )

        c4.metric(
            "Distribution",
            f"{i_score}/100",
        )

    else:

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric(
            "CTR",
            f"{c_score}/100",
        )

        c2.metric(
            "Retention",
            f"{r_score}/100",
        )

        c3.metric(
            "Impressions",
            f"{i_score}/100",
        )

        c4.metric(
            "Engagement",
            f"{e_score}/100",
        )

        c5.metric(
            "Channel",
            f"{channel_score}/100",
        )


    # ========================================================
    # PRIMARY DIAGNOSIS
    # ========================================================

    st.divider()

    st.header(
        "🚨 What's Actually Holding This Video Back?"
    )

    if bottleneck["type"] == "healthy":

        st.success(
            f"🟢 **{bottleneck['title']}**\n\n"
            f"{bottleneck['reason']}\n\n"
            f"**What to do:** {bottleneck['action']}"
        )

    elif bottleneck["type"] == "data":

        st.info(
            f"⚪ **{bottleneck['title']}**\n\n"
            f"{bottleneck['reason']}\n\n"
            f"**What to do:** {bottleneck['action']}"
        )

    else:

        st.warning(
            f"🔴 **{bottleneck['title']}**\n\n"
            f"{bottleneck['reason']}\n\n"
            f"**What to do:** {bottleneck['action']}"
        )


    # ========================================================
    # CHANNEL COMPARISON
    # ========================================================

    if channel_stats:

        st.divider()

        if is_short:

            st.header(
                "📱 Compared With Your Other Shorts"
            )

        else:

            st.header(
                "🆚 Compared With Your Channel"
            )


        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Your Average",
            f"{channel_stats['average']:,.0f}",
        )

        c2.metric(
            "This Video",
            f"{channel_stats['ratio']:.2f}×",
        )

        c3.metric(
            "Your Best",
            f"{channel_stats['best']:,}",
        )


        ratio = channel_stats["ratio"]


        if ratio >= 1.5:

            st.success(
                "🔥 This video is performing substantially "
                "above your recent comparison group."
            )

        elif ratio >= 1:

            st.success(
                "🟢 This video is around or above your normal performance."
            )

        elif ratio >= 0.75:

            st.warning(
                "🟡 This video is somewhat below your normal performance."
            )

        else:

            st.error(
                "🔴 This video is substantially below your normal performance."
            )


    # ========================================================
    # MOMENTUM
    # ========================================================

    st.divider()

    st.header(
        "🚀 Momentum"
    )

    if age_seconds is not None:

        if age_seconds < 6 * 3600:

            st.info(
                "🕐 **Very early:** this video has been live for "
                "less than 6 hours. Avoid making major conclusions yet."
            )

        elif age_seconds < 24 * 3600:

            st.info(
                "🟡 **Early:** the video has been live for less "
                "than a day. Momentum can still change considerably."
            )

        elif age_seconds < 3 * 86400:

            st.warning(
                "🟠 **Developing:** enough time has passed for "
                "an early comparison, but performance can still change."
            )

        else:

            st.success(
                "🟢 **Established:** the video has been live long "
                "enough for a more meaningful performance comparison."
            )


    if velocity is not None:

        st.write(
            f"Current view velocity: **{format_velocity(velocity)}**"
        )


    # ========================================================
    # TITLE
    # ========================================================

    st.divider()

    st.header(
        "📝 Title Check"
    )

    st.write(
        f"**{video['title']}**"
    )

    st.metric(
        "Title Score",
        f"{title_analysis['score']}/100",
    )

    for check in title_analysis["checks"]:

        if check.startswith("🟢"):

            st.success(check)

        else:

            st.warning(check)


    # ========================================================
    # THUMBNAIL
    # ========================================================

    st.divider()

    st.header(
        "🖼️ Thumbnail Check"
    )

    if is_short:

        st.info(
            "For Shorts, don't treat traditional CTR/thumbnail "
            "diagnosis exactly like long-form videos."
        )

    if video["thumbnail"]:

        st.success(
            "🟢 Thumbnail successfully retrieved."
        )

        st.info(
            "The no-AI version does not claim to judge artistic "
            "quality. It uses your actual performance data to "
            "decide whether packaging is likely worth investigating."
        )

    else:

        st.error(
            "❌ Thumbnail could not be retrieved."
        )


    # ========================================================
    # ACTION PLAN
    # ========================================================

    st.divider()

    st.header(
        "🎯 What I Would Do"
    )


    if bottleneck["type"] == "packaging":

        st.markdown(
            """
            ### 🥇 Improve the thumbnail/title

            Your CTR is the biggest weakness.

            ### 🥈 Keep the actual video concept

            Your retention suggests people who click are reasonably interested.

            ### 🥉 Test one packaging change at a time

            Don't change five things simultaneously.
            """
        )


    elif bottleneck["type"] == "retention":

        st.markdown(
            """
            ### 🥇 Fix the opening

            Get to the main premise faster.

            ### 🥈 Improve pacing

            Remove unnecessary sections and dead time.

            ### 🥉 Don't immediately change the thumbnail

            If people are clicking, the packaging may already be doing its job.
            """
        )


    elif bottleneck["type"] == "distribution":

        st.markdown(
            """
            ### 🥇 Don't panic

            Low distribution does not automatically mean the video is bad.

            ### 🥈 Watch the trend

            Keep monitoring impressions/views.

            ### 🥉 Study the topic

            Compare the subject against your strongest uploads.
            """
        )


    elif bottleneck["type"] == "both":

        st.markdown(
            """
            ### 🥇 Fix packaging

            Get more people interested in clicking.

            ### 🥈 Fix the opening

            Once they click, make sure the video immediately delivers.

            ### 🥉 Don't change everything at once

            Improve the biggest problem first.
            """
        )


    elif bottleneck["type"] == "data":

        st.markdown(
            """
            ### 🥇 Wait

            There isn't enough data yet.

            ### 🥈 Monitor the next few hours

            Watch impressions, views, and retention.

            ### 🥉 Don't panic-change anything

            Early numbers can be misleading.
            """
        )


    else:

        st.markdown(
            """
            ### 🥇 Keep monitoring

            There isn't one catastrophic problem.

            ### 🥈 Study your winners

            Compare this upload with your strongest videos.

            ### 🥉 Test one variable

            Keep experimenting without destroying what already works.
            """
        )


    # ========================================================
    # DON'T CHANGE
    # ========================================================

    st.divider()

    st.header(
        "🚫 What I Would NOT Change"
    )

    if bottleneck["type"] == "retention":

        st.success(
            "🖼️ Don't immediately replace the thumbnail. "
            "Your viewers are clicking."
        )

    elif bottleneck["type"] == "packaging":

        st.success(
            "🎬 Don't immediately rewrite the entire video. "
            "The content appears capable of holding viewers."
        )

    elif bottleneck["type"] == "distribution":

        st.success(
            "🖼️ Don't automatically blame the thumbnail. "
            "Your CTR is relatively healthy."
        )

    elif bottleneck["type"] == "data":

        st.info(
            "⏳ Don't make major changes yet."
        )

    else:

        st.success(
            "⚖️ Don't change everything at once."
        )


    # ========================================================
    # RECENT VIDEOS
    # ========================================================

    if other_videos:

        st.divider()

        st.header(
            "🏆 Recent Uploads"
        )

        for item in other_videos[:10]:

            item_date = item[
                "published_at"
            ][:10]

            duration = format_duration(
                item["duration_seconds"]
            )

            st.write(
                f"**{item['title']}**  \n"
                f"👁️ {item['views']:,} views • "
                f"⏱️ {duration} • "
                f"📅 {item_date}"
            )


    # ========================================================
    # LIMITATIONS
    # ========================================================

    st.divider()

    with st.expander(
        "ℹ️ How this works"
    ):

        st.write(
            """
            **Automatically retrieved:**

            • Video title
            • Thumbnail
            • Views
            • Likes
            • Comments
            • Video duration
            • Publication date
            • How long the video has been live
            • Recent public uploads
            • Comparable Shorts performance

            **Entered from YouTube Studio:**

            • CTR
            • Impressions
            • Average percentage viewed

            Private YouTube Studio analytics require authenticated
            access to the channel, so this app does not pretend that
            a public video URL can provide those private metrics.
            """
        )


    st.success(
        "🩺 Diagnosis complete — no OpenAI or Gemini API required."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "YouTube Video Doctor • Performance recommendations are "
    "diagnostic estimates, not official YouTube ranking rules."
)
