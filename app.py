import streamlit as st
import re
import requests
import base64
from statistics import mean
from googleapiclient.discovery import build


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="YouTube Video Diagnostic",
    page_icon="📊",
    layout="wide"
)

st.title("📊 YouTube Video Diagnostic")
st.write(
    "Analyze your video's packaging, CTR, distribution, retention, "
    "engagement, and channel performance."
)


# =========================================================
# SECRETS
# =========================================================

try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    st.error("❌ YOUTUBE_API_KEY is missing from Streamlit Secrets.")
    st.stop()

# Gemini is optional.
# The app still works without it, but AI thumbnail/title analysis
# will be unavailable.

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")


# =========================================================
# YOUTUBE API
# =========================================================

def get_youtube_client():

    return build(
        "youtube",
        "v3",
        developerKey=YOUTUBE_API_KEY
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

    youtube = get_youtube_client()

    request = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=video_id
    )

    response = request.execute()

    if not response.get("items"):
        return None

    item = response["items"][0]

    snippet = item["snippet"]
    stats = item["statistics"]

    channel_id = snippet["channelId"]

    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))

    thumbnail = (
        snippet["thumbnails"]
        .get("maxres",
             snippet["thumbnails"].get("high"))
        ["url"]
    )

    channel_request = youtube.channels().list(
        part="statistics,snippet",
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
        "id": video_id,
        "title": snippet["title"],
        "description": snippet.get("description", ""),
        "channel_title": snippet["channelTitle"],
        "channel_id": channel_id,
        "thumbnail": thumbnail,
        "published_at": snippet["publishedAt"],
        "views": views,
        "likes": likes,
        "comments": comments,
        "subscribers": subscribers,
        "duration": item["contentDetails"]["duration"]
    }


# =========================================================
# GET RECENT CHANNEL VIDEOS
# =========================================================

def get_recent_channel_videos(channel_id, exclude_video_id):

    youtube = get_youtube_client()

    search_request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        type="video",
        order="date",
        maxResults=10
    )

    search_response = search_request.execute()

    video_ids = []

    for item in search_response.get("items", []):

        video_id = item["id"]["videoId"]

        if video_id != exclude_video_id:
            video_ids.append(video_id)

    if not video_ids:
        return []

    video_request = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    )

    video_response = video_request.execute()

    videos = []

    for item in video_response.get("items", []):

        stats = item["statistics"]

        videos.append({
            "id": item["id"],
            "title": item["snippet"]["title"],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "published_at": item["snippet"]["publishedAt"]
        })

    return videos


# =========================================================
# CHANNEL COMPARISON
# =========================================================

def compare_to_channel(video, recent_videos):

    if not recent_videos:
        return None

    avg_views = mean(
        video_item["views"]
        for video_item in recent_videos
    )

    avg_likes = mean(
        video_item["likes"]
        for video_item in recent_videos
    )

    if avg_views > 0:
        view_ratio = video["views"] / avg_views
    else:
        view_ratio = 0

    if avg_likes > 0:
        like_ratio = video["likes"] / avg_likes
    else:
        like_ratio = 0

    return {
        "average_views": avg_views,
        "average_likes": avg_likes,
        "view_ratio": view_ratio,
        "like_ratio": like_ratio
    }


# =========================================================
# SMART DIAGNOSTIC ENGINE
# =========================================================

def diagnose_video(
    ctr,
    impressions,
    retention,
    views,
    likes,
    comments,
    channel_comparison=None
):

    score = 100

    findings = []

    problems = []

    strengths = []


    # -----------------------------------------------------
    # PACKAGING / CTR
    # -----------------------------------------------------

    if impressions < 2000:

        if ctr >= 8:

            strengths.append("Strong early CTR")

            findings.append(
                (
                    "Packaging",
                    "🟢",
                    f"CTR is {ctr:.1f}% on a small sample of "
                    f"{impressions:,} impressions. Early packaging "
                    "looks promising, but there isn't enough "
                    "distribution to draw a firm conclusion."
                )
            )

        elif ctr >= 5:

            score -= 7

            findings.append(
                (
                    "Packaging",
                    "🟡",
                    f"CTR is {ctr:.1f}%. The packaging is getting "
                    "some clicks, but there is room to make the "
                    "thumbnail/title more compelling."
                )
            )

        else:

            score -= 20

            problems.append("Packaging")

            findings.append(
                (
                    "Packaging",
                    "🔴",
                    f"CTR is only {ctr:.1f}%. The thumbnail/title "
                    "combination may not be creating enough curiosity."
                )
            )

    elif impressions < 100000:

        if ctr >= 7:

            strengths.append("Strong CTR")

            findings.append(
                (
                    "Packaging",
                    "🟢",
                    f"CTR is {ctr:.1f}% across {impressions:,} "
                    "impressions. Packaging is performing strongly."
                )
            )

        elif ctr >= 4.5:

            score -= 10

            findings.append(
                (
                    "Packaging",
                    "🟡",
                    f"CTR is {ctr:.1f}%. Packaging is acceptable, "
                    "but stronger thumbnail/title packaging could "
                    "increase the number of people clicking."
                )
            )

        else:

            score -= 23

            problems.append("Packaging")

            findings.append(
                (
                    "Packaging",
                    "🔴",
                    f"CTR is {ctr:.1f}% despite {impressions:,} "
                    "impressions. Packaging is likely limiting growth."
                )
            )

    else:

        if ctr >= 5:

            strengths.append("Strong high-distribution CTR")

            findings.append(
                (
                    "Packaging",
                    "🟢",
                    f"CTR is {ctr:.1f}% despite very large "
                    f"distribution ({impressions:,} impressions). "
                    "That is a strong packaging signal."
                )
            )

        elif ctr >= 3:

            score -= 10

            findings.append(
                (
                    "Packaging",
                    "🟡",
                    f"CTR is {ctr:.1f}% with {impressions:,} "
                    "impressions. The video is reaching a broad "
                    "audience, but packaging could be sharper."
                )
            )

        else:

            score -= 25

            problems.append("Packaging")

            findings.append(
                (
                    "Packaging",
                    "🔴",
                    f"CTR is only {ctr:.1f}% after {impressions:,} "
                    "impressions. Thumbnail/title packaging is "
                    "probably a major bottleneck."
                )
            )


    # -----------------------------------------------------
    # RETENTION
    # -----------------------------------------------------

    if retention >= 50:

        strengths.append("Excellent retention")

        findings.append(
            (
                "Retention",
                "🟢",
                f"Average percentage viewed is {retention:.1f}%. "
                "Viewers are staying highly engaged."
            )
        )

    elif retention >= 40:

        score -= 7

        findings.append(
            (
                "Retention",
                "🟡",
                f"Average percentage viewed is {retention:.1f}%. "
                "Retention is acceptable, but pacing and the "
                "opening could still be improved."
            )
        )

    elif retention >= 30:

        score -= 20

        problems.append("Retention")

        findings.append(
            (
                "Retention",
                "🔴",
                f"Average percentage viewed is only {retention:.1f}%. "
                "A substantial number of viewers are leaving early."
            )
        )

    else:

        score -= 30

        problems.append("Retention")

        findings.append(
            (
                "Retention",
                "🔴",
                f"Average percentage viewed is only {retention:.1f}%. "
                "Retention is a major weakness. Focus heavily on "
                "the opening and pacing."
            )
        )


    # -----------------------------------------------------
    # ENGAGEMENT
    # -----------------------------------------------------

    like_rate = 0

    comment_rate = 0

    if views > 0:

        like_rate = (likes / views) * 100
        comment_rate = (comments / views) * 100


    if like_rate >= 5:

        strengths.append("Strong like engagement")

        findings.append(
            (
                "Engagement",
                "🟢",
                f"Like rate is {like_rate:.2f}%. "
                "Viewer engagement is strong."
            )
        )

    elif like_rate >= 2:

        score -= 3

        findings.append(
            (
                "Engagement",
                "🟡",
                f"Like rate is {like_rate:.2f}%. "
                "Engagement is reasonable."
            )
        )

    else:

        score -= 8

        findings.append(
            (
                "Engagement",
                "🔴",
                f"Like rate is only {like_rate:.2f}%. "
                "The video may not be generating much active engagement."
            )
        )


    # -----------------------------------------------------
    # CHANNEL COMPARISON
    # -----------------------------------------------------

    if channel_comparison:

        ratio = channel_comparison["view_ratio"]

        if ratio >= 1.5:

            strengths.append("Outperforming recent channel videos")

            findings.append(
                (
                    "Channel Performance",
                    "🟢",
                    f"This video has about {ratio:.1f}× the views "
                    "of your recent-channel average."
                )
            )

        elif ratio >= 0.75:

            findings.append(
                (
                    "Channel Performance",
                    "🟡",
                    f"This video is at about {ratio:.1f}× your "
                    "recent-channel average. Performance is fairly normal."
                )
            )

        else:

            score -= 10

            problems.append("Channel Performance")

            findings.append(
                (
                    "Channel Performance",
                    "🔴",
                    f"This video is at only {ratio:.1f}× your "
                    "recent-channel average. It is underperforming "
                    "your recent uploads."
                )
            )


    # -----------------------------------------------------
    # CROSS-METRIC DIAGNOSIS
    # -----------------------------------------------------

    if ctr >= 7 and retention < 35:

        cross_diagnosis = (
            "🚨 Your packaging appears stronger than your viewer "
            "experience. People are clicking, but many aren't staying. "
            "Do NOT immediately change the thumbnail."
        )

    elif ctr < 4.5 and retention >= 40:

        cross_diagnosis = (
            "🚨 Your video appears stronger after the click than "
            "before the click. The content is holding viewers, but "
            "the thumbnail/title may be preventing enough people "
            "from entering the video."
        )

    elif ctr >= 7 and retention >= 40:

        cross_diagnosis = (
            "🔥 Both packaging and viewer retention are healthy. "
            "The next major question is whether YouTube continues "
            "expanding distribution."
        )

    elif ctr < 4.5 and retention < 35:

        cross_diagnosis = (
            "🚨 You have problems on both sides of the click. "
            "Improve the thumbnail/title AND the opening/pacing."
        )

    else:

        cross_diagnosis = (
            "The metrics are mixed. There isn't one overwhelmingly "
            "obvious bottleneck, so look at the individual findings."
        )


    # -----------------------------------------------------
    # PRIORITY
    # -----------------------------------------------------

    if "Packaging" in problems:

        priority = (
            "Fix the thumbnail/title first. Your biggest issue "
            "appears to be getting enough viewers to click."
        )

    elif "Retention" in problems:

        priority = (
            "Fix retention first. Your packaging is not necessarily "
            "the problem if viewers are clicking but leaving."
        )

    elif "Channel Performance" in problems:

        priority = (
            "Investigate why this upload is underperforming your "
            "normal channel baseline."
        )

    else:

        priority = (
            "There is no single catastrophic weakness. "
            "Optimize the weakest yellow metric rather than "
            "changing everything at once."
        )


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


    return {
        "score": score,
        "overall": overall,
        "findings": findings,
        "strengths": strengths,
        "problems": problems,
        "priority": priority,
        "cross_diagnosis": cross_diagnosis,
        "like_rate": like_rate,
        "comment_rate": comment_rate
    }


# =========================================================
# GEMINI IMAGE + TEXT ANALYSIS
# =========================================================

def analyze_thumbnail_with_gemini(
    thumbnail_url,
    title,
    channel_name
):

    if not GEMINI_API_KEY:
        return None

    try:

        image_response = requests.get(
            thumbnail_url,
            timeout=15
        )

        image_response.raise_for_status()

        image_bytes = image_response.content

        mime_type = image_response.headers.get(
            "Content-Type",
            "image/jpeg"
        )

        encoded_image = base64.b64encode(
            image_bytes
        ).decode("utf-8")


        prompt = f"""
You are a YouTube thumbnail and title expert.

Analyze this YouTube thumbnail and title.

Channel:
{channel_name}

Title:
{title}

Evaluate:

1. Thumbnail focal point
2. Mobile readability
3. Text amount
4. Visual clutter
5. Contrast
6. Subject size
7. Curiosity
8. Whether the thumbnail communicates the video's premise
9. Whether the title and thumbnail complement each other
10. The THREE most important improvements

This is a long-form gaming/HOI4-style channel, so judge it
for gaming viewers rather than generic corporate YouTube.

Be honest and specific.

Return:

THUMBNAIL SCORE: X/100

STRENGTHS:
- ...
- ...
- ...

PROBLEMS:
- ...
- ...
- ...

TITLE:
- ...

TITLE + THUMBNAIL:
- ...

TOP 3 CHANGES:
1. ...
2. ...
3. ...
"""


        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.5-flash:generateContent"
            f"?key={GEMINI_API_KEY}"
        )


        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": encoded_image
                            }
                        }
                    ]
                }
            ]
        }


        response = requests.post(
            url,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        result = response.json()

        return (
            result["candidates"][0]["content"]["parts"][0]["text"]
        )

    except Exception as error:

        return f"Gemini analysis failed: {error}"


# =========================================================
# GEMINI OVERALL ANALYST
# =========================================================

def generate_ai_diagnosis(
    title,
    ctr,
    impressions,
    retention,
    views,
    likes,
    diagnostic,
    channel_comparison
):

    if not GEMINI_API_KEY:
        return None

    try:

        channel_text = "No channel comparison available."

        if channel_comparison:

            channel_text = f"""
Recent channel average views:
{channel_comparison['average_views']:.0f}

This video's views:
{views}

View ratio:
{channel_comparison['view_ratio']:.2f}x
"""


        prompt = f"""
You are a YouTube performance analyst.

Analyze this video using the metrics below.

TITLE:
{title}

CTR:
{ctr:.1f}%

IMPRESSIONS:
{impressions:,}

AVERAGE PERCENTAGE VIEWED:
{retention:.1f}%

VIEWS:
{views:,}

LIKES:
{likes:,}

LIKE RATE:
{diagnostic['like_rate']:.2f}%

OVERALL SCORE:
{diagnostic['score']}/100

RULE-BASED DIAGNOSIS:
{diagnostic['cross_diagnosis']}

MAIN PRIORITY:
{diagnostic['priority']}

{channel_text}

Give a concise but useful diagnosis.

Answer these:

1. WHAT IS WORKING?
2. WHAT IS HURTING THE VIDEO?
3. WHAT SHOULD THE CREATOR CHANGE FIRST?
4. WHAT SHOULD THEY NOT CHANGE?
5. ONE-SENTENCE VERDICT

Do not pretend these metrics reveal the YouTube algorithm.
Make recommendations based on the evidence.
"""


        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.5-flash:generateContent"
            f"?key={GEMINI_API_KEY}"
        )


        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }


        response = requests.post(
            url,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        result = response.json()

        return (
            result["candidates"][0]["content"]["parts"][0]["text"]
        )

    except Exception as error:

        return f"AI analyst failed: {error}"


# =========================================================
# INPUTS
# =========================================================

video_url = st.text_input(
    "Paste YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)


st.subheader("📊 YouTube Analytics")

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
# ANALYZE BUTTON
# =========================================================

if st.button(
    "🔍 Analyze Video",
    type="primary",
    use_container_width=True
):

    if not video_url:

        st.error("Paste a YouTube URL first.")

        st.stop()


    video_id = extract_video_id(video_url)

    if not video_id:

        st.error("That doesn't look like a valid YouTube URL.")

        st.stop()


    # -----------------------------------------------------
    # GET VIDEO
    # -----------------------------------------------------

    with st.spinner("Getting YouTube data..."):

        try:

            video = get_video_data(video_id)

        except Exception as error:

            st.error(
                f"YouTube API error: {error}"
            )

            st.stop()


    if not video:

        st.error("Video not found.")

        st.stop()


    # -----------------------------------------------------
    # GET CHANNEL HISTORY
    # -----------------------------------------------------

    with st.spinner("Comparing with recent channel videos..."):

        try:

            recent_videos = get_recent_channel_videos(
                video["channel_id"],
                video["id"]
            )

            channel_comparison = compare_to_channel(
                video,
                recent_videos
            )

        except Exception:

            recent_videos = []

            channel_comparison = None


    # -----------------------------------------------------
    # RUN DIAGNOSIS
    # -----------------------------------------------------

    diagnostic = diagnose_video(
        ctr=user_ctr,
        impressions=user_impressions,
        retention=user_retention,
        views=video["views"],
        likes=video["likes"],
        comments=video["comments"],
        channel_comparison=channel_comparison
    )


    # =====================================================
    # VIDEO HEADER
    # =====================================================

    st.divider()

    st.header(
        f"🎬 {video['title']}"
    )

    st.caption(
        f"Channel: {video['channel_title']} • "
        f"{video['subscribers']:,} subscribers"
    )


    col1, col2 = st.columns([1, 2])


    with col1:

        st.image(
            video["thumbnail"],
            use_container_width=True
        )


    with col2:

        m1, m2 = st.columns(2)

        with m1:

            st.metric(
                "Views",
                f"{video['views']:,}"
            )

        with m2:

            st.metric(
                "Likes",
                f"{video['likes']:,}"
            )


        m3, m4 = st.columns(2)

        with m3:

            st.metric(
                "Comments",
                f"{video['comments']:,}"
            )

        with m4:

            st.metric(
                "Subscribers",
                f"{video['subscribers']:,}"
            )


    # =====================================================
    # OVERALL SCORE
    # =====================================================

    st.divider()

    st.header("🧠 Overall Diagnosis")

    st.subheader(
        f"{diagnostic['overall']} — "
        f"{diagnostic['score']}/100"
    )


    st.info(
        f"🎯 **Priority:** {diagnostic['priority']}"
    )


    st.warning(
        diagnostic["cross_diagnosis"]
    )


    # =====================================================
    # METRICS
    # =====================================================

    st.subheader("📈 Performance Metrics")

    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "CTR",
            f"{user_ctr:.1f}%"
        )


    with c2:

        st.metric(
            "Impressions",
            f"{user_impressions:,}"
        )


    with c3:

        st.metric(
            "Retention",
            f"{user_retention:.1f}%"
        )


    with c4:

        st.metric(
            "Like Rate",
            f"{diagnostic['like_rate']:.2f}%"
        )


    # =====================================================
    # DETAILED DIAGNOSIS
    # =====================================================

    st.divider()

    st.header("🔬 Detailed Diagnosis")


    for category, status, message in diagnostic["findings"]:

        if status == "🟢":

            st.success(
                f"**{category}** {status} — {message}"
            )

        elif status == "🟡":

            st.warning(
                f"**{category}** {status} — {message}"
            )

        else:

            st.error(
                f"**{category}** {status} — {message}"
            )


    # =====================================================
    # CHANNEL COMPARISON
    # =====================================================

    if channel_comparison:

        st.divider()

        st.header("📊 Compared With Your Channel")


        c1, c2, c3 = st.columns(3)


        with c1:

            st.metric(
                "Recent Video Avg Views",
                f"{channel_comparison['average_views']:,.0f}"
            )


        with c2:

            st.metric(
                "This Video",
                f"{video['views']:,}"
            )


        with c3:

            st.metric(
                "Performance vs Average",
                f"{channel_comparison['view_ratio']:.2f}×"
            )


        st.caption(
            "Comparison uses the most recent videos available "
            "through the YouTube Data API. It does not have access "
            "to those videos' private CTR or retention."
        )


    # =====================================================
    # RECENT VIDEOS TABLE
    # =====================================================

    if recent_videos:

        st.subheader("Recent Uploads")

        for recent in recent_videos[:5]:

            ratio = 0

            if channel_comparison:
                ratio = (
                    recent["views"] /
                    channel_comparison["average_views"]
                )

            st.write(
                f"**{recent['title']}** — "
                f"{recent['views']:,} views "
                f"({ratio:.2f}× channel average)"
            )


    # =====================================================
    # AI THUMBNAIL / TITLE ANALYSIS
    # =====================================================

    st.divider()

    st.header("🖼️ AI Thumbnail & Title Analysis")


    if GEMINI_API_KEY:

        with st.spinner(
            "Gemini is examining your thumbnail and title..."
        ):

            thumbnail_analysis = analyze_thumbnail_with_gemini(
                video["thumbnail"],
                video["title"],
                video["channel_title"]
            )


        if thumbnail_analysis:

            st.markdown(
                thumbnail_analysis
            )

    else:

        st.info(
            "Add GEMINI_API_KEY to Streamlit Secrets to enable "
            "AI thumbnail and title analysis."
        )


    # =====================================================
    # AI OVERALL ANALYST
    # =====================================================

    st.divider()

    st.header("🤖 AI Performance Analyst")


    if GEMINI_API_KEY:

        with st.spinner(
            "Generating your final performance analysis..."
        ):

            ai_analysis = generate_ai_diagnosis(
                title=video["title"],
                ctr=user_ctr,
                impressions=user_impressions,
                retention=user_retention,
                views=video["views"],
                likes=video["likes"],
                diagnostic=diagnostic,
                channel_comparison=channel_comparison
            )


        if ai_analysis:

            st.markdown(
                ai_analysis
            )

    else:

        st.info(
            "Add GEMINI_API_KEY to enable the AI Performance Analyst."
        )


    # =====================================================
    # FINAL RECOMMENDATIONS
    # =====================================================

    st.divider()

    st.header("🎯 What I'd Change")


    if "Packaging" in diagnostic["problems"]:

        st.error(
            "🖼️ **1. Work on the thumbnail/title.** "
            "Your CTR suggests the packaging is currently "
            "one of the biggest opportunities."
        )

    else:

        st.success(
            "🖼️ **1. Don't immediately change the thumbnail.** "
            "Your CTR isn't currently showing an obvious "
            "packaging crisis."
        )


    if "Retention" in diagnostic["problems"]:

        st.error(
            "🎬 **2. Improve the opening and pacing.** "
            "Viewers are clicking but too many are leaving."
        )

    else:

        st.success(
            "🎬 **2. Retention isn't your biggest problem.** "
            "Don't completely restructure the video based "
            "on retention alone."
        )


    if channel_comparison:

        if channel_comparison["view_ratio"] < 0.75:

            st.warning(
                "📈 **3. Investigate why this upload is below "
                "your channel's normal view level.**"
            )

        elif channel_comparison["view_ratio"] >= 1.5:

            st.success(
                "📈 **3. This video is outperforming your "
                "recent channel baseline.**"
            )


st.divider()

st.caption(
    "Diagnostic scores are heuristic estimates, not official "
    "YouTube benchmarks. CTR and retention vary substantially "
    "by topic, audience, traffic source, video length, and "
    "distribution."
)
