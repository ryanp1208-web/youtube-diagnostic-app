import streamlit as st
from PIL import Image

st.set_page_config(page_title="YouTube Diagnostic Engine", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Video Diagnostic Dashboard")
st.caption("Upload your thumbnail and input metrics for a complete audit.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Channel Benchmarks")
    avg_ctr = st.number_input("Average CTR (%)", min_value=0.0, max_value=100.0, value=6.5, step=0.1)
    avg_retention = st.number_input("Average Retention (%)", min_value=0.0, max_value=100.0, value=42.0, step=0.5)
    avg_impressions = st.number_input("Average Impressions", min_value=0, value=4500, step=100)

with col2:
    st.subheader("2. Video Under Audit")
    video_title = st.text_input("Video Title", value="Kaiserreich Germany Playthrough Part 4")
    
    # Thumbnail Uploader Section
    uploaded_file = st.file_uploader("Upload Video Thumbnail (JPG/PNG)", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Thumbnail Preview", use_column_width=True)
        
    video_ctr = st.number_input("Video CTR (%)", min_value=0.0, max_value=100.0, value=2.8, step=0.1)
    video_retention = st.number_input("Video Retention (%)", min_value=0.0, max_value=100.0, value=21.5, step=0.5)
    video_impressions = st.number_input("Video Impressions", min_value=0, value=4100, step=100)

st.divider()

if st.button("Run Diagnostic", type="primary", use_container_width=True):
    st.header(f"Report for: '{video_title}'")
    
    # Packaging Assessment
    if video_ctr < (avg_ctr * 0.80):
        st.error("**Packaging Alert (Low CTR)**")
        st.write(f"Your CTR is **{video_ctr}%**, which is significantly lower than your **{avg_ctr}%** average.")
        if uploaded_file is not None:
            st.warning("⚠️ **Thumbnail Feedback:** Since your CTR is low, evaluate the uploaded thumbnail above. Try adding higher contrast, reducing text clutter, or making subject faces larger.")
        else:
            st.warning("⚠️ Try uploading a thumbnail image to preview and visually inspect your packaging.")
    else:
        st.success("**Packaging Healthy:** CTR is performing well relative to channel average.")