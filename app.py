import re
from datetime import datetime, timezone

import streamlit as st
from googleapiclient.discovery import build


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube Video Diagnostic",
    page_icon="📊",
    layout="wide",
)

YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")


# ============================================================
# HELPERS
# ============================================================

def extract_video_id(url: str):
    patterns = [
        r"(?:v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url or "")
        if match:
            return match.group(1)

    return None


def youtube_client():
    return build(
        "youtube",
        "v3",
        developerKey=YOUTUBE_API_KEY
    )


def get_video(video_id: str):
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
        "id": video_id,
        "title": snippet.get("title", "Unknown title"),
        "channel_title": snippet.get(
            "channelTitle",
            "Unknown channel"
        ),
        "channel_id": snippet.get(
            "channelId",
            ""
        ),
        "published_at": snippet.get(
            "publishedAt",
            ""
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


def get_recent_uploads(
    channel_id: str,
    limit: int = 5
):
    yt = youtube_client()

    channel_response = yt.channels().list(
        part="contentDetails,statistics",
        id=channel_id
    ).execute()

    if not channel_response.get("items"):
        return []

    channel = channel_response["items"][0]

    uploads_id = (
        channel["contentDetails"]
        ["relatedPlaylists"]
        ["uploads"]
    )

    response = yt.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=uploads_id,
        maxResults=limit
    ).execute()

    videos = []

    for item in response.get(
        "items",
        []
    ):

        video_id = (
            item["contentDetails"]
            .get("videoId")
        )

        if not video_id:
            continue

        try:

            video = get_video(
                video_id
            )

            if video:
                videos.append(video)

        except Exception:
            continue

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
        return 0.0

    return (
        (likes + comments)
        / views
    ) * 100


def engagement_diagnosis(
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
# CTR DIAGNOSIS
# ============================================================

def ctr_diagnosis(
    ctr,
    impressions
):

    if impressions < 500:

        if ctr >= 8:

            return (
                "🟢",
                "Promising CTR, but the sample "
                "is too small for a strong conclusion."
            )

        if ctr >= 5:

            return (
                "🟡",
                "Reasonable early CTR. Wait for "
                "more impressions before judging "
                "the packaging."
            )

        return (
            "🔴",
            "Low early CTR, but the sample is "
            "too small to panic over."
        )

    if impressions < 2000:

        if ctr >= 8:

            return (
                "🟢",
                "Strong CTR for a small "
                "distribution sample."
            )

        if ctr >= 5:

            return (
                "🟡",
                "Decent CTR, with more data needed."
            )

        return (
            "🔴",
            "Packaging may be limiting clicks."
        )

    if impressions < 100000:

        if ctr >= 8:

            return (
                "🟢",
                "Excellent CTR at this level "
                "of distribution."
            )

        if ctr >= 6:

            return (
                "🟢",
                "Strong CTR."
            )

        if ctr >= 4:

            return (
                "🟡",
                "Average CTR. There is room "
                "to improve the title/thumbnail."
            )

        return (
            "🔴",
            "Low CTR. Packaging is a "
            "likely bottleneck."
        )

    if ctr >= 6:

        return (
            "🟢",
            "Very strong CTR despite broad "
            "distribution."
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
            "Understandable CTR at large scale, "
            "but packaging may still improve."
        )

    return (
        "🔴",
        "Weak CTR even considering the "
        "large amount of distribution."
    )


# ============================================================
# RETENTION DIAGNOSIS
# ============================================================

def retention_diagnosis(
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
            "Solid retention with some "
            "room for improvement."
        )

    if retention >= 30:

        return (
            "🟠",
            "Retention is becoming a "
            "meaningful weakness."
        )

    return (
        "🔴",
        "Low retention. Viewer drop-off "
        "is likely a major issue."
    )


# ============================================================
# MAIN DIAGNOSIS
# ============================================================

def diagnose(
    ctr,
    impressions,
    retention,
    views,
    likes,
    comments
):

    score = 100

    problems = []
    strengths = []
    actions = []

    ctr_status, ctr_text = ctr_diagnosis(
        ctr,
        impressions
    )

    ret_status, ret_text = retention_diagnosis(
        retention
    )

    engagement = engagement_rate(
        views,
        likes,
        comments
    )

    eng_status, eng_text = engagement_diagnosis(
        engagement
    )

    # --------------------------------------------------------
    # CTR
    # --------------------------------------------------------

    if ctr_status == "🟢":

        strengths.append(
            "🖼️ Packaging / click appeal"
        )

    elif ctr_status == "🟡":

        score -= 7

    else:

        score -= 20

        problems.append(
            "🖼️ Packaging / click appeal"
        )

        actions.append(
            (
                1,
                "Improve the thumbnail and title",
                "Use one obvious focal point, stronger "
                "contrast, less clutter, and a title/"
                "thumbnail combination that creates "
                "curiosity without confusion."
            )
        )

    # --------------------------------------------------------
    # RETENTION
    # --------------------------------------------------------

    if ret_status == "🟢":

        strengths.append(
            "🎬 Viewer retention"
        )

    elif ret_status == "🟡":

        score -= 5

    elif ret_status == "🟠":

        score -= 15

        problems.append(
            "🎬 Viewer retention"
        )

        actions.append(
            (
                1,
                "Tighten the video",
                "Get to the premise faster, remove "
                "dead time, improve pacing, and make "
                "sure the opening immediately delivers "
                "the promise of the title and thumbnail."
            )
        )

    else:

        score -= 30

        problems.append(
            "🎬 Viewer retention"
        )

        actions.append(
            (
                1,
                "Fix the opening and pacing",
                "The biggest opportunity is keeping "
                "viewers after they click. Cut slow "
                "sections and deliver the main premise "
                "earlier."
            )
        )

    # --------------------------------------------------------
    # ENGAGEMENT
    # --------------------------------------------------------

    if eng_status == "🟢":

        strengths.append(
            "💬 Engagement"
        )

    elif eng_status == "🟡":

        score -= 3

    else:

        score -= 8

        problems.append(
            "💬 Engagement"
        )

        actions.append(
            (
                2,
                "Increase natural viewer interaction",
                "Give viewers something worth reacting "
                "to: a question, prediction, controversial "
                "choice, challenge, or clear moment to discuss."
            )
        )

    # ========================================================
    # CROSS-METRIC ANALYSIS
    # ========================================================

    if ctr >= 7 and retention < 35:

        headline = (
            "🚨 People are clicking, but the video "
            "isn't keeping enough of them."
        )

        priority = (
            "Fix the opening, pacing, and payoff "
            "before changing the thumbnail."
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
            "🔥 Both packaging and retention look healthy."
        )

        priority = (
            "Avoid drastic changes. Let distribution develop."
        )

    elif ctr < 4.5 and retention < 35:

        headline = (
            "🚨 Both packaging and viewer retention "
            "need attention."
        )

        priority = (
            "Improve the thumbnail/title first, "
            "then improve the opening and pacing."
        )

    else:

        headline = (
            "🟡 Performance is mixed rather than "
            "having one catastrophic problem."
        )

        priority = (
            "Fix the weakest metric first instead "
            "of changing everything."
        )

    # ========================================================
    # DON'T CHANGE THINGS UNNECESSARILY
    # ========================================================

    if (
        ctr_status == "🟢"
        and not any(
            "Packaging" in p
            for p in problems
        )
    ):

        actions.append(
            (
                99,
                "Don't blindly replace the thumbnail",
                "CTR isn't showing an obvious packaging "
                "crisis. A drastic thumbnail change could hurt."
            )
        )

    if ret_status == "🟢":

        actions.append(
            (
                99,
                "Don't completely rebuild the video",
                "Retention isn't showing an obvious "
                "viewer-experience crisis."
            )
        )

    if impressions < 2000:

        actions.append(
            (
                3,
                "Treat the result as preliminary",
                "There are not many impressions yet. "
                "Avoid making major decisions from CTR alone."
            )
        )

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
        "score": score,
        "rating": rating,
        "headline": headline,
        "priority": priority,
        "ctr_status": ctr_status,
        "ctr_text": ctr_text,
        "ret_status": ret_status,
        "ret_text": ret_text,
        "eng_status": eng_status,
        "eng_text": eng_text,
        "engagement": engagement,
        "problems": problems,
        "strengths": strengths,
        "actions": sorted(
            actions,
            key=lambda x: x[0]
        ),
    }


# ============================================================
# APP
# ============================================================

st.title(
    "📊 YouTube Video Diagnostic"
)

st.write(
    "Enter your YouTube Studio numbers and this app "
    "will diagnose the likely bottleneck: packaging, "
    "retention, engagement, or simply lack of data."
)


# ============================================================
# API KEY CHECK
# ============================================================

if not YOUTUBE_API_KEY:

    st.error(
        "❌ YOUTUBE_API_KEY is missing from "
        "Streamlit Secrets."
    )

    st.code(
        'YOUTUBE_API_KEY = "your_youtube_api_key_here"',
        language="toml"
    )

    st.stop()


# ============================================================
# INPUT
# ============================================================

video_url = st.text_input(
    "🎬 YouTube video URL",
    placeholder=
    "https://www.youtube.com/watch?v=..."
)


st.subheader(
    "📈 YouTube Studio Metrics"
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
        "Average Percentage Viewed (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1
    )


# ============================================================
# ANALYZE
# ============================================================

if st.button(
    "🚀 Analyze Video",
    type="primary",
    use_container_width=True
):

    video_id = extract_video_id(
        video_url
    )

    if not video_id:

        st.error(
            "❌ I couldn't recognize that YouTube URL."
        )

        st.stop()


    with st.spinner(
        "Loading YouTube data..."
    ):

        try:

            video = get_video(
                video_id
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


    result = diagnose(
        ctr=ctr,
        impressions=impressions,
        retention=retention,
        views=video["views"],
        likes=video["likes"],
        comments=video["comments"]
    )


    # ========================================================
    # VIDEO
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
    # OVERALL DIAGNOSIS
    # ========================================================

    st.divider()

    st.header(
        "🧠 Overall Diagnosis"
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
        f"🎯 **Most important:** "
        f"{result['priority']}"
    )


    # ========================================================
    # METRIC BREAKDOWN
    # ========================================================

    st.divider()

    st.header(
        "🔬 Metric Breakdown"
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
        "Engagement Rate",
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
            "🚨 Biggest Problems"
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
        "🎯 What I'd Change"
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

        else:

            st.info(
                f"**{title}**\n\n{text}"
            )


    # ========================================================
    # FINAL NOTE
    # ========================================================

    st.divider()

    st.caption(
        "These are diagnostic heuristics, not official "
        "YouTube benchmarks. CTR and retention vary "
        "substantially by topic, audience, traffic source, "
        "video length, and distribution."
    )
