import re
import statistics

import streamlit as st
from googleapiclient.discovery import build


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="YouTube Video Diagnostic",
    page_icon="📊",
    layout="wide",
)

st.title("📊 YouTube Video Diagnostic")
st.caption(
    "Paste a video, enter the three YouTube Studio numbers, "
    "and get a diagnosis without filling out a giant form."
)


# ============================================================
# API
# ============================================================

YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")

if not YOUTUBE_API_KEY:
    st.error("❌ YOUTUBE_API_KEY is missing from Streamlit Secrets.")
    st.code(
        'YOUTUBE_API_KEY = "your_youtube_api_key_here"',
        language="toml"
    )
    st.stop()


@st.cache_resource
def youtube_client():
    return build(
        "youtube",
        "v3",
        developerKey=YOUTUBE_API_KEY
    )


# ============================================================
# VIDEO ID
# ============================================================

def extract_video_id(url):

    patterns = [
        r"(?:v=|youtu\.be/|youtube\.com/shorts/)"
        r"([A-Za-z0-9_-]{11})"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url or ""
        )

        if match:
            return match.group(1)

    return None


# ============================================================
# GET VIDEO
# ============================================================

@st.cache_data(ttl=600)
def get_video(video_id):

    yt = youtube_client()

    response = yt.videos().list(
        part="snippet,statistics,contentDetails",
        id=video_id
    ).execute()

    if not response.get("items"):
        return None

    item = response["items"][0]

    snippet = item["snippet"]
    stats = item.get("statistics", {})
    thumbs = snippet.get("thumbnails", {})

    thumbnail = (
        thumbs.get("maxres")
        or thumbs.get("high")
        or thumbs.get("medium")
        or thumbs.get("default")
    )

    return {

        "id":
            video_id,

        "title":
            snippet.get(
                "title",
                "Unknown title"
            ),

        "channel_title":
            snippet.get(
                "channelTitle",
                "Unknown channel"
            ),

        "channel_id":
            snippet.get(
                "channelId",
                ""
            ),

        "published_at":
            snippet.get(
                "publishedAt",
                ""
            ),

        "thumbnail":
            thumbnail["url"]
            if thumbnail
            else None,

        "views":
            int(
                stats.get(
                    "viewCount",
                    0
                )
            ),

        "likes":
            int(
                stats.get(
                    "likeCount",
                    0
                )
            ),

        "comments":
            int(
                stats.get(
                    "commentCount",
                    0
                )
            ),
    }


# ============================================================
# RECENT CHANNEL VIDEOS
# ============================================================

@st.cache_data(ttl=600)
def get_recent_videos(
    channel_id,
    limit=10
):

    yt = youtube_client()

    response = yt.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()

    if not response.get("items"):
        return []

    uploads = (
        response["items"][0]
        ["contentDetails"]
        ["relatedPlaylists"]
        ["uploads"]
    )

    playlist = yt.playlistItems().list(
        part="contentDetails,snippet",
        playlistId=uploads,
        maxResults=limit
    ).execute()

    ids = [

        item["contentDetails"].get(
            "videoId"
        )

        for item in playlist.get(
            "items",
            []
        )

        if item["contentDetails"].get(
            "videoId"
        )
    ]

    if not ids:
        return []

    details = yt.videos().list(
        part="snippet,statistics,contentDetails",
        id=",".join(ids)
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

        videos.append({

            "id":
                item["id"],

            "title":
                item["snippet"].get(
                    "title",
                    ""
                ),

            "views":
                int(
                    stats.get(
                        "viewCount",
                        0
                    )
                ),

            "likes":
                int(
                    stats.get(
                        "likeCount",
                        0
                    )
                ),

            "comments":
                int(
                    stats.get(
                        "commentCount",
                        0
                    )
                ),

            "published_at":
                item["snippet"].get(
                    "publishedAt",
                    ""
                ),
        })

    return videos


# ============================================================
# ENGAGEMENT
# ============================================================

def engagement_rate(
    views,
    likes,
    comments
):

    if views <= 0:
        return 0

    return (
        (likes + comments)
        / views
    ) * 100


# ============================================================
# CTR DIAGNOSIS
# ============================================================

def ctr_status(
    ctr,
    impressions
):

    if impressions < 500:

        if ctr >= 8:
            return (
                "🟢",
                "Promising, but the sample is tiny."
            )

        if ctr >= 5:
            return (
                "🟡",
                "Reasonable early CTR; "
                "wait for more impressions."
            )

        return (
            "🔴",
            "Low early CTR, but there isn't "
            "enough data to panic."
        )


    if impressions < 2000:

        if ctr >= 8:
            return (
                "🟢",
                "Strong CTR for an early test."
            )

        if ctr >= 5:
            return (
                "🟡",
                "Decent CTR with more data "
                "still needed."
            )

        return (
            "🔴",
            "Packaging may be limiting clicks."
        )


    if impressions < 100000:

        if ctr >= 8:
            return (
                "🟢",
                "Excellent CTR at this "
                "distribution level."
            )

        if ctr >= 6:
            return (
                "🟢",
                "Strong CTR."
            )

        if ctr >= 4:
            return (
                "🟡",
                "Average CTR; packaging "
                "has room to improve."
            )

        return (
            "🔴",
            "Low CTR; packaging is "
            "probably a bottleneck."
        )


    if ctr >= 6:

        return (
            "🟢",
            "Very strong CTR despite "
            "broad distribution."
        )

    if ctr >= 4:

        return (
            "🟡",
            "Healthy CTR for a heavily "
            "distributed video."
        )

    if ctr >= 2.5:

        return (
            "🟡",
            "Understandable at this scale, "
            "but packaging may improve."
        )

    return (
        "🔴",
        "Weak CTR even after accounting "
        "for broad distribution."
    )


# ============================================================
# RETENTION DIAGNOSIS
# ============================================================

def retention_status(
    retention
):

    if retention >= 55:

        return (
            "🟢",
            "Excellent retention."
        )

    if retention >= 45:

        return (
            "🟢",
            "Strong retention."
        )

    if retention >= 40:

        return (
            "🟡",
            "Solid retention with room "
            "to improve."
        )

    if retention >= 30:

        return (
            "🟠",
            "Retention is becoming a "
            "meaningful weakness."
        )

    return (
        "🔴",
        "Low retention; viewer drop-off "
        "is likely a major problem."
    )


# ============================================================
# ENGAGEMENT DIAGNOSIS
# ============================================================

def engagement_status(
    rate
):

    if rate >= 6:

        return (
            "🟢",
            "Excellent engagement."
        )

    if rate >= 3:

        return (
            "🟢",
            "Healthy engagement."
        )

    if rate >= 1.5:

        return (
            "🟡",
            "Average engagement."
        )

    return (
        "🔴",
        "Low engagement relative to views."
    )


# ============================================================
# CHANNEL COMPARISON
# ============================================================

def channel_comparison(
    views,
    recent
):

    if not recent:
        return None

    values = [

        video["views"]

        for video in recent

        if video["views"] >= 0
    ]

    if len(values) < 2:
        return None

    average = statistics.mean(
        values
    )

    median = statistics.median(
        values
    )

    if average <= 0:
        return None

    ratio = views / average

    if ratio >= 1.5:

        label = (
            "🔥 Well above your recent "
            "channel average"
        )

    elif ratio >= 1.0:

        label = (
            "🟢 Above your recent "
            "channel average"
        )

    elif ratio >= 0.75:

        label = (
            "🟡 Slightly below your recent "
            "channel average"
        )

    else:

        label = (
            "🔴 Significantly below your "
            "recent channel average"
        )

    return {

        "average":
            average,

        "median":
            median,

        "ratio":
            ratio,

        "label":
            label,
    }


# ============================================================
# MAIN DIAGNOSIS
# ============================================================

def diagnose(

    ctr,

    impressions,

    retention,

    views,

    likes,

    comments,

    comparison

):

    engagement = engagement_rate(
        views,
        likes,
        comments
    )

    ctr_icon, ctr_text = ctr_status(
        ctr,
        impressions
    )

    retention_icon, retention_text = (
        retention_status(
            retention
        )
    )

    engagement_icon, engagement_text = (
        engagement_status(
            engagement
        )
    )

    score = 100

    strengths = []
    problems = []
    actions = []


    # ========================================================
    # CTR
    # ========================================================

    if ctr_icon == "🟢":

        strengths.append(
            "🖼️ Packaging / click appeal"
        )

    elif ctr_icon == "🟡":

        score -= 7

    else:

        score -= 20

        problems.append(
            "🖼️ Packaging / click appeal"
        )

        actions.append((

            1,

            "Improve the thumbnail/title",

            "Your biggest click-side opportunity "
            "is packaging. Make the main idea obvious, "
            "reduce clutter, and create a stronger "
            "reason to click."

        ))


    # ========================================================
    # RETENTION
    # ========================================================

    if retention_icon == "🟢":

        strengths.append(
            "🎬 Viewer retention"
        )

    elif retention_icon == "🟡":

        score -= 5

    elif retention_icon == "🟠":

        score -= 15

        problems.append(
            "🎬 Viewer retention"
        )

        actions.append((

            1,

            "Tighten the video",

            "Get to the premise faster, "
            "remove dead sections, "
            "and improve pacing."

        ))

    else:

        score -= 30

        problems.append(
            "🎬 Viewer retention"
        )

        actions.append((

            1,

            "Fix the opening and pacing",

            "The main problem appears to happen "
            "after the click. Deliver the title/"
            "thumbnail promise faster and remove "
            "slow sections."

        ))


    # ========================================================
    # ENGAGEMENT
    # ========================================================

    if engagement_icon == "🟢":

        strengths.append(
            "💬 Engagement"
        )

    elif engagement_icon == "🟡":

        score -= 3

    else:

        score -= 8

        problems.append(
            "💬 Engagement"
        )

        actions.append((

            2,

            "Give viewers something to react to",

            "Use a natural question, prediction, "
            "challenge, or controversial choice."

        ))


    # ========================================================
    # CROSS-METRIC DIAGNOSIS
    # ========================================================

    if ctr >= 7 and retention < 35:

        headline = (
            "🚨 People are clicking, but the "
            "video isn't keeping enough of them."
        )

        priority = (
            "Fix the opening and pacing before "
            "touching the thumbnail."
        )


    elif ctr < 4.5 and retention >= 40:

        headline = (
            "🎯 The people who click are staying "
            "reasonably well, but not enough people "
            "are clicking."
        )

        priority = (
            "Work on the thumbnail/title before "
            "rebuilding the video."
        )


    elif ctr >= 7 and retention >= 40:

        headline = (
            "🔥 Both packaging and retention "
            "look healthy."
        )

        priority = (
            "Don't make drastic changes. "
            "Let distribution develop."
        )


    elif ctr < 4.5 and retention < 35:

        headline = (
            "🚨 Both packaging and viewer "
            "retention need attention."
        )

        priority = (
            "Improve the thumbnail/title first, "
            "then tighten the opening."
        )


    else:

        headline = (
            "🟡 Performance is mixed rather than "
            "having one catastrophic problem."
        )

        priority = (
            "Fix the weakest metric first "
            "instead of changing everything."
        )


    # ========================================================
    # CHANNEL COMPARISON
    # ========================================================

    if comparison:

        ratio = comparison["ratio"]

        if ratio >= 1.5:

            strengths.append(
                "📈 Views are substantially above "
                "your recent channel average"
            )

        elif ratio < 0.75:

            problems.append(
                "📉 Views are substantially below "
                "your recent channel average"
            )


    # ========================================================
    # SMALL SAMPLE
    # ========================================================

    if impressions < 2000:

        actions.append((

            3,

            "Treat this as preliminary",

            "There aren't many impressions yet. "
            "Don't make a major decision from CTR alone."

        ))


    # ========================================================
    # DON'T MESS WITH HEALTHY THINGS
    # ========================================================

    if ctr_icon == "🟢":

        actions.append((

            99,

            "Don't blindly replace the thumbnail",

            "CTR isn't showing an obvious "
            "packaging crisis."

        ))


    if retention_icon == "🟢":

        actions.append((

            99,

            "Don't completely rebuild the video",

            "Retention isn't showing an obvious "
            "viewer-experience crisis."

        ))


    # ========================================================
    # SCORE
    # ========================================================

    score = max(
        0,
        min(
            100,
            score
        )
    )


    if score >= 90:

        rating = "🔥 Excellent"

    elif score >= 80:

        rating = "🟢 Strong"

    elif score >= 65:

        rating = "🟡 Decent"

    elif score >= 50:

        rating = "🟠 Needs improvement"

    else:

        rating = "🔴 Weak"


    return {

        "score":
            score,

        "rating":
            rating,

        "headline":
            headline,

        "priority":
            priority,

        "ctr_status":
            ctr_icon,

        "ctr_text":
            ctr_text,

        "ret_status":
            retention_icon,

        "ret_text":
            retention_text,

        "eng_status":
            engagement_icon,

        "eng_text":
            engagement_text,

        "engagement":
            engagement,

        "strengths":
            strengths,

        "problems":
            problems,

        "actions":
            sorted(
                actions,
                key=lambda x: x[0]
            ),
    }


# ============================================================
# INPUT
# ============================================================

video_url = st.text_input(

    "🎬 Paste your YouTube video URL",

    placeholder=
    "https://www.youtube.com/watch?v=..."

)


st.subheader(
    "📊 Three numbers from YouTube Studio"
)


c1, c2, c3 = st.columns(3)


with c1:

    ctr = st.number_input(

        "CTR (%)",

        min_value=0.0,

        max_value=100.0,

        value=0.0,

        step=0.1

    )


with c2:

    impressions = st.number_input(

        "Impressions",

        min_value=0,

        value=0,

        step=100

    )


with c3:

    retention = st.number_input(

        "Average percentage viewed (%)",

        min_value=0.0,

        max_value=100.0,

        value=0.0,

        step=0.1

    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

if st.button(

    "🚀 Analyze",

    type="primary",

    use_container_width=True

):

    video_id = extract_video_id(
        video_url
    )


    if not video_id:

        st.error(
            "❌ Paste a valid YouTube video URL."
        )

        st.stop()


    with st.spinner(
        "Analyzing your video..."
    ):

        try:

            video = get_video(
                video_id
            )

            recent = (
                get_recent_videos(
                    video["channel_id"],
                    limit=10
                )
                if video
                else []
            )

        except Exception as exc:

            st.error(
                f"YouTube API error: {exc}"
            )

            st.stop()


    if not video:

        st.error(
            "❌ Video not found."
        )

        st.stop()


    # Remove current video from comparison.

    recent_without_current = [

        v

        for v in recent

        if v["id"] != video_id

    ]


    comparison = channel_comparison(

        video["views"],

        recent_without_current

    )


    result = diagnose(

        ctr=ctr,

        impressions=impressions,

        retention=retention,

        views=video["views"],

        likes=video["likes"],

        comments=video["comments"],

        comparison=comparison

    )


    # ========================================================
    # VIDEO HEADER
    # ========================================================

    st.divider()

    st.header(
        f"🎬 {video['title']}"
    )

    st.caption(
        f"Channel: {video['channel_title']}"
    )


    left, right = st.columns(
        [1, 2]
    )


    with left:

        if video["thumbnail"]:

            st.image(
                video["thumbnail"],
                use_container_width=True
            )


    with right:

        a, b, c = st.columns(3)

        a.metric(
            "Views",
            f"{video['views']:,}"
        )

        b.metric(
            "Likes",
            f"{video['likes']:,}"
        )

        c.metric(
            "Comments",
            f"{video['comments']:,}"
        )


        a, b, c = st.columns(3)

        a.metric(
            "CTR",
            f"{ctr:.1f}%"
        )

        b.metric(
            "Impressions",
            f"{impressions:,}"
        )

        c.metric(
            "Retention",
            f"{retention:.1f}%"
        )


    # ========================================================
    # MAIN DIAGNOSIS
    # ========================================================

    st.divider()

    st.header(
        "🧠 Diagnosis"
    )


    a, b = st.columns(
        [1, 3]
    )


    with a:

        st.metric(
            "Performance Score",
            f"{result['score']}/100"
        )


    with b:

        st.subheader(
            result["rating"]
        )

        st.write(
            result["headline"]
        )


    st.info(
        f"🎯 **What I'd fix first:** "
        f"{result['priority']}"
    )


    # ========================================================
    # CHANNEL COMPARISON
    # ========================================================

    if comparison:

        st.divider()

        st.header(
            "📈 Compared With Your Channel"
        )


        a, b, c = st.columns(3)


        a.metric(

            "Recent average views",

            f"{comparison['average']:,.0f}"

        )


        b.metric(

            "This video's ratio",

            f"{comparison['ratio']:.2f}×"

        )


        c.metric(

            "Recent median views",

            f"{comparison['median']:,.0f}"

        )


        if comparison["ratio"] >= 1.5:

            st.success(
                comparison["label"]
            )

        elif comparison["ratio"] >= 0.75:

            st.warning(
                comparison["label"]
            )

        else:

            st.error(
                comparison["label"]
            )


    # ========================================================
    # WHY
    # ========================================================

    st.divider()

    st.header(
        "🔬 Why"
    )


    st.write(

        f"**🖼️ CTR:** "
        f"{result['ctr_status']} "
        f"{result['ctr_text']}"

    )


    st.write(

        f"**🎬 Retention:** "
        f"{result['ret_status']} "
        f"{result['ret_text']}"

    )


    st.write(

        f"**💬 Engagement:** "
        f"{result['eng_status']} "
        f"{result['eng_text']}"

    )


    st.metric(

        "Engagement rate",

        f"{result['engagement']:.2f}%"

    )


    # ========================================================
    # STRENGTHS
    # ========================================================

    if result["strengths"]:

        st.divider()

        st.header(
            "💪 What's Working"
        )


        for item in result["strengths"]:

            st.success(
                item
            )


    # ========================================================
    # PROBLEMS
    # ========================================================

    if result["problems"]:

        st.divider()

        st.header(
            "🚨 What's Hurting"
        )


        for item in result["problems"]:

            st.error(
                item
            )


    # ========================================================
    # ACTION PLAN
    # ========================================================

    st.divider()

    st.header(
        "🎯 What I'd Do"
    )


    for priority, title, text in result["actions"]:

        if priority == 1:

            st.error(
                f"**{title}**\n\n{text}"
            )

        elif priority == 2:

            st.warning(
                f"**{title}**\n\n{text}"
            )

        elif priority == 3:

            st.info(
                f"**{title}**\n\n{text}"
            )

        else:

            st.caption(
                f"**{title}** — {text}"
            )


    # ========================================================
    # RECENT VIDEOS
    # ========================================================

    if recent_without_current:

        st.divider()

        st.header(
            "🆕 Your Recent Videos"
        )


        for item in recent_without_current[:5]:

            published = (
                item["published_at"][:10]
            )

            st.write(

                f"**{item['title']}** — "
                f"{item['views']:,} views — "
                f"{published}"

            )


    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    st.caption(

        "This diagnosis uses your video's metrics "
        "and recent channel performance. It is a "
        "heuristic, not an official YouTube score."

    )
