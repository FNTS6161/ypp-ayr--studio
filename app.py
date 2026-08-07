"""
YPP AUTO-STUDIO v2.0
High-CPM Video Generator - Streamlit Web App
Single-file architecture: UI + state management + API calls + video processing.

NOTE ON BACKGROUND FOOTAGE:
The original spec does not define a stock-footage/background source. To keep the
pipeline fully runnable end-to-end, this app lets the user optionally upload a
background video/image; if none is supplied, an animated gradient (Ken Burns
style zoom) is generated automatically as a fallback canvas for the subtitles,
effects and CTA to be composited onto.
"""

import os
import re
import time
import uuid
import asyncio
import tempfile
import traceback

import numpy as np
import streamlit as st

# ------------------------------------------------------------------------------------
# PAGE CONFIG (must be first Streamlit call)
# ------------------------------------------------------------------------------------
st.set_page_config(
    page_title="YPP Auto-Studio v2.0",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------------------------------
# CUSTOM CSS — dark theme + mobile responsiveness
# ------------------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Tighten default padding on mobile */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 4rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 760px;
    }
    /* Header banner */
    .ypp-header {
        background: linear-gradient(135deg, #1a1c24 0%, #0e1117 100%);
        border: 1px solid #FFD400;
        border-radius: 14px;
        padding: 18px 16px;
        margin-bottom: 18px;
        text-align: center;
    }
    .ypp-header h1 {
        font-size: 1.35rem;
        margin: 0;
        color: #FFD400;
        letter-spacing: 0.5px;
    }
    .ypp-header p {
        margin: 4px 0 0 0;
        color: #9aa0a6;
        font-size: 0.85rem;
    }
    /* Section cards */
    .ypp-section {
        background: #161B22;
        border-radius: 12px;
        padding: 14px 16px 6px 16px;
        margin-bottom: 16px;
        border: 1px solid #262b34;
    }
    .ypp-section h3 {
        font-size: 1.0rem;
        color: #FFD400;
        margin-top: 0;
        margin-bottom: 10px;
    }
    /* Primary action button */
    div.stButton > button {
        background: linear-gradient(135deg, #FFD400, #FFB300);
        color: #111 !important;
        font-weight: 700;
        border-radius: 10px;
        border: none;
        padding: 0.75rem 1rem;
        width: 100%;
        font-size: 1.0rem;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #FFE04D, #FFC233);
        color: #000 !important;
    }
    /* Log terminal look */
    .stCodeBlock, code {
        font-size: 0.78rem !important;
    }
    @media (max-width: 480px) {
        .ypp-header h1 { font-size: 1.1rem; }
        .ypp-section { padding: 10px 12px 4px 12px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------------
# STATIC CONFIG / LOOKUP TABLES
# ------------------------------------------------------------------------------------

LANGUAGES = {
    "Türkçe (tr-TR)": {"code": "tr-TR", "voice": "tr-TR-AhmetNeural", "cta": "🔔 ABONE OL"},
    "Almanca (de-DE) - High CPM": {"code": "de-DE", "voice": "de-DE-KillianNeural", "cta": "🔔 ABONNIEREN"},
    "İngilizce (en-US) - High CPM": {"code": "en-US", "voice": "en-US-ChristopherNeural", "cta": "🔔 SUBSCRIBE"},
    "İspanyolca (es-ES)": {"code": "es-ES", "voice": "es-ES-AlvaroNeural", "cta": "🔔 SUSCRÍBETE"},
    "Fransızca (fr-FR)": {"code": "fr-FR", "voice": "fr-FR-HenriNeural", "cta": "🔔 ABONNEZ-VOUS"},
}

SUBTITLE_TEMPLATES = {
    "Yellow Pop-Up (Shorts Trend)": {
        "color": "black",
        "bg_color": "#FFD400",
        "stroke_color": "black",
        "stroke_width": 2,
        "font_size_ratio": 0.075,
    },
    "White Box": {
        "color": "black",
        "bg_color": "white",
        "stroke_color": None,
        "stroke_width": 0,
        "font_size_ratio": 0.065,
    },
    "Neon Green": {
        "color": "#39FF14",
        "bg_color": None,
        "stroke_color": "black",
        "stroke_width": 3,
        "font_size_ratio": 0.075,
    },
}

SUB_POSITION_MAP = {"Üst": "top", "Orta": "center", "Alt": "bottom"}

EMOJI_MAP = {
    "money": "💰", "para": "💰", "dinero": "💰", "geld": "💰", "argent": "💰",
    "love": "❤️", "aşk": "❤️", "amor": "❤️", "liebe": "❤️", "amour": "❤️",
    "fire": "🔥", "ateş": "🔥", "fuego": "🔥", "feuer": "🔥", "feu": "🔥",
    "win": "🏆", "kazan": "🏆", "gana": "🏆", "gewinn": "🏆", "gagner": "🏆",
    "shock": "😱", "şok": "😱", "increíble": "😱", "unglaublich": "😱", "incroyable": "😱",
    "secret": "🤫", "sır": "🤫", "secreto": "🤫", "geheimnis": "🤫", "secret_fr": "🤫",
    "time": "⏰", "zaman": "⏰", "tiempo": "⏰", "zeit": "⏰", "temps": "⏰",
    "star": "⭐", "yıldız": "⭐", "estrella": "⭐", "stern": "⭐", "étoile": "⭐",
    "warning": "⚠️", "dikkat": "⚠️", "peligro": "⚠️", "achtung": "⚠️", "attention": "⚠️",
    "success": "✅", "başarı": "✅", "éxito": "✅", "erfolg": "✅", "succès": "✅",
}

OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------------------------------------
# SESSION STATE INIT
# ------------------------------------------------------------------------------------
if "logs" not in st.session_state:
    st.session_state.logs = []
if "final_video_path" not in st.session_state:
    st.session_state.final_video_path = None
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{ts}] {msg}")


# ------------------------------------------------------------------------------------
# HEADER
# ------------------------------------------------------------------------------------
st.markdown(
    """
    <div class="ypp-header">
        <h1>🎬 YPP AUTO-STUDIO v2.0</h1>
        <p>High-CPM Video Generator</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------------
# API KEY (Gemini) — required, kept in session only
# ------------------------------------------------------------------------------------
with st.expander("🔑 API Anahtarı (Gemini) — zorunlu", expanded=not bool(st.secrets.get("GEMINI_API_KEY", ""))):
    default_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    gemini_api_key = st.text_input(
        "Google Gemini API Key",
        value=default_key,
        type="password",
        help="https://aistudio.google.com/app/apikey adresinden ücretsiz alabilirsiniz.",
    )

# ------------------------------------------------------------------------------------
# SECTION 1 — Content & Target Region (CPM) Settings
# ------------------------------------------------------------------------------------
st.markdown('<div class="ypp-section"><h3>📝 1. İçerik & Hedef Bölge (CPM) Ayarları</h3>', unsafe_allow_html=True)

topic = st.text_input("Video Konusu / Başlık", placeholder="Örn: 5 Şaşırtıcı Uzay Gerçeği")

target_language = st.selectbox("Hedef Dil / Bölge", list(LANGUAGES.keys()), index=2)

video_format = st.radio(
    "Video Formatı",
    ["Dikey Shorts (9:16)", "Yatay Long-Form (16:9)"],
    horizontal=True,
)

bg_file = st.file_uploader(
    "Arkaplan Görsel/Video (opsiyonel — boş bırakılırsa otomatik animasyonlu arkaplan oluşturulur)",
    type=["mp4", "mov", "jpg", "jpeg", "png"],
)

st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------
# SECTION 2 — Subtitles, Effects & Styling
# ------------------------------------------------------------------------------------
st.markdown('<div class="ypp-section"><h3>🎨 2. Altyazı, Efekt & Stil</h3>', unsafe_allow_html=True)

subtitle_template = st.selectbox("Altyazı Şablonu", list(SUBTITLE_TEMPLATES.keys()))
subtitle_position_tr = st.radio("Altyazı Konumu", list(SUB_POSITION_MAP.keys()), horizontal=True)

st.write("**Video Efektleri**")
fx_flip = st.checkbox("Horizontal Flip (Aynalama - Telif Önleyici)", value=True)
fx_emoji = st.checkbox("Dynamic Emojis (Word-based auto-emojis)", value=True)
fx_color = st.checkbox("Color Filter (Cinematic Cold / Warm / Vintage)", value=True)
color_filter_type = None
if fx_color:
    color_filter_type = st.selectbox("Filtre Tipi", ["Cold", "Warm", "Vintage"], label_visibility="collapsed")
fx_cta = st.checkbox('Dynamic Call to Action ("Abone Ol" / "Subscribe")', value=True)

st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------
# SECTION 3 — YPP & Copyright Protection Controls
# ------------------------------------------------------------------------------------
st.markdown('<div class="ypp-section"><h3>🛡️ 3. YPP & Telif Koruma Kontrolleri</h3>', unsafe_allow_html=True)
fx_anticopy = st.checkbox(
    "Reused Content Anti-Copyright Filter (%100 Özgünleştirme & Dynamic Zoom/Pan)",
    value=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------
# PRIMARY ACTION
# ------------------------------------------------------------------------------------
run_clicked = st.button("🚀 VİDEOYU ÜRET VE BULUTA YÜKLE", disabled=st.session_state.is_processing)

progress_placeholder = st.empty()
log_placeholder = st.empty()


def render_logs():
    log_placeholder.code("\n".join(st.session_state.logs[-200:]) or "…", language="log")


# ------------------------------------------------------------------------------------
# BACKEND: SCRIPT GENERATION (Gemini)
# ------------------------------------------------------------------------------------
def generate_script(api_key: str, topic: str, lang_name: str, fmt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')


    is_short = "Dikey" in fmt
    length_hint = "45-60 saniyede seslendirilecek, çok yüksek retention'lı kısa bir Shorts" if is_short else \
        "3-5 dakikada seslendirilecek, bölümlere ayrılmış uzun formatlı bir video"

    prompt = f"""
Sen viral YouTube senaristisisin. Aşağıdaki konu için tamamen ÖZGÜN (telifsiz, hiçbir kaynaktan alıntı olmayan),
{lang_name.split(' ')[0]} dilinde, {length_hint} anlatım metni yaz.

Konu: "{topic}"

Kurallar:
- İlk cümle güçlü bir "hook" olsun (izleyiciyi ilk 3 saniyede yakalasın).
- Sadece seslendirilecek düz metni yaz. Sahne yönergesi, parantez içi not, markdown, başlık YAZMA.
- Doğal, konuşma diline uygun, akıcı cümleler kullan.
- Video sonunda doğal bir şekilde kanalı takip etmeye teşvik eden bir kapanış cümlesi ekle.
"""
    response = model.generate_content(prompt)
    script_text = (response.text or "").strip()
    script_text = re.sub(r"[*_#`]", "", script_text)
    return script_text


# ------------------------------------------------------------------------------------
# BACKEND: TEXT-TO-SPEECH (edge-tts) WITH WORD-LEVEL TIMINGS
# ------------------------------------------------------------------------------------
async def _synthesize_async(text: str, voice: str, out_path: str):
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    word_boundaries = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append(
                    {
                        "text": chunk["text"],
                        "start": chunk["offset"] / 10_000_000,   # 100-ns units -> seconds
                        "duration": chunk["duration"] / 10_000_000,
                    }
                )
    return word_boundaries


def synthesize_speech(text: str, voice: str, out_path: str):
    return asyncio.run(_synthesize_async(text, voice, out_path))


# ------------------------------------------------------------------------------------
# BACKEND: VIDEO COMPOSITION (moviepy 1.0.3 API — use .set_position(), not .set_pos())
# ------------------------------------------------------------------------------------
def _make_fallback_background(duration: float, size):
    """Animated gradient + slow zoom (Ken Burns) used when no footage is uploaded."""
    from moviepy.editor import VideoClip

    w, h = size
    base = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / max(h - 1, 1)
        base[y, :, 0] = int(20 + 40 * t)
        base[y, :, 1] = int(10 + 20 * t)
        base[y, :, 2] = int(60 + 80 * (1 - t))

    def make_frame(t):
        zoom = 1.0 + 0.05 * (t / max(duration, 1))
        frame = base.copy()
        return frame

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.resize(size)
    return clip


def _apply_color_filter(clip, filter_type: str):
    def cold(image):
        img = image.astype(np.float32)
        img[:, :, 2] = np.clip(img[:, :, 2] * 1.15, 0, 255)  # boost blue
        img[:, :, 0] = np.clip(img[:, :, 0] * 0.95, 0, 255)  # reduce red
        return img.astype("uint8")

    def warm(image):
        img = image.astype(np.float32)
        img[:, :, 0] = np.clip(img[:, :, 0] * 1.15, 0, 255)  # boost red
        img[:, :, 1] = np.clip(img[:, :, 1] * 1.05, 0, 255)  # slight green
        img[:, :, 2] = np.clip(img[:, :, 2] * 0.9, 0, 255)   # reduce blue
        return img.astype("uint8")

    def vintage(image):
        img = image.astype(np.float32)
        sepia = np.array(
            [[0.393, 0.769, 0.189],
             [0.349, 0.686, 0.168],
             [0.272, 0.534, 0.131]]
        )
        img = img @ sepia.T
        img = np.clip(img * 0.85, 0, 255)
        return img.astype("uint8")

    fx = {"Cold": cold, "Warm": warm, "Vintage": vintage}.get(filter_type)
    if fx is None:
        return clip
    return clip.fl_image(fx)


def _build_word_subtitle_clips(word_boundaries, template: dict, position: str, size, use_emoji: bool):
    from moviepy.editor import TextClip, CompositeVideoClip

    w, h = size
    font_size = max(int(h * template["font_size_ratio"]), 24)
    clips = []

    pos_y = {"top": h * 0.12, "center": h * 0.46, "bottom": h * 0.78}[position]

    # Group words into short phrases (3-4 words) for readable pop-up captions
    phrase_size = 3
    for i in range(0, len(word_boundaries), phrase_size):
        group = word_boundaries[i:i + phrase_size]
        if not group:
            continue
        phrase = " ".join(g["text"] for g in group).strip()
        if use_emoji:
            for key, emoji in EMOJI_MAP.items():
                if key in phrase.lower():
                    phrase = f"{phrase} {emoji}"
                    break
        start = group[0]["start"]
        end = group[-1]["start"] + group[-1]["duration"]
        dur = max(end - start, 0.15)

        txt_kwargs = dict(
            text=phrase,
            fontsize=font_size,
            color=template["color"],
            font="Arial-Bold",
            method="caption",
            size=(int(w * 0.9), None),
            align="center",
        )
        if template["bg_color"]:
            txt_kwargs["bg_color"] = template["bg_color"]
        if template["stroke_color"]:
            txt_kwargs["stroke_color"] = template["stroke_color"]
            txt_kwargs["stroke_width"] = template["stroke_width"]

        try:
            txt_clip = TextClip(**txt_kwargs)
        except Exception:
            # Fallback if ImageMagick / caption mode unavailable
            txt_kwargs.pop("method", None)
            txt_kwargs.pop("size", None)
            txt_kwargs.pop("align", None)
            txt_clip = TextClip(**txt_kwargs)

        txt_clip = (
            txt_clip
            .set_start(start)
            .set_duration(dur)
            .set_position(("center", pos_y))
        )
        clips.append(txt_clip)

    return clips


def _build_cta_clip(cta_text: str, size, total_duration: float, position="bottom"):
    from moviepy.editor import TextClip

    w, h = size
    y = h * 0.88 if position == "bottom" else h * 0.06
    cta = TextClip(
        cta_text,
        fontsize=max(int(h * 0.045), 22),
        color="white",
        font="Arial-Bold",
        bg_color="red",
        method="label",
    )
    interval = 15.0
    fragments = []
    t = 3.0
    while t < total_duration:
        frag = (
            cta.copy()
            .set_start(t)
            .set_duration(min(3.0, max(total_duration - t, 0)))
            .set_position(("center", y))
        )
        fragments.append(frag)
        t += interval
    return fragments


def compose_video(
    script_text,
    audio_path,
    word_boundaries,
    bg_upload_path,
    video_format,
    fx_flip,
    fx_color,
    color_filter_type,
    subtitle_template_name,
    subtitle_position,
    fx_emoji,
    fx_cta,
    cta_text,
    fx_anticopy,
    out_path,
):
    from moviepy.editor import (
        VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, vfx
    )

    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    size = (1080, 1920) if "Dikey" in video_format else (1920, 1080)

    # --- Background ---
    if bg_upload_path:
        ext = os.path.splitext(bg_upload_path)[1].lower()
        if ext in (".mp4", ".mov"):
            bg = VideoFileClip(bg_upload_path)
            if bg.duration < duration:
                loops = int(duration // bg.duration) + 1
                bg = bg.fx(vfx.loop, n=loops)
            bg = bg.subclip(0, duration)
        else:
            bg = ImageClip(bg_upload_path).set_duration(duration)
        bg = bg.resize(height=size[1]) if bg.h / bg.w < size[1] / size[0] else bg.resize(width=size[0])
        bg = bg.crop(
            x_center=bg.w / 2, y_center=bg.h / 2, width=size[0], height=size[1]
        )
    else:
        bg = _make_fallback_background(duration, size)

    # --- Anti-copyright: dynamic zoom/pan ---
    if fx_anticopy:
        bg = bg.fx(vfx.resize, lambda t: 1.0 + 0.03 * (t / max(duration, 1)))
        bg = bg.set_position(("center", "center"))

    # --- Horizontal flip ---
    if fx_flip:
        bg = bg.fx(vfx.mirror_x)

    # --- Color filter ---
    if fx_color and color_filter_type:
        bg = _apply_color_filter(bg, color_filter_type)

    bg = bg.set_duration(duration)

    layers = [bg]

    # --- Subtitles ---
    template = SUBTITLE_TEMPLATES[subtitle_template_name]
    if word_boundaries:
        layers.extend(
            _build_word_subtitle_clips(word_boundaries, template, subtitle_position, size, fx_emoji)
        )

    # --- CTA ---
    if fx_cta:
        layers.extend(_build_cta_clip(cta_text, size, duration))

    final = CompositeVideoClip(layers, size=size).set_duration(duration)
    final = final.set_audio(audio_clip)

    final.write_videofile(
        out_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=2,
        preset="medium",
        logger=None,
    )
    final.close()
    audio_clip.close()
    if bg_upload_path and os.path.splitext(bg_upload_path)[1].lower() in (".mp4", ".mov"):
        bg.close()


# ------------------------------------------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------------------------------------------
def run_pipeline():
    st.session_state.logs = []
    st.session_state.final_video_path = None
    progress = progress_placeholder.progress(0, text="Başlatılıyor…")

    try:
        if not gemini_api_key:
            log("❌ HATA: Gemini API anahtarı girilmedi.")
            render_logs()
            progress.progress(0, text="Durduruldu — API anahtarı eksik")
            return
        if not topic.strip():
            log("❌ HATA: Video konusu boş olamaz.")
            render_logs()
            progress.progress(0, text="Durduruldu — konu eksik")
            return

        lang_info = LANGUAGES[target_language]

        with tempfile.TemporaryDirectory() as tmpdir:
            # ---- STEP 1: Script generation ----
            log(f"▶ Adım 1/4: Senaryo üretiliyor (Gemini-1.5-flash) — dil: {lang_info['code']}")
            render_logs()
            progress.progress(10, text="Senaryo yazılıyor…")
            script_text = generate_script(gemini_api_key, topic, target_language, video_format)
            log(f"✅ Senaryo hazır ({len(script_text.split())} kelime).")
            render_logs()
            progress.progress(30, text="Senaryo tamamlandı")

            # ---- STEP 2: TTS ----
            log(f"▶ Adım 2/4: Seslendirme üretiliyor (edge-tts, ses: {lang_info['voice']})")
            render_logs()
            progress.progress(40, text="Ses üretiliyor…")
            audio_path = os.path.join(tmpdir, "voice.mp3")
            word_boundaries = synthesize_speech(script_text, lang_info["voice"], audio_path)
            log(f"✅ Ses dosyası oluşturuldu ({len(word_boundaries)} kelime zamanlaması yakalandı).")
            render_logs()
            progress.progress(55, text="Seslendirme tamamlandı")

            # ---- Save uploaded background (if any) ----
            bg_path = None
            if bg_file is not None:
                bg_path = os.path.join(tmpdir, f"bg{os.path.splitext(bg_file.name)[1]}")
                with open(bg_path, "wb") as f:
                    f.write(bg_file.getbuffer())
                log("📎 Kullanıcı arkaplanı yüklendi.")
            else:
                log("ℹ️ Arkaplan verilmedi — otomatik animasyonlu arkaplan üretilecek.")
            render_logs()

            # ---- STEP 3: Render video ----
            log("▶ Adım 3/4: Video render ediliyor (moviepy/ffmpeg) — flip, renk filtresi, altyazı, CTA")
            render_logs()
            progress.progress(65, text="Video birleştiriliyor…")

            out_filename = f"ypp_{uuid.uuid4().hex[:10]}.mp4"
            out_path = os.path.join(OUTPUT_DIR, out_filename)

            compose_video(
                script_text=script_text,
                audio_path=audio_path,
                word_boundaries=word_boundaries,
                bg_upload_path=bg_path,
                video_format=video_format,
                fx_flip=fx_flip,
                fx_color=fx_color,
                color_filter_type=color_filter_type,
                subtitle_template_name=subtitle_template,
                subtitle_position=SUB_POSITION_MAP[subtitle_position_tr],
                fx_emoji=fx_emoji,
                fx_cta=fx_cta,
                cta_text=lang_info["cta"],
                fx_anticopy=fx_anticopy,
                out_path=out_path,
            )
            log("✅ Video render tamamlandı.")
            render_logs()
            progress.progress(90, text="Render tamamlandı")

            # ---- STEP 4: Save/output ----
            log(f"▶ Adım 4/4: Çıktı kaydedildi → /output/{out_filename}")
            st.session_state.final_video_path = out_path
            render_logs()
            progress.progress(100, text="Tamamlandı 🎉")
            log("🚀 İşlem tamamlandı. Aşağıdan önizleyip indirebilirsiniz.")
            render_logs()

    except Exception as e:
        log(f"❌ HATA: {e}")
        log(traceback.format_exc(limit=3))
        render_logs()
        progress.progress(0, text="Hata oluştu")


if run_clicked:
    st.session_state.is_processing = True
    run_pipeline()
    st.session_state.is_processing = False

render_logs()

# ------------------------------------------------------------------------------------
# OUTPUT: PREVIEW + DOWNLOAD
# ------------------------------------------------------------------------------------
if st.session_state.final_video_path and os.path.exists(st.session_state.final_video_path):
    st.markdown('<div class="ypp-section"><h3>📼 Sonuç</h3>', unsafe_allow_html=True)
    st.video(st.session_state.final_video_path)
    with open(st.session_state.final_video_path, "rb") as f:
        st.download_button(
            "⬇️ Videoyu İndir (.mp4)",
            data=f,
            file_name=os.path.basename(st.session_state.final_video_path),
            mime="video/mp4",
        )
    st.markdown("</div>", unsafe_allow_html=True)
