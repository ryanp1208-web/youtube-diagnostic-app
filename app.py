# ==========================================
# YOUTUBE VIDEO DIAGNOSTIC ENGINE
# ==========================================

def diagnose_video(ctr, impressions, retention, views, likes):
    """
    Diagnose YouTube video performance.

    Inputs:
        ctr         = CTR as a percentage (example: 8.5)
        impressions = total impressions
        retention   = average percentage viewed (example: 42.5)
        views       = total views
        likes       = total likes

    Returns:
        score       = 0-100
        overall     = overall performance rating
        diagnostics = list of individual findings
        priority    = most important thing to improve
    """

    score = 100
    diagnostics = []

    # ==========================================
    # 1. CTR / THUMBNAIL + TITLE
    # ==========================================

    if impressions < 2000:
        # Small sample = don't overreact
        if ctr >= 8:
            diagnostics.append({
                "category": "Packaging",
                "status": "good",
                "message": (
                    f"CTR is {ctr:.1f}% with only {impressions:,} impressions. "
                    "The early packaging signal is strong, but the sample is still small."
                ),
                "impact": 0
            })

        elif ctr >= 5:
            diagnostics.append({
                "category": "Packaging",
                "status": "okay",
                "message": (
                    f"CTR is {ctr:.1f}%. The thumbnail/title combination is "
                    "getting a reasonable number of clicks, but there is room to improve it."
                ),
                "impact": 8
            })
            score -= 8

        else:
            diagnostics.append({
                "category": "Packaging",
                "status": "bad",
                "message": (
                    f"CTR is only {ctr:.1f}% on {impressions:,} impressions. "
                    "The thumbnail or title may not be generating enough curiosity."
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
                    f"CTR is {ctr:.1f}% across {impressions:,} impressions. "
                    "Packaging is performing strongly at this level of distribution."
                ),
                "impact": 0
            })

        elif ctr >= 4.5:
            diagnostics.append({
                "category": "Packaging",
                "status": "okay",
                "message": (
                    f"CTR is {ctr:.1f}% across {impressions:,} impressions. "
                    "Packaging is acceptable, but a stronger thumbnail/title could increase clicks."
                ),
                "impact": 10
            })
            score -= 10

        else:
            diagnostics.append({
                "category": "Packaging",
                "status": "bad",
                "message": (
                    f"CTR is {ctr:.1f}% despite {impressions:,} impressions. "
                    "Packaging is likely limiting further growth."
                ),
                "impact": 20
            })
            score -= 20

    else:
        # Very large impression count
        if ctr >= 5:
            diagnostics.append({
                "category": "Packaging",
                "status": "good",
                "message": (
                    f"CTR is {ctr:.1f}% despite {impressions:,} impressions. "
                    "That is a strong packaging signal at high distribution."
                ),
                "impact": 0
            })

        elif ctr >= 3:
            diagnostics.append({
                "category": "Packaging",
                "status": "okay",
                "message": (
                    f"CTR is {ctr:.1f}% with {impressions:,} impressions. "
                    "The video is reaching a broad audience, but packaging could be sharper."
                ),
                "impact": 10
            })
            score -= 10

        else:
            diagnostics.append({
                "category": "Packaging",
                "status": "bad",
                "message": (
                    f"CTR is only {ctr:.1f}% after {impressions:,} impressions. "
                    "The thumbnail/title combination is probably the biggest weakness."
                ),
                "impact": 25
            })
            score -= 25

    # ==========================================
    # 2. RETENTION
    # ==========================================

    if retention >= 50:
        diagnostics.append({
            "category": "Retention",
            "status": "good",
            "message": (
                f"Average percentage viewed is {retention:.1f}%. "
                "Viewers are staying engaged."
            ),
            "impact": 0
        })

    elif retention >= 40:
        diagnostics.append({
            "category": "Retention",
            "status": "okay",
            "message": (
                f"Average percentage viewed is {retention:.1f}%. "
                "Retention is acceptable, but the opening and pacing could be improved."
            ),
            "impact": 10
        })
        score -= 10

    elif retention >= 30:
        diagnostics.append({
            "category": "Retention",
            "status": "bad",
            "message": (
                f"Average percentage viewed is only {retention:.1f}%. "
                "A significant number of viewers are leaving before the video finishes."
            ),
            "impact": 20
        })
        score -= 20

    else:
        diagnostics.append({
            "category": "Retention",
            "status": "bad",
            "message": (
                f"Average percentage viewed is only {retention:.1f}%. "
                "Retention is a major weakness. Focus on the first minute, pacing, "
                "and removing unnecessary sections."
            ),
            "impact": 30
        })
        score -= 30

    # ==========================================
    # 3. LIKE ENGAGEMENT
    # ==========================================

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

    # ==========================================
    # 4. FIND THE BIGGEST PROBLEM
    # ==========================================

    biggest_problem = None
    biggest_impact = 0

    for diagnostic in diagnostics:
        if diagnostic["impact"] > biggest_impact:
            biggest_impact = diagnostic["impact"]
            biggest_problem = diagnostic["category"]

    if biggest_problem == "Packaging":
        priority = (
            "Thumbnail/title is the biggest opportunity. "
            "Consider improving the focal point, contrast, clarity, "
            "and curiosity of the packaging."
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
            "Consider making the video more interactive and "
            "giving viewers a reason to comment or like."
        )

    else:
        priority = (
            "No major weakness detected. "
            "The video's core metrics are performing reasonably well."
        )

    # ==========================================
    # 5. FINAL SCORE
    # ==========================================

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
