import streamlit as st
import whisper
import ffmpeg
import os
import uuid
import hashlib
from transformers import pipeline

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Video Transcriber", layout="wide", page_icon="🎬")
st.title("🎬 Comprehensive AI Video Transcriber & Captioner")

# --- CREATE CACHE FOLDER ---
# This ensures a folder exists to store our completed files
CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- CACHING THE AI MODELS ---
@st.cache_resource(show_spinner=False)
def load_standard_model(size):
    return whisper.load_model(size, device="cpu")

@st.cache_resource(show_spinner=False)
def load_akan_model():
    return pipeline(
        "automatic-speech-recognition",
        model="GiftMark/akan-whisper-model",
        chunk_length_s=30,
        device="cpu"
    )

# --- UTILITY FUNCTIONS ---
def get_file_hash(uploaded_file):
    """Generates a unique SHA-256 hash for the uploaded video file."""
    sha256_hash = hashlib.sha256()
    # Read the file in chunks so we don't crash the RAM on massive files
    for chunk in iter(lambda: uploaded_file.read(4096), b""):
        sha256_hash.update(chunk)
    # Reset the file pointer back to the beginning so Streamlit can still read it later!
    uploaded_file.seek(0)
    return sha256_hash.hexdigest()

def hex_to_ass(hex_code, opacity=100):
    hex_code = hex_code.lstrip('#')
    r, g, b = hex_code[0:2], hex_code[2:4], hex_code[4:6]
    alpha = hex(int(255 - (opacity / 100 * 255)))[2:].zfill(2).upper()
    return f"&H{alpha}{b}{g}{r}"

def format_timestamp(seconds):
    if seconds is None:
        seconds = 0.0
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((secs - int(secs)) * 1000)
    return f"{int(hours):02}:{int(minutes):02}:{int(secs):02},{millis:03}"

# --- SIDEBAR: SETTINGS ---
st.sidebar.header("⚙️ AI Engine Settings")

model_size = st.sidebar.selectbox("Whisper Model Size", ["base", "small", "medium", "large"], index=0)
task = st.sidebar.radio("AI Task", ["Transcribe (Original Language)", "Translate to English"])

LANGUAGES = [
    "Auto-Detect", "English", "Akan (Twi)", "Spanish", "French", "German",
    "Italian", "Portuguese", "Dutch", "Russian", "Japanese",
    "Chinese", "Arabic", "Hindi", "Swahili", "Yoruba"
]
selected_lang = st.sidebar.selectbox("Spoken Language", LANGUAGES, index=0)

if selected_lang == "Akan (Twi)":
    st.sidebar.info("🇬🇭 **Akan (Twi):** Using custom Hugging Face model.")
elif selected_lang == "Auto-Detect":
    st.sidebar.success("🌐 **Auto-Detect Active.**")

st.sidebar.header("🚀 Performance Options")
export_res = st.sidebar.selectbox(
    "Scale Down Video For Faster CPU Rendering",
    ["Original Resolution", "1080p", "720p (Recommended)", "480p"],
    index=2
)

st.sidebar.header("🎨 Caption Styling")
font_family = st.sidebar.selectbox("Font Style", ["Arial", "Impact", "Arial Black", "Verdana", "Courier New"])
font_size = st.sidebar.slider("Text Size", 10, 100, 24)
text_color = st.sidebar.color_picker("Text Color", "#FFFFFF")

stroke_width = st.sidebar.slider("Stroke Width", 0, 10, 2)
stroke_color = st.sidebar.color_picker("Stroke Color", "#000000")

bg_mode = st.sidebar.selectbox("Background Options", ["No Background", "Drop Shadow", "Solid Background Box"])

if bg_mode == "No Background":
    border_style = 1; shadow_width = 0; final_back_color = hex_to_ass("#000000", 0)
elif bg_mode == "Drop Shadow":
    border_style = 1
    shadow_width = st.sidebar.slider("Shadow Distance", 1, 10, 2)
    final_back_color = hex_to_ass(st.sidebar.color_picker("Shadow Color", "#000000"), 100)
else:
    border_style = 3; shadow_width = 0
    final_back_color = hex_to_ass(st.sidebar.color_picker("Box Color", "#000000"), st.sidebar.slider("Box Opacity (%)", 0, 100, 80))

# --- MAIN APP INTERFACE ---
st.info("⚠️ **Note:** To prevent server overload, maximum file upload size is restricted to 200MB.")
uploaded_file = st.file_uploader("Upload a Video File", type=["mp4", "mov", "avi", "mkv"])

if uploaded_file:
    # 1. Generate the unique hash fingerprint for this exact video
    file_hash = get_file_hash(uploaded_file)

    # 2. Define our file paths using the hash inside the cache folder
    input_video = os.path.join(CACHE_DIR, f"{file_hash}_input.mp4")
    output_srt = os.path.join(CACHE_DIR, f"{file_hash}_subs.srt")
    output_video = os.path.join(CACHE_DIR, f"{file_hash}_final.mp4")
    output_mp3 = os.path.join(CACHE_DIR, f"{file_hash}_audio.mp3")

    # Save the input video to disk
    with open(input_video, "wb") as f:
        f.write(uploaded_file.read())

    st.video(input_video)

    col1, col2, col3 = st.columns(3)
    generate_srt_only = col1.button("📄 Generate SRT Only", type="secondary")
    extract_mp3_only = col2.button("🎵 Extract MP3 Audio", type="secondary")
    generate_and_burn = col3.button("🎬 Generate & Burn Video", type="primary")

    # --- LOGIC BRANCH 1: AUDIO EXTRACTION ---
    if extract_mp3_only:
        # Check if we already extracted this audio before!
        if os.path.exists(output_mp3):
            st.success("⚡ Audio found in cache! Instant download ready.")
            with open(output_mp3, "rb") as f:
                st.download_button("⬇️ Download MP3 File", f, file_name="audio_track.mp3", mime="audio/mpeg")
        else:
            with st.spinner("🎵 Ripping high-quality MP3 audio from video..."):
                try:
                    (
                        ffmpeg.input(input_video)
                        .output(output_mp3, acodec="libmp3lame", q=2)
                        .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
                    )
                    st.success("✅ Audio extracted successfully in seconds!")
                    with open(output_mp3, "rb") as f:
                        st.download_button("⬇️ Download MP3 File", f, file_name="audio_track.mp3", mime="audio/mpeg")
                except ffmpeg.Error as e:
                    st.error(f"FFmpeg Error: {e.stderr.decode('utf-8')}")

    # --- LOGIC BRANCH 2: AI TRANSCRIPTION & VIDEO RENDERING ---
    elif generate_srt_only or generate_and_burn:

        # --- THE CACHE CHECK ---
        # If the SRT file already exists for this video, SKIP Phase 1, 2, and 3 entirely!
        if os.path.exists(output_srt):
            st.success("⚡ Previous transcription found in cache! Skipping AI processing...")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            status_text.info("Phase 1/4: Loading AI Model into Memory...")
            progress_bar.progress(25)

            if selected_lang == "Akan (Twi)":
                pipe = load_akan_model()
                status_text.warning("Phase 2/4: Transcribing Akan Twi Audio (This takes a few minutes...)")
                progress_bar.progress(50)

                result = pipe(input_video, return_timestamps=True)

                status_text.info("Phase 3/4: Formatting Subtitles...")
                progress_bar.progress(75)

                with open(output_srt, "w", encoding="utf-8") as srt_file:
                    for i, chunk in enumerate(result["chunks"], start=1):
                        start_time = chunk["timestamp"][0]
                        end_time = chunk["timestamp"][1] or (start_time + 3.0)
                        srt_file.write(f"{i}\n{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n{chunk['text'].strip()}\n\n")

            else:
                model = load_standard_model(model_size)
                status_text.warning("Phase 2/4: Transcribing Audio (This takes a few minutes...)")
                progress_bar.progress(50)

                options = {}
                if selected_lang != "Auto-Detect":
                    options["language"] = selected_lang.lower()
                if task == "Translate to English":
                    options["task"] = "translate"

                result = model.transcribe(input_video, **options)

                status_text.info("Phase 3/4: Formatting Subtitles...")
                progress_bar.progress(75)

                with open(output_srt, "w", encoding="utf-8") as srt_file:
                    for i, segment in enumerate(result["segments"], start=1):
                        srt_file.write(f"{i}\n{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}\n{segment['text'].strip()}\n\n")

            status_text.success("Phase 3/4 Complete! Transcription saved to cache.")
            progress_bar.progress(100)
            status_text.empty() # Clear the progress bar text

        # --- PHASE 4: RENDERING OR DOWNLOADING ---
        if generate_srt_only:
            st.success("📄 SRT Ready!")
            with open(output_srt, "rb") as f:
                st.download_button("📝 Download .SRT File", f, file_name="subtitles.srt")

        if generate_and_burn:
            with st.spinner(f"🎨 Burning styled captions onto video at {export_res}..."):
                scale_filter = ""
                if export_res == "1080p":
                    scale_filter = "scale=-2:1080,"
                elif export_res == "720p (Recommended)":
                    scale_filter = "scale=-2:720,"
                elif export_res == "480p":
                    scale_filter = "scale=-2:480,"

                style = (
                    f"FontName={font_family},Fontsize={font_size},"
                    f"PrimaryColour={hex_to_ass(text_color)},"
                    f"OutlineColour={hex_to_ass(stroke_color)},"
                    f"BackColour={final_back_color},"
                    f"BorderStyle={border_style},Outline={stroke_width},"
                    f"Shadow={shadow_width},Alignment=2"
                )

                vf_string = f"{scale_filter}subtitles={output_srt}:force_style='{style}'"

                try:
                    (
                        ffmpeg.input(input_video)
                        .output(output_video, vf=vf_string)
                        .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
                    )
                    st.success("✅ Complete! Video Rendering Finished.")

                    colA, colB = st.columns(2)
                    with open(output_video, "rb") as f:
                        colA.download_button("⬇️ Download Captioned Video", f, file_name="captioned_video.mp4")
                    with open(output_srt, "rb") as f:
                        colB.download_button("📝 Download .SRT File", f, file_name="subtitles.srt")

                except ffmpeg.Error as e:
                    st.error(f"Error burning subtitles: {e.stderr.decode('utf-8')}")