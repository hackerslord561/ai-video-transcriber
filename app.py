import streamlit as st
import whisper
import ffmpeg
import os
import hashlib
import shutil
import requests
from deep_translator import GoogleTranslator # --- NEW: The Translation Bridge ---

# --- SILENCE NOISY AI WARNINGS ---
import warnings
from transformers import pipeline, logging as hf_logging
warnings.filterwarnings("ignore")
hf_logging.set_verbosity_error()

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Video Transcriber", layout="wide", page_icon="🎬")
st.title("🎬 Comprehensive AI Video Transcriber & Captioner")

# --- INITIALIZE SESSION STATE FOR UI PERSISTENCE ---
if "action_type" not in st.session_state:
    st.session_state.action_type = None

# --- CREATE CACHE FOLDER ---
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
        model="facebook/mms-1b-all",
        model_kwargs={"target_lang": "aka", "ignore_mismatched_sizes": True},
        device="cpu"
    )

# --- UTILITY FUNCTIONS ---
def get_file_hash(uploaded_file):
    sha256_hash = hashlib.sha256()
    for chunk in iter(lambda: uploaded_file.read(4096), b""):
        sha256_hash.update(chunk)
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
    st.sidebar.info("🇬🇭 **Akan (Twi):** Powered by Meta MMS Enterprise Model.")
elif selected_lang == "Auto-Detect":
    st.sidebar.success("🌐 **Auto-Detect Active.**")

st.sidebar.header("🚀 Performance Options")
export_res = st.sidebar.selectbox(
    "Scale Down Video For Faster CPU Rendering",
    ["Original Resolution", "1080p", "720p (Recommended)", "480p"],
    index=2
)

st.sidebar.header("🗑️ Storage Management")
if st.sidebar.button("Clear Server Cache"):
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR)
    st.sidebar.success("✅ Server cache completely wiped!")

# --- MONETIZATION: SECURE EMAIL & SUBSCRIPTION CHECK ---
st.sidebar.header("🏷️ Branding (Watermark)")

PAYSTACK_SECRET = os.environ.get("PAYSTACK_SECRET_KEY")

def verify_subscription(sub_code, user_email):
    if not PAYSTACK_SECRET or not user_email or not sub_code:
        return False

    url = f"https://api.paystack.co/subscription/{sub_code}"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Cache-Control": "no-cache"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            status = data.get("data", {}).get("status")
            api_email = data.get("data", {}).get("customer", {}).get("email", "")

            if status == "active" and api_email.strip().lower() == user_email.strip().lower():
                return True
        return False
    except:
        return False

user_email_input = st.sidebar.text_input("📧 Enter your Email Address")

if user_email_input:
    st.sidebar.info(f"⚠️ **IMPORTANT:** When purchasing your subscription on Paystack, you MUST use exactly **{user_email_input}** or your code will not work!")
else:
    st.sidebar.warning("⚠️ Enter your email address above to unlock or purchase a subscription.")

pro_input = st.sidebar.text_input("🔑 Enter Paystack Subscription Code (e.g., SUB_...)", type="password")

is_pro = False
if pro_input and user_email_input:
    with st.sidebar:
        with st.spinner("Verifying email and subscription securely..."):
            is_pro = verify_subscription(pro_input, user_email_input)

if is_pro:
    st.sidebar.success("🔓 Active Subscription Confirmed! Watermark tools unlocked.")
    watermark_text = st.sidebar.text_input("Watermark Text (Leave blank for none)", "")
    watermark_size = st.sidebar.slider("Watermark Text Size", 10, 100, 24)
    watermark_opacity = st.sidebar.slider("Watermark Opacity", 0.0, 1.0, 0.5)
else:
    st.sidebar.error("🔒 App renders with 'Hackerslord Studios' watermark.")
    if pro_input and user_email_input:
        st.sidebar.error("❌ Verification failed. Code is invalid, inactive, or does not match this email address.")

    paystack_url = "https://paystack.shop/pay/spb9j8vcmc"
    st.sidebar.markdown(f"**[💳 Subscribe for $2/month to remove watermarks!]({paystack_url})**")

    watermark_text = "Hackerslord Studios"
    watermark_size = 24
    watermark_opacity = 0.5

# --- CAPTION STYLING ---
st.sidebar.header("🎨 Caption Styling")
font_family = st.sidebar.selectbox("Font Style", ["Arial", "Impact", "Arial Black", "Verdana", "Courier New"])
font_size = st.sidebar.slider("Caption Text Size", 10, 100, 24)
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
    file_hash = get_file_hash(uploaded_file)

    input_video = os.path.join(CACHE_DIR, f"{file_hash}_input.mp4")
    output_srt = os.path.join(CACHE_DIR, f"{file_hash}_subs.srt")
    output_txt = os.path.join(CACHE_DIR, f"{file_hash}_transcript.txt")
    output_video = os.path.join(CACHE_DIR, f"{file_hash}_final.mp4")
    output_mp3 = os.path.join(CACHE_DIR, f"{file_hash}_audio.mp3")

    with open(input_video, "wb") as f:
        f.write(uploaded_file.read())

    st.video(input_video)

    col1, col2, col3, col4 = st.columns(4)
    if col1.button("📄 Generate SRT", type="secondary"): st.session_state.action_type = "srt"
    if col2.button("📝 Generate TXT", type="secondary"): st.session_state.action_type = "txt"
    if col3.button("🎵 Extract MP3", type="secondary"): st.session_state.action_type = "mp3"
    if col4.button("🎬 Burn Video", type="primary"): st.session_state.action_type = "burn"

    # --- PROCESSING BLOCK ---
    if st.session_state.action_type == "mp3":
        if not os.path.exists(output_mp3):
            with st.spinner("🎵 Ripping high-quality MP3 audio from video..."):
                try:
                    (
                        ffmpeg.input(input_video)
                        .output(output_mp3, acodec="libmp3lame", q=2)
                        .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
                    )
                except ffmpeg.Error as e:
                    st.error(f"FFmpeg Error: {e.stderr.decode('utf-8')}")

    elif st.session_state.action_type in ["srt", "txt", "burn"]:
        if not (os.path.exists(output_srt) and os.path.exists(output_txt)):
            progress_bar = st.progress(0)
            status_text = st.empty()

            status_text.info("Phase 1/4: Loading AI Model into Memory...")
            progress_bar.progress(25)

            if selected_lang == "Akan (Twi)":
                pipe = load_akan_model()
                status_text.warning("Phase 2/4: Transcribing with Meta MMS (This takes a few minutes...)")
                progress_bar.progress(50)

                result = pipe(
                    input_video,
                    chunk_length_s=30,
                    return_timestamps="word"
                )

                status_text.info("Phase 3/4: Formatting & Translating Subtitles...")
                progress_bar.progress(75)

                with open(output_srt, "w", encoding="utf-8") as srt_file, open(output_txt, "w", encoding="utf-8") as txt_file:
                    chunks_data = result.get("chunks", [])

                    srt_idx = 1
                    current_chunk = {"text": "", "start": None, "end": None}

                    for word_data in chunks_data:
                        word = word_data["text"]
                        timestamp = word_data.get("timestamp", (None, None))
                        start, end = timestamp

                        if start is None or end is None:
                            continue

                        if current_chunk["start"] is None:
                            current_chunk["start"] = start
                            current_chunk["end"] = end
                            current_chunk["text"] = word

                        elif (end - current_chunk["start"]) <= 3.0:
                            current_chunk["end"] = end
                            current_chunk["text"] = (current_chunk["text"] + " " + word).strip()

                        else:
                            final_text = current_chunk['text'].strip()

                            # --- INTERCEPT & TRANSLATE ---
                            if task == "Translate to English" and final_text:
                                try:
                                    final_text = GoogleTranslator(source='auto', target='en').translate(final_text)
                                except:
                                    pass # If the API fails for a second, it falls back to original Twi

                            srt_file.write(f"{srt_idx}\n{format_timestamp(current_chunk['start'])} --> {format_timestamp(current_chunk['end'])}\n{final_text}\n\n")
                            txt_file.write(f"{final_text}\n")
                            srt_idx += 1
                            current_chunk = {"start": start, "end": end, "text": word}

                    if current_chunk["start"] is not None:
                        final_text = current_chunk['text'].strip()

                        # --- INTERCEPT & TRANSLATE FOR THE FINAL CHUNK ---
                        if task == "Translate to English" and final_text:
                            try:
                                final_text = GoogleTranslator(source='auto', target='en').translate(final_text)
                            except:
                                pass

                        srt_file.write(f"{srt_idx}\n{format_timestamp(current_chunk['start'])} --> {format_timestamp(current_chunk['end'])}\n{final_text}\n\n")
                        txt_file.write(f"{final_text}\n")

            else:
                model = load_standard_model(model_size)
                status_text.warning("Phase 2/4: Transcribing Audio (This takes a few minutes...)")
                progress_bar.progress(50)

                options = {
                    "fp16": False,
                    "condition_on_prev_tokens": False
                }

                if selected_lang != "Auto-Detect":
                    options["language"] = selected_lang.lower()
                if task == "Translate to English":
                    options["task"] = "translate"

                try:
                    result = model.transcribe(input_video, **options)
                except RuntimeError as e:
                    st.error(f"Transcription failed: {e}. Please try a different video or model size.")
                    result = {"segments": []}

                status_text.info("Phase 3/4: Formatting Subtitles...")
                progress_bar.progress(75)

                with open(output_srt, "w", encoding="utf-8") as srt_file, open(output_txt, "w", encoding="utf-8") as txt_file:
                    for i, segment in enumerate(result.get("segments", []), start=1):
                        text = segment['text'].strip()
                        srt_file.write(f"{i}\n{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}\n{text}\n\n")
                        txt_file.write(f"{text}\n")

            progress_bar.progress(100)
            status_text.empty()

        if st.session_state.action_type == "burn" and not os.path.exists(output_video):
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

                if watermark_text:
                    safe_text = watermark_text.replace("'", "\\'").replace(":", "\\:")
                    drawtext_filter = f",drawtext=text='{safe_text}':fontcolor=white@{watermark_opacity}:fontsize={watermark_size}:x=w-tw-20:y=20"
                    vf_string += drawtext_filter

                try:
                    (
                        ffmpeg.input(input_video)
                        .output(output_video, vf=vf_string)
                        .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
                    )
                except ffmpeg.Error as e:
                    st.error(f"Error burning subtitles: {e.stderr.decode('utf-8')}")

    # --- PERSISTENT DOWNLOAD PANEL ---
    if st.session_state.action_type:
        st.markdown("---")
        st.subheader("🎉 Your Files are Ready!")

        dl_col1, dl_col2, dl_col3, dl_col4 = st.columns(4)

        if st.session_state.action_type == "mp3" and os.path.exists(output_mp3):
            with open(output_mp3, "rb") as f:
                dl_col1.download_button("⬇️ Download MP3", f, file_name="audio_track.mp3", mime="audio/mpeg")

        elif st.session_state.action_type in ["srt", "txt", "burn"]:
            if os.path.exists(output_srt):
                with open(output_srt, "rb") as f:
                    dl_col1.download_button("📝 Download .SRT", f, file_name="subtitles.srt")
            if os.path.exists(output_txt):
                with open(output_txt, "rb") as f:
                    dl_col2.download_button("📄 Download .TXT", f, file_name="transcript.txt")
            if st.session_state.action_type == "burn" and os.path.exists(output_video):
                with open(output_video, "rb") as f:
                    dl_col3.download_button("🎬 Download Video", f, file_name="hackerslord_captioned.mp4")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("❌ Close & Clear Results"):
            st.session_state.action_type = None
            st.rerun()