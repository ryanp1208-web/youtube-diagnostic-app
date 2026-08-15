import re
import statistics
from datetime import datetime

import streamlit as st
from googleapiclient.discovery import build


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube Video Doctor",
    page_icon="🩺",
    layout="wide",
)

st.markdown("""
<style>
    .metric-card {
        padding: 14px 16px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 10px;
    }

    .big-score {
        font-size: 42px;
        font-weight: 800;
    }

    .small-label {
        font-size: 13px;
        opacity: .7;
    }

    .diagnosis-box {
        padding: 20px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,.25);
        margin: 10px 0;
    }

    .priority {
        font-size: 18px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


st.title("🩺 YouTube Video Doctor")
st.caption(
    "Diagnose your videos using your own channel data — no AI API required."
)


# ============================================================
# API
# ============================================================

YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")

if not YOUTUBE_API_KEY:
    st.error("❌ Add YOUTUBE_API_KEY to Streamlit Secrets.")
    st.stop()


@st.cache_resource
def youtube_client():
    return build(
        "youtube",
        "v3",
        developerKey=YOUTUBE_API_KEY,
    )


# ============================================================
# SESSION HISTORY
# ============================================================

if "history" not in st.session_state:
    st.session_state.history = []

if "loaded_video" not in st.session_state:
    st.session_state.loaded_video = None

if "diagnosis" not in st.session_state:
    st.session_state.diagnosis = None


# ============================================================
# HELPERS
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
    thumbnails = snippet.get("thumbnails", {})

    thumbnail = (
        thumbnails.get("maxres")
        or thumbnails.get("high")
        or thumbnails.get("medium")
        or thumbnails.get("default")
    )

    return {
        "id": video_id,
        "title": snippet.get("title", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "channel_id": snippet.get("channelId", ""),
        "published_at": snippet.get("publishedAt", ""),
        "description": snippet.get("description", ""),
        "thumbnail": thumbnail["url"] if thumbnail else None,
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
    }


@st.cache_data(ttl=600)
def get_recent_videos(channel_id, limit=20):
    yt = youtube_client()

    channel = yt.channels().list(
        part="contentDetails",
        id=channel_id,
    ).execute()

    if not channel.get("items"):
        return []

    playlist = (
        channel["items"][0]
        ["contentDetails"]
        ["relatedPlaylists"]
        ["uploads"]
    )

    response = yt.playlistItems().list(
        part="contentDetails,snippet",
        playlistId=playlist,
        maxResults=limit,
    ).execute()

    ids = [
        item["contentDetails"]["videoId"]
        for item in response.get("items", [])
        if item["contentDetails"].get("videoId")
    ]

    if not ids:
        return []

    details = yt.videos().list(
        part="snippet,statistics",
        id=",".join(ids),
    ).execute()

    videos = []

    for item in details.get("items", []):
        stats = item.get("statistics", {})

        videos.append({
            "id": item["id"],
            "title": item["snippet"].get("title", ""),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "published_at": item["snippet"].get("publishedAt", ""),
        })

    return videos


def engagement_rate(views, likes, comments):
    if views <= 0:
        return 0

    return ((likes + comments) / views) * 100


def score_ctr(ctr):
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


def score_retention(retention):
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
    if retention >= 25:
        return 38

    return 20


def score_impressions(impressions):
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
    if impressions >= 500:
        return 35

    return 20


def title_analysis(title):
    score = 100
    warnings = []

    length = len(title)

    if length > 80:
        score -= 25
        warnings.append(
            "The title is very long. Consider making it tighter."
        )

    elif length > 65:
        score -= 10
        warnings.append(
            "The title is somewhat long."
        )

    if length < 25:
        warnings.append(
            "The title is very short. Make sure the premise is obvious."
        )

    if title.isupper() and len(title) > 10:
        score -= 10
        warnings.append(
            "The entire title is uppercase."
        )

    if not warnings:
        warnings.append(
            "Title length and structure look reasonable."
        )

    return max(0, score), warnings


def channel_stats(current_views, videos):
    if not videos:
        return None

    views = [
        v["views"]
        for v in videos
        if v["views"] >= 0
    ]

    if not views:
        return None

    average = statistics.mean(views)
    median = statistics.median(views)
    best = max(views)

    return {
        "average": average,
        "median": median,
        "best": best,
        "ratio": current_views / average if average else 0,
    }


# ============================================================
# CHANNEL-SPECIFIC BENCHMARKS
# ============================================================

def benchmark_metric(current, values):
    if not values:
        return None

    avg = statistics.mean(values)

    if avg == 0:
        return None

    return {
        "average": avg,
        "difference": ((current - avg) / avg) * 100,
    }


def bottleneck(ctr, retention, impressions, stats):
    if impressions < 500:
        return {
            "title": "Not enough data yet",
            "icon": "⚪",
            "reason": (
                "The video has not received enough impressions "
                "to make a reliable diagnosis."
            ),
            "action": "Wait for more data before making major changes.",
            "type": "data",
        }

    if ctr < 4.5 and retention >= 40:
        return {
            "title": "Packaging is the main bottleneck",
            "icon": "🔴",
            "reason": (
                "People who click are staying reasonably well, "
                "but the video is not generating enough clicks."
            ),
            "action": "Test the thumbnail/title combination first.",
            "type": "packaging",
        }

    if ctr >= 7 and retention < 35:
        return {
            "title": "Retention is the main bottleneck",
            "icon": "🔴",
            "reason": (
                "The packaging gets people into the video, "
                "but too many viewers leave."
            ),
            "action": "Improve the opening, pacing, and payoff.",
            "type": "retention",
        }

    if ctr < 4.5 and retention < 35:
        return {
            "title": "Packaging and retention both need work",
            "icon": "🔴",
            "reason": (
                "The video is struggling to attract clicks "
                "and keep the viewers it does attract."
            ),
            "action": (
                "Fix the packaging first, then work on the opening."
            ),
            "type": "both",
        }

    if (
        stats
        and stats["ratio"] < 0.65
        and ctr >= 5
    ):
        return {
            "title": "Distribution is the main bottleneck",
            "icon": "🟠",
            "reason": (
                "Your CTR is reasonably healthy, but this video "
                "is receiving much less distribution than your "
                "recent uploads."
            ),
            "action": (
                "Don't immediately replace the thumbnail. "
                "Monitor impressions first."
            ),
            "type": "distribution",
        }

    if ctr >= 7 and retention >= 40:
        return {
            "title": "Core viewer signals look healthy",
            "icon": "🟢",
            "reason": (
                "Both click appeal and retention are strong."
            ),
            "action": (
                "Don't overcorrect. Let the video gather more data."
            ),
            "type": "healthy",
        }

    return {
        "title": "Performance is mixed",
        "icon": "🟡",
        "reason": (
            "There is no single catastrophic metric."
        ),
        "action": (
            "Focus on whichever metric is furthest below your "
            "normal channel performance."
        ),
        "type": "mixed",
    }


def health_score(
    ctr_score,
    retention_score,
    impressions_score,
    channel_score,
):
    return round(
        ctr_score * 0.30
        + retention_score * 0.35
        + impressions_score * 0.15
        + channel_score * 0.20
    )


# ============================================================
# LOAD VIDEO
# ============================================================

st.markdown("### 🎬 Analyze a video")

url = st.text_input(
    "YouTube URL",
    placeholder="Paste a YouTube video URL...",
    label_visibility="collapsed",
)

if st.button(
    "Load Video →",
    type="primary",
    use_container_width=True,
):
    video_id = extract_video_id(url)

    if not video_id:
        st.error("That doesn't look like a valid YouTube URL.")
        st.stop()

    try:
        video = get_video(video_id)

        if not video:
            st.error("Video not found.")
            st.stop()

        st.session_state.loaded_video = video
        st.session_state.diagnosis = None

    except Exception as e:
        st.error(f"YouTube API error: {e}")
        st.stop()


# ============================================================
# VIDEO LOADED
# ============================================================

video = st.session_state.loaded_video

if video:

    st.divider()

    left, right = st.columns([1, 2])

    with left:
        if video["thumbnail"]:
            st.image(
                video["thumbnail"],
                use_container_width=True,
            )

    with right:

        st.subheader(video["title"])

        st.caption(
            f"{video['channel_title']} • "
            f"{video['published_at'][:10]}"
        )

        a, b, c = st.columns(3)

        a.metric(
            "Views",
            f"{video['views']:,}",
        )

        b.metric(
            "Likes",
            f"{video['likes']:,}",
        )

        c.metric(
            "Comments",
            f"{video['comments']:,}",
        )


    # ========================================================
    # COMPACT STUDIO METRICS
    # ========================================================

    st.markdown("### 📊 Studio Snapshot")

    st.caption(
        "Enter the three numbers from YouTube Studio. "
        "Everything else is calculated automatically."
    )

    a, b, c = st.columns(3)

    with a:
        ctr = st.number_input(
            "CTR %",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.1,
            key="ctr_input",
        )

    with b:
        impressions = st.number_input(
            "Impressions",
            min_value=0,
            value=0,
            step=100,
            key="impressions_input",
        )

    with c:
        retention = st.number_input(
            "Avg. % viewed",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.1,
            key="retention_input",
        )


    if st.button(
        "🩺 Diagnose",
        type="primary",
        use_container_width=True,
    ):

        recent = get_recent_videos(
            video["channel_id"],
            20,
        )

        comparison = [
            v for v in recent
            if v["id"] != video["id"]
        ]

        stats = channel_stats(
            video["views"],
            comparison,
        )

        ctr_score = score_ctr(ctr)
        retention_score = score_retention(retention)
        impressions_score = score_impressions(impressions)

        channel_score = 50

        if stats:
            ratio = stats["ratio"]

            if ratio >= 2:
                channel_score = 100
            elif ratio >= 1.5:
                channel_score = 95
            elif ratio >= 1.25:
                channel_score = 85
            elif ratio >= 1:
                channel_score = 75
            elif ratio >= .8:
                channel_score = 65
            elif ratio >= .6:
                channel_score = 50
            else:
                channel_score = 30

        score = health_score(
            ctr_score,
            retention_score,
            impressions_score,
            channel_score,
        )

        diagnosis = bottleneck(
            ctr,
            retention,
            impressions,
            stats,
        )

        tscore, twarnings = title_analysis(
            video["title"]
        )

        result = {
            "video_id": video["id"],
            "title": video["title"],
            "views": video["views"],
            "ctr": ctr,
            "impressions": impressions,
            "retention": retention,
            "score": score,
            "ctr_score": ctr_score,
            "retention_score": retention_score,
            "impressions_score": impressions_score,
            "channel_score": channel_score,
            "diagnosis": diagnosis,
            "stats": stats,
            "title_score": tscore,
            "title_warnings": twarnings,
            "time": datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ),
        }

        st.session_state.diagnosis = result

        # Don't duplicate the same video
        st.session_state.history = [
            h for h in st.session_state.history
            if h["video_id"] != video["id"]
        ]

        st.session_state.history.insert(
            0,
            result,
        )

        st.rerun()


# ============================================================
# RESULTS
# ============================================================

result = st.session_state.diagnosis

if result:

    st.divider()

    tabs = st.tabs([
        "🩺 Diagnosis",
        "🖼️ Thumbnail",
        "📊 Channel",
        "🧪 A/B Testing",
        "🗂️ History",
    ])


    # ========================================================
    # DIAGNOSIS TAB
    # ========================================================

    with tabs[0]:

        st.header("🩺 Diagnosis")

        a, b, c, d = st.columns(4)

        a.metric(
            "Health",
            f"{result['score']}/100",
        )

        b.metric(
            "CTR",
            f"{result['ctr']:.1f}%",
        )

        c.metric(
            "Retention",
            f"{result['retention']:.1f}%",
        )

        d.metric(
            "Impressions",
            f"{result['impressions']:,}",
        )


        if result["score"] >= 80:
            st.success(
                "🟢 **Strong overall performance**"
            )

        elif result["score"] >= 65:
            st.warning(
                "🟡 **Decent performance with room to improve**"
            )

        else:
            st.error(
                "🔴 **This video has significant weaknesses**"
            )


        st.subheader("🚨 Main Problem")

        diagnosis = result["diagnosis"]

        if diagnosis["type"] == "healthy":
            st.success(
                f"{diagnosis['icon']} **{diagnosis['title']}**\n\n"
                f"{diagnosis['reason']}\n\n"
                f"**Recommendation:** {diagnosis['action']}"
            )

        elif diagnosis["type"] == "data":
            st.info(
                f"{diagnosis['icon']} **{diagnosis['title']}**\n\n"
                f"{diagnosis['reason']}\n\n"
                f"**Recommendation:** {diagnosis['action']}"
            )

        else:
            st.warning(
                f"{diagnosis['icon']} **{diagnosis['title']}**\n\n"
                f"{diagnosis['reason']}\n\n"
                f"**Recommendation:** {diagnosis['action']}"
            )


        st.subheader("🎯 What I'd Do First")

        if diagnosis["type"] == "packaging":

            st.markdown("""
            **🥇 1. Test the thumbnail/title**

            Your viewers who click are showing decent interest.
            The first thing I'd experiment with is getting more
            people to click.

            **🥈 2. Keep the actual video structure**

            Don't completely rewrite your content strategy based
            only on CTR.
            """)

        elif diagnosis["type"] == "retention":

            st.markdown("""
            **🥇 1. Fix the opening**

            Get to the actual premise faster.

            **🥈 2. Improve pacing**

            Remove dead time and make the progression of the video
            easier to follow.

            **🚫 Don't immediately change the thumbnail**

            People are already clicking.
            """)

        elif diagnosis["type"] == "distribution":

            st.markdown("""
            **🥇 1. Monitor impressions**

            Your CTR isn't screaming "bad thumbnail."

            **🥈 2. Don't panic**

            Low impressions do not automatically mean the video
            itself is bad.

            **🚫 Don't immediately replace the thumbnail**
            """)

        elif diagnosis["type"] == "both":

            st.markdown("""
            **🥇 1. Fix packaging**

            Get more people interested in clicking.

            **🥈 2. Fix the opening**

            Once people click, give them a reason to stay.

            **⚠️ Don't change ten things simultaneously.**
            """)

        else:

            st.markdown("""
            **🥇 1. Improve the weakest metric**

            Don't change everything at once.

            **🥈 2. Compare against your winners**

            Look for patterns in the videos that outperform your
            normal channel average.
            """)


        st.subheader("📊 Component Scores")

        a, b, c, d = st.columns(4)

        a.metric(
            "CTR",
            f"{result['ctr_score']}/100",
        )

        b.metric(
            "Retention",
            f"{result['retention_score']}/100",
        )

        c.metric(
            "Impressions",
            f"{result['impressions_score']}/100",
        )

        d.metric(
            "Channel",
            f"{result['channel_score']}/100",
        )


        st.subheader("📝 Title")

        st.write(
            f"**{result['title']}**"
        )

        st.metric(
            "Title score",
            f"{result['title_score']}/100",
        )

        for warning in result["title_warnings"]:
            st.info(warning)


    # ========================================================
    # THUMBNAIL TAB
    # ========================================================

    with tabs[1]:

        st.header("🖼️ Thumbnail Lab")

        st.caption(
            "Upload the thumbnail you actually used to check "
            "basic packaging characteristics."
        )

        uploaded = st.file_uploader(
            "Upload thumbnail",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp",
            ],
            label_visibility="collapsed",
        )

        if uploaded:

            st.image(
                uploaded,
                width=640,
            )

            try:

                from PIL import Image

                image = Image.open(uploaded)

                width, height = image.size

                ratio = width / height

                st.subheader("Thumbnail diagnostics")

                a, b, c = st.columns(3)

                a.metric(
                    "Width",
                    f"{width}px",
                )

                b.metric(
                    "Height",
                    f"{height}px",
                )

                c.metric(
                    "Aspect ratio",
                    f"{ratio:.2f}",
                )


                if width < 1280:
                    st.warning(
                        "⚠️ The thumbnail is below the commonly "
                        "recommended 1280px width."
                    )

                else:
                    st.success(
                        "✅ Resolution is large enough."
                    )


                if 1.7 <= ratio <= 1.85:
                    st.success(
                        "✅ Aspect ratio is close to YouTube's "
                        "16:9 format."
                    )

                else:
                    st.warning(
                        "⚠️ The image isn't close to 16:9."
                    )


                st.info(
                    "💡 This tool intentionally does not pretend "
                    "to judge artistic quality without computer "
                    "vision. Use CTR to determine whether the "
                    "thumbnail actually works."
                )

            except Exception as e:
                st.error(
                    f"Could not analyze image: {e}"
                )

        else:

            st.info(
                "Upload your thumbnail to analyze it."
            )


    # ========================================================
    # CHANNEL TAB
    # ========================================================

    with tabs[2]:

        st.header("📊 Your Channel")

        stats = result["stats"]

        if not stats:

            st.info(
                "Not enough recent channel data."
            )

        else:

            a, b, c = st.columns(3)

            a.metric(
                "Recent average",
                f"{stats['average']:,.0f}",
            )

            b.metric(
                "This video",
                f"{stats['ratio']:.2f}× average",
            )

            c.metric(
                "Best recent",
                f"{stats['best']:,}",
            )


            difference = (
                (result["views"] - stats["average"])
                / stats["average"]
            ) * 100 if stats["average"] else 0


            if difference >= 0:

                st.success(
                    f"🔥 This video is **{difference:.0f}% above** "
                    f"your recent average."
                )

            else:

                st.warning(
                    f"📉 This video is **{abs(difference):.0f}% below** "
                    f"your recent average."
                )


            st.subheader(
                "🏆 Compare With Your Winners"
            )

            recent = get_recent_videos(
                video["channel_id"],
                20,
            )

            winners = sorted(
                recent,
                key=lambda x: x["views"],
                reverse=True,
            )[:5]

            for i, winner in enumerate(
                winners,
                1,
            ):

                st.write(
                    f"**#{i} — {winner['title']}**  \n"
                    f"👁️ {winner['views']:,} views"
                )


    # ========================================================
    # A/B TESTING
    # ========================================================

    with tabs[3]:

        st.header("🧪 A/B Test Calculator")

        st.caption(
            "Compare two thumbnail/title experiments using "
            "their CTR and impressions."
        )

        a, b = st.columns(2)

        with a:

            st.subheader("Version A")

            ctr_a = st.number_input(
                "CTR A (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                key="ab_ctr_a",
            )

            impressions_a = st.number_input(
                "Impressions A",
                min_value=0,
                value=0,
                step=100,
                key="ab_imp_a",
            )

        with b:

            st.subheader("Version B")

            ctr_b = st.number_input(
                "CTR B (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                key="ab_ctr_b",
            )

            impressions_b = st.number_input(
                "Impressions B",
                min_value=0,
                value=0,
                step=100,
                key="ab_imp_b",
            )


        if st.button(
            "Compare A vs B",
            use_container_width=True,
        ):

            if impressions_a == 0 or impressions_b == 0:

                st.warning(
                    "Enter impressions for both versions."
                )

            else:

                difference = ctr_b - ctr_a

                relative = (
                    difference / ctr_a * 100
                    if ctr_a > 0
                    else 0
                )

                if difference > 0:

                    st.success(
                        f"🏆 **Version B is currently winning.**\n\n"
                        f"CTR is **{difference:.2f} percentage points higher** "
                        f"({relative:.1f}% relative improvement)."
                    )

                elif difference < 0:

                    st.success(
                        f"🏆 **Version A is currently winning.**\n\n"
                        f"CTR is **{abs(difference):.2f} percentage points higher**."
                    )

                else:

                    st.info(
                        "The CTRs are currently identical."
                    )

                st.warning(
                    "⚠️ Treat small differences cautiously when "
                    "the impression counts are low."
                )


    # ========================================================
    # HISTORY TAB
    # ========================================================

    with tabs[4]:

        st.header("🗂️ Diagnosis History")

        if not st.session_state.history:

            st.info(
                "Your analyzed videos will appear here."
            )

        else:

            for item in st.session_state.history:

                with st.expander(
                    f"{item['title']} — "
                    f"{item['score']}/100"
                ):

                    a, b, c, d = st.columns(4)

                    a.metric(
                        "Health",
                        f"{item['score']}/100",
                    )

                    b.metric(
                        "CTR",
                        f"{item['ctr']:.1f}%",
                    )

                    c.metric(
                        "Retention",
                        f"{item['retention']:.1f}%",
                    )

                    d.metric(
                        "Views",
                        f"{item['views']:,}",
                    )

                    st.write(
                        f"**Diagnosis:** "
                        f"{item['diagnosis']['title']}"
                    )

                    st.caption(
                        f"Analyzed: {item['time']}"
                    )

            if st.button(
                "🗑️ Clear History"
            ):

                st.session_state.history = []
                st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "YouTube Video Doctor • No OpenAI/Gemini required • "
    "Diagnostics are estimates, not official YouTube ranking rules."
)
