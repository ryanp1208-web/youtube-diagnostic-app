import re
import statistics

import streamlit as st
from googleapiclient.discovery import build
from openai import OpenAI


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
    "Diagnose your video's performance and get an AI-powered explanation."
)


# ============================================================
# API KEYS
# ============================================================

YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")

if not YOUTUBE_API_KEY:
    st.error("❌ YOUTUBE_API_KEY is missing from Streamlit Secrets.")
    st.stop()

if not OPENAI_API_KEY:
    st.warning(
        "⚠️ OPENAI_API_KEY is missing. "
        "The normal diagnosis will still work, but AI Overview will be disabled."
    )


# ============================================================
# CLIENTS
# ============================================================

@st.cache_resource
def youtube_client():
    return build(
        "youtube",
        "v3",
        developerKey=YOUTUBE_API_KEY,
    )


@st.cache_resource
def openai_client():
    if not OPENAI_API_KEY:
        return None

    return OpenAI(
        api_key=OPENAI_API_KEY
    )


# ============================================================
# VIDEO ID
# ============================================================

def extract_video_id(url):

    patterns = [
        r"(?:v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})"
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
# YOUTUBE VIDEO
# ============================================================

@st.cache_data(ttl=600)
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
    thumbs = snippet.get("thumbnails", {})

    thumbnail = (
        thumbs.get("maxres")
        or thumbs.get("high")
        or thumbs.get("medium")
        or thumbs.get("default")
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
        "published_at": snippet.get(
            "publishedAt",
            ""
        ),
        "description": snippet.get(
            "description",
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
        id=channel_id,
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
        maxResults=limit,
    ).execute()

    ids = [
        item["contentDetails"].get("videoId")
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
        })

    return videos


# ============================================================
# METRICS
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


def channel_stats(
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

    average = statistics.mean(values)
    median = statistics.median(values)

    sorted_values = sorted(
        values,
        reverse=True
    )

    best = sorted_values[0]

    top_three_average = statistics.mean(
        sorted_values[
            :min(
                3,
                len(sorted_values)
            )
        ]
    )

    ratio = (
        views / average
        if average > 0
        else 0
    )

    best_ratio = (
        views / best
        if best > 0
        else 0
    )

    if ratio >= 1.5:
        label = (
            "🔥 Well above your recent channel average"
        )

    elif ratio >= 1:
        label = (
            "🟢 Above your recent channel average"
        )

    elif ratio >= 0.75:
        label = (
            "🟡 Slightly below your recent channel average"
        )

    else:
        label = (
            "🔴 Significantly below your recent channel average"
        )

    return {
        "average": average,
        "median": median,
        "best": best,
        "top_three_average": top_three_average,
        "ratio": ratio,
        "best_ratio": best_ratio,
        "label": label,
    }


# ============================================================
# CTR
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
                "Reasonable early CTR; wait for more impressions."
            )

        return (
            "🔴",
            "Low early CTR, but there isn't enough data to panic."
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
                "Decent CTR with more data still needed."
            )

        return (
            "🔴",
            "Packaging may be limiting clicks."
        )

    if impressions < 100000:

        if ctr >= 8:
            return (
                "🟢",
                "Excellent CTR at this distribution level."
            )

        if ctr >= 6:
            return (
                "🟢",
                "Strong CTR."
            )

        if ctr >= 4:
            return (
                "🟡",
                "Average CTR; packaging has room to improve."
            )

        return (
            "🔴",
            "Low CTR; packaging is probably a bottleneck."
        )

    if ctr >= 6:
        return (
            "🟢",
            "Very strong CTR despite broad distribution."
        )

    if ctr >= 4:
        return (
            "🟡",
            "Healthy CTR for a heavily distributed video."
        )

    if ctr >= 2.5:
        return (
            "🟡",
            "Understandable at this scale, but packaging may improve."
        )

    return (
        "🔴",
        "Weak CTR even after accounting for broad distribution."
    )


# ============================================================
# RETENTION
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
            "Solid retention with room to improve."
        )

    if retention >= 30:
        return (
            "🟠",
            "Retention is becoming a meaningful weakness."
        )

    return (
        "🔴",
        "Low retention; viewer drop-off is likely a major problem."
    )


# ============================================================
# ENGAGEMENT
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
# MAIN DIAGNOSIS
# ============================================================

def diagnose(
    ctr,
    impressions,
    retention,
    views,
    likes,
    comments,
    stats
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

    # CTR
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

        actions.append({
            "priority": 1,
            "title": "Improve the thumbnail/title",
            "text": (
                "CTR is the clearest weakness. "
                "Make the video's main idea obvious, "
                "reduce clutter, and create a stronger "
                "reason to click."
            )
        })

    # RETENTION
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

        actions.append({
            "priority": 1,
            "title": "Tighten the video",
            "text": (
                "Get to the premise faster, "
                "remove dead sections, and improve pacing."
            )
        })

    else:

        score -= 30

        problems.append(
            "🎬 Viewer retention"
        )

        actions.append({
            "priority": 1,
            "title": "Fix the opening and pacing",
            "text": (
                "The main problem appears to happen after "
                "the click. Deliver the title/thumbnail "
                "promise faster and remove slow sections."
            )
        })

    # ENGAGEMENT
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

        actions.append({
            "priority": 2,
            "title": "Give viewers something to react to",
            "text": (
                "Use a natural question, prediction, "
                "challenge, or controversial choice."
            )
        })

    # CROSS METRIC DIAGNOSIS
    if ctr >= 7 and retention < 35:

        headline = (
            "🚨 People are clicking, but the video "
            "isn't keeping enough of them."
        )

        priority = (
            "Fix the opening and pacing before touching the thumbnail."
        )

        diagnosis_type = "retention"

    elif ctr < 4.5 and retention >= 40:

        headline = (
            "🎯 The people who click are staying reasonably well, "
            "but not enough people are clicking."
        )

        priority = (
            "Work on the thumbnail/title before rebuilding the video."
        )

        diagnosis_type = "packaging"

    elif ctr >= 7 and retention >= 40:

        headline = (
            "🔥 Both packaging and retention look healthy."
        )

        priority = (
            "Don't make drastic changes. Let distribution develop."
        )

        diagnosis_type = "healthy"

    elif ctr < 4.5 and retention < 35:

        headline = (
            "🚨 Both packaging and viewer retention need attention."
        )

        priority = (
            "Improve the thumbnail/title first, then tighten the opening."
        )

        diagnosis_type = "both"

    else:

        headline = (
            "🟡 Performance is mixed rather than having one "
            "catastrophic problem."
        )

        priority = (
            "Fix the weakest metric first instead of changing everything."
        )

        diagnosis_type = "mixed"

    # CHANNEL
    if stats:

        if stats["ratio"] >= 1.5:

            strengths.append(
                "📈 Views are substantially above your recent channel average"
            )

        elif stats["ratio"] < 0.75:

            problems.append(
                "📉 Views are substantially below your recent channel average"
            )

        if stats["best_ratio"] >= 0.8:

            strengths.append(
                "🏆 This video is competitive with your best recent uploads"
            )

    # SMART ACTIONS
    if diagnosis_type == "retention":

        actions.insert(0, {
            "priority": 1,
            "title": "Do NOT change the thumbnail first",
            "text": (
                "Your CTR says people are interested enough to click. "
                "The bigger problem is what happens after they arrive."
            )
        })

    elif diagnosis_type == "packaging":

        actions.insert(0, {
            "priority": 1,
            "title": "Test the packaging",
            "text": (
                "Your retention says the video can hold viewers once "
                "they click. The thumbnail/title is the more logical "
                "first thing to improve."
            )
        })

    elif diagnosis_type == "healthy":

        actions.insert(0, {
            "priority": 1,
            "title": "Don't overcorrect",
            "text": (
                "Both major viewer signals look healthy. "
                "A drastic change could make a good situation worse."
            )
        })

    elif diagnosis_type == "both":

        actions.insert(0, {
            "priority": 1,
            "title": "Fix packaging, then fix retention",
            "text": (
                "The video has problems both getting clicks and keeping "
                "viewers. Start with the thumbnail/title, then work "
                "on the opening."
            )
        })

    if impressions < 2000:

        actions.append({
            "priority": 3,
            "title": "Treat this result as preliminary",
            "text": (
                "There aren't many impressions yet. "
                "Don't make a major decision from CTR alone."
            )
        })

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
        "ctr_status": ctr_icon,
        "ctr_text": ctr_text,
        "ret_status": retention_icon,
        "ret_text": retention_text,
        "eng_status": engagement_icon,
        "eng_text": engagement_text,
        "engagement": engagement,
        "strengths": list(
            dict.fromkeys(strengths)
        ),
        "problems": list(
            dict.fromkeys(problems)
        ),
        "actions": sorted(
            actions,
            key=lambda x: x["priority"]
        ),
        "diagnosis_type": diagnosis_type,
    }


# ============================================================
# AI OVERVIEW
# ============================================================

def generate_ai_overview(
    video,
    ctr,
    impressions,
    retention,
    result,
    stats,
    video_length_minutes,
    avg_view_duration_minutes,
    traffic_source
):

    client = openai_client()

    if client is None:
        return None

    channel_average = (
        round(stats["average"])
        if stats
        else "Unavailable"
    )

    best_recent = (
        stats["best"]
        if stats
        else "Unavailable"
    )

    ratio = (
        round(stats["ratio"], 2)
        if stats
        else "Unavailable"
    )

    prompt = f"""
You are the AI doctor for a YouTube creator.

Analyze this video's performance like an experienced YouTube
analytics strategist.

IMPORTANT:
Do not pretend that there are universal perfect CTR or retention
numbers. Consider the impressions, video length, audience behavior,
and the creator's own channel averages.

VIDEO:
Title: {video['title']}
Views: {video['views']}
Likes: {video['likes']}
Comments: {video['comments']}

METRICS:
CTR: {ctr}%
Impressions: {impressions:,} 
Average percentage viewed: {retention}%
Video length: {video_length_minutes} minutes
Average view duration: {avg_view_duration_minutes} minutes
Traffic source selected by creator: {traffic_source}

CHANNEL CONTEXT:
Recent channel average views: {channel_average}
Best recent video views: {best_recent}
Current video vs recent average: {ratio}x

OUR RULE-BASED DIAGNOSIS:
Performance score: {result['score']}/100
Rating: {result['rating']}
Main diagnosis: {result['headline']}
First priority: {result['priority']}

Strengths:
{chr(10).join('- ' + x for x in result['strengths'])}

Problems:
{chr(10).join('- ' + x for x in result['problems'])}

Give the creator a concise but useful AI overview.

Use exactly these sections:

## 🩺 AI Diagnosis
Explain what is probably happening.

## 🎯 Biggest Problem
Identify the single most important thing to fix.

## ✅ What Is Working
Explain the strongest signal.

## 🔧 What I Would Change
Give 3 concrete actions.

## 🚫 What I Would NOT Change
Tell the creator what they should leave alone for now.

## 🚀 Next Video Advice
Give 2-3 practical suggestions for the next upload.

Be honest about uncertainty.
Do not invent analytics that were not provided.
Do not claim to know the exact YouTube algorithm.
Keep the advice practical for a gaming/HOI4 creator.
"""

    try:

        response = client.responses.create(
            model="gpt-5.6",
            input=prompt,
        )

        return response.output_text

    except Exception as exc:

        return (
            f"⚠️ AI Overview failed:\n\n"
            f"{exc}"
        )


# ============================================================
# INPUT
# ============================================================

video_url = st.text_input(
    "🎬 Paste your YouTube video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)

st.subheader(
    "📊 Performance Data"
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


st.subheader(
    "⏱️ Optional Video Context"
)

c1, c2, c3 = st.columns(3)

with c1:

    video_length = st.number_input(
        "Video length (minutes)",
        min_value=0.0,
        value=0.0,
        step=0.5,
    )

with c2:

    avg_view_duration = st.number_input(
        "Average view duration (minutes)",
        min_value=0.0,
        value=0.0,
        step=0.5,
    )

with c3:

    traffic_source = st.selectbox(
        "Main traffic source",
        [
            "Unknown / not sure",
            "Browse features",
            "Suggested videos",
            "YouTube Search",
            "External",
            "Channel pages",
            "Other YouTube features",
        ]
    )


# ============================================================
# ANALYZE
# ============================================================

if st.button(
    "🚀 Diagnose Video",
    type="primary",
    use_container_width=True,
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

            if not video:

                st.error(
                    "❌ Video not found."
                )

                st.stop()

            recent = get_recent_videos(
                video["channel_id"],
                limit=10
            )

        except Exception as exc:

            st.error(
                f"YouTube API error: {exc}"
            )

            st.stop()


    recent_without_current = [

        v
        for v in recent
        if v["id"] != video_id

    ]


    stats = channel_stats(
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

        stats=stats

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
    # DIAGNOSIS
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
    # PERFORMANCE SNAPSHOT
    # ========================================================

    st.divider()

    st.header(
        "📊 Performance Snapshot"
    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "CTR",
        f"{ctr:.1f}%"
    )

    m2.metric(
        "Retention",
        f"{retention:.1f}%"
    )

    m3.metric(
        "Impressions",
        f"{impressions:,}"
    )

    m4.metric(
        "Engagement",
        f"{result['engagement']:.2f}%"
    )


    # ========================================================
    # VIDEO CONTEXT
    # ========================================================

    if video_length > 0:

        st.divider()

        st.header(
            "⏱️ Video Context"
        )

        a, b, c = st.columns(3)

        a.metric(
            "Video length",
            f"{video_length:.1f} min"
        )

        if avg_view_duration > 0:

            b.metric(
                "Avg view duration",
                f"{avg_view_duration:.1f} min"
            )

            calculated_retention = (
                avg_view_duration
                / video_length
            ) * 100

            c.metric(
                "Calculated retention",
                f"{calculated_retention:.1f}%"
            )

        else:

            b.metric(
                "Avg view duration",
                "Not entered"
            )

            c.metric(
                "Traffic source",
                traffic_source
            )


    # ========================================================
    # CHANNEL COMPARISON
    # ========================================================

    if stats:

        st.divider()

        st.header(
            "🆚 Compared With Your Channel"
        )

        a, b, c, d = st.columns(4)

        a.metric(
            "Recent average",
            f"{stats['average']:,.0f}"
        )

        b.metric(
            "This video",
            f"{stats['ratio']:.2f}×"
        )

        c.metric(
            "Recent median",
            f"{stats['median']:,.0f}"
        )

        d.metric(
            "Best recent",
            f"{stats['best']:,}"
        )

        if stats["ratio"] >= 1.5:

            st.success(
                stats["label"]
            )

        elif stats["ratio"] >= 0.75:

            st.warning(
                stats["label"]
            )

        else:

            st.error(
                stats["label"]
            )


    # ========================================================
    # METRIC BREAKDOWN
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


    # ========================================================
    # WHAT'S WORKING
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
    # WHAT'S HURTING
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

    for action in result["actions"]:

        if action["priority"] == 1:

            st.error(
                f"**{action['title']}**\n\n"
                f"{action['text']}"
            )

        elif action["priority"] == 2:

            st.warning(
                f"**{action['title']}**\n\n"
                f"{action['text']}"
            )

        else:

            st.info(
                f"**{action['title']}**\n\n"
                f"{action['text']}"
            )


    # ========================================================
    # AI OVERVIEW
    # ========================================================

    if OPENAI_API_KEY:

        st.divider()

        st.header(
            "🤖 AI Doctor's Overview"
        )

        st.caption(
            "The AI gets the video's metrics and the diagnosis above "
            "and explains what is probably happening."
        )

        with st.spinner(
            "The AI is analyzing the diagnosis..."
        ):

            ai_overview = generate_ai_overview(

                video=video,

                ctr=ctr,

                impressions=impressions,

                retention=retention,

                result=result,

                stats=stats,

                video_length_minutes=video_length,

                avg_view_duration_minutes=avg_view_duration,

                traffic_source=traffic_source

            )

        if ai_overview:

            st.markdown(
                ai_overview
            )

        else:

            st.warning(
                "AI Overview could not be generated."
            )


    # ========================================================
    # TITLE CHECK
    # ========================================================

    st.divider()

    st.header(
        "📝 Title Quick Check"
    )

    title = video["title"]

    if len(title) > 70:

        st.warning(
            "⚠️ Your title is fairly long. "
            "Consider making it more concise."
        )

    elif len(title) < 25:

        st.info(
            "💡 Your title is short. "
            "Make sure it clearly communicates the video's idea."
        )

    else:

        st.success(
            "🟢 Title length looks reasonable."
        )


    if title.isupper() and len(title) > 10:

        st.warning(
            "⚠️ The entire title is uppercase."
        )


    # ========================================================
    # RECENT VIDEOS
    # ========================================================

    if recent_without_current:

        st.divider()

        st.header(
            "🆕 Recent Videos"
        )

        for item in recent_without_current[:7]:

            published = item["published_at"][:10]

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
        "YouTube Video Doctor is a diagnostic tool, not an official "
        "YouTube ranking system. Metrics vary by audience, topic, "
        "traffic source, video length, and distribution."
    )
