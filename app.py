"""
YPP AUTO-STUDIO v3.0 Pro
High-CPM Video Generator - Streamlit Web App
ElevenLabs TTS, Word-by-Word Pop-up Subtitles, Background Music & Multi-API Integration
"""

import os
import re
import time
import uuid
import asyncio
import tempfile
import traceback
import requests

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import streamlit as st
from groq import Groq

# ------------------------------------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------------------------------------
st.set_page_config(
    page_title="YPP Auto-Studio v3.0 Pro",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------------------------------
# CUSTOM CSS
# ------------------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 4rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 760px;
    }
    .ypp-header {
        background: linear-gradient(135deg, #1a1c24 0%, #0e1117 100%);
        border: 1px solid #FFD400;
        border-radius: 14px;
        padding: 18px 16px;
        margin-bottom: 18px;
        text-align: center;
    }
    .ypp-header h1 {
        font-size: 1.4rem;
        margin: 0;
        color: #FFD400;
        letter-spacing: 0.5px;
    }
    .ypp-header p {
        margin: 4px 0 0 0;
        color: #9aa0a6;
        font-size: 0.85rem;
    }
    .ypp-section {
        background: #161B22;
        border-radius: 12px;
        padding: 14px 16px 14px 16px;
        margin-bottom: 16px;
        border: 1px solid #262b34;
    }
    .ypp-section h3 {
        font-size: 1.0rem;
        color: #FFD400;
        margin-top: 0;
        margin-bottom: 10px;
    }
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
    .stCodeBlock, code {
        font-size: 0.78rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------------
# CONFIG & LOOKUPS
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
        "color": "#111111",
        "bg_color": "#FFD400",
        "stroke_color": "#000000",
        "stroke_width": 0,
        "font_size_ratio": 0.042,
    },
    "White Box": {
        "color": "#000000",
        "bg_color": "#FFFFFF",
        "stroke_color": None,
        "stroke_width": 0,
        "font_size_ratio": 0.038,
    },
    "Neon Green Stroke": {
        "color": "#39FF14",
        "bg_color": None,
        "stroke_color": "#000000",
        "stroke_width": 3,
        "font_size_ratio": 0.045,
    },
}

SUB_POSITION_MAP = {"Üst": "top", "Orta": "center", "Alt": "bottom"}

EMOJI_MAP = {
    "money": "💰", "para": "💰", "dinero": "💰", "geld": "💰",
    "love": "❤️", "aşk": "❤️", "amor": "❤️", "liebe": "❤️",
    "fire": "🔥", "ateş": "🔥", "fuego": "🔥", "feuer": "🔥",
    "win": "🏆", "kazan": "🏆", "gana": "🏆", "gewinn": "🏆",
    "shock": "😱", "şok": "😱",
    "secret": "🤫", "sır": "🤫",
    "time": "⏰", "zaman": "⏰",
    "star": "⭐", "yıldız": "⭐",
    "warning": "⚠️", "dikkat": "⚠️",
}

OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------------------------------------
# SESSION STATE
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
# HEADER & UI
# ------------------------------------------------------------------------------------
st.markdown(
    """
    <div class="ypp-header">
        <h1>🎬 YPP AUTO-STUDIO v3.0 Pro</h1>
        <p>High-CPM Video Generator (ElevenLabs + Pop-Up Subtitles)</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("🔑 API Anahtarları (Kullanıcı Ayarları)", expanded=True):
    groq_api_key = st.text_input(
        "Groq API Key (Senaryo Üretimi - Zorunlu)",
        value=st.secrets.get("GROQ_API_KEY", ""),
        type="password",
        help="https://console.groq.com/keys adresinden ücretsiz alabilirsiniz.",
    )
    elevenlabs_api_key = st.text_input(
        "ElevenLabs API Key (Profesyonel İnsansı Ses - Opsiyonel)",
        value=st.secrets.get("ELEVENLABS_API_KEY", ""),
        type="password",
        help="Boş bırakılırsa ücretsiz Edge-TTS sesi kullanılır.",
    )
    elevenlabs_voice_id = st.text_input(
        "ElevenLabs Voice ID (Varsayılan: 21m00Tcm4TlvDq8ikWAM - Rachel)",
        value="21m00Tcm4TlvDq8ikWAM",
    )

st.markdown('<div class="ypp-section"><h3>📝 1. İçerik & Format Ayarları</h3>', unsafe_allow_html=True)
topic = st.text_input("Video Konusu / Başlık", placeholder="Örn: 5 Şaşırtıcı Uzay Gerçeği")
target_language = st.selectbox("Hedef Dil / Bölge", list(LANGUAGES.keys()), index=0)
video_format = st.radio("Video Formatı", ["Dikey Shorts (9:16)", "Yatay Long-Form (16:9)"], horizontal=True)
bg_file = st.file_uploader("Arkaplan Görsel/Video (Opsiyonel)", type=["mp4", "mov", "jpg", "jpeg", "png"])
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="ypp-section"><h3>🎵 2. Müzik & Ses Seviyesi Ayarları</h3>', unsafe_allow_html=True)
music_file = st.file_uploader("Cihazdan Fon Müziği Yükle (MP3/WAV)", type=["mp3", "wav", "m4a"])
col_m1, col_m2 = st.columns(2)
with col_m1:
    voice_volume = st.slider("Seslendirme Seviyesi (%)", min_value=0, max_value=200, value=100, step=10)
with col_m2:
    music_volume = st.slider("Fon Müziği Seviyesi (%)", min_value=0, max_value=100, value=20, step=5)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="ypp-section"><h3>🎨 3. Altyazı, Efekt & Stil</h3>', unsafe_allow_html=True)
subtitle_template = st.selectbox("Altyazı Şablonu", list(SUBTITLE_TEMPLATES.keys()))
subtitle_position_tr = st.radio("Altyazı Konumu", list(SUB_POSITION_MAP.keys()), index=1, horizontal=True)

st.write("**Video Efektleri**")
fx_flip = st.checkbox("Horizontal Flip (Aynalama - Telif Önleyici)", value=True)
fx_emoji = st.checkbox("Dynamic Emojis (Otomatik emoji ekleme)", value=True)
fx_color = st.checkbox("Color Filter (Sinematik Renk Filtresi)", value=True)
color_filter_type = None
if fx_color:
    color_filter_type = st.selectbox("Filtre Tipi", ["Cold", "Warm", "Vintage"], label_visibility="collapsed")
fx_cta = st.checkbox('Dynamic Call to Action ("Abone Ol" Butonu)', value=True)
fx_anticopy = st.checkbox("Reused Content Anti-Copyright Filter (%100 Özgünleştirme)", value=True)
st.markdown("</div>", unsafe_allow_html=True)

run_clicked = st.button("🚀 VİDEOYU ÜRET VE BULUTA YÜKLE", disabled=st.session_state.is_processing)
progress_placeholder = st.empty()
log_placeholder = st.empty()


def render_logs():
    log_placeholder.code("\n".join(st.session_state.logs[-200:]) or "…", language="log")


# ------------------------------------------------------------------------------------
# SCRIPT & TTS ENGINES
# ------------------------------------------------------------------------------------
def generate_script(api_key: str, topic: str, lang_name: str, fmt: str) -> str:
    client = Groq(api_key=api_key)
    is_short = "Dikey" in fmt
    length_hint = "45-60 saniyede seslendirilecek viral kısa Shorts" if is_short else "2-3 dakikalık video"

    prompt = f"""
Sen viral YouTube senaristisisin. Konu: "{topic}"
Dil: {lang_name.split(' ')[0]}. Format: {length_hint}.
Kural: Sadece seslendirilecek metni yaz. Sahne yönergesi, markdown veya başlık EKLEME. İlk cümlen güçlü bir hook olsun.
"""
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
    )
    script_text = (response.choices[0].message.content or "").strip()
    return re.sub(r"[*_#`]", "", script_text)


def synthesize_elevenlabs(text: str, api_key: str, voice_id: str, out_path: str):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    res = requests.post(url, json=data, headers=headers)
    if res.status_code == 200:
        with open(out_path, "wb") as f:
            f.write(res.content)
        return True
    else:
        raise Exception(f"ElevenLabs Error {res.status_code}: {res.text}")


async def _synthesize_edge_async(text: str, voice: str, out_path: str):
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
                        "start": chunk["offset"] / 10_000_000,
                        "duration": chunk["duration"] / 10_000_000,
                    }
                )
    return word_boundaries


# ------------------------------------------------------------------------------------
# PIL TEXT RENDERER
# ------------------------------------------------------------------------------------
def _create_pil_text_clip(text, font_size, color="black", bg_color="#FFD400", stroke_color=None, stroke_width=0):
    from moviepy.editor import ImageClip

    font = None
    for font_name in ["DejaVuSans-Bold.ttf", "FreeSansBold.ttf", "arial.ttf"]:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x, pad_y = 20, 12
    img_w = text_w + pad_x * 2
    img_h = text_h + pad_y * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if bg_color:
        draw.rounded_rectangle([0, 0, img_w, img_h], radius=10, fill=bg_color)

    x, y = pad_x - bbox[0], pad_y - bbox[1]

    if stroke_color and stroke_width > 0:
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)

    draw.text((x, y), text, font=font, fill=color)

    img_np = np.array(img)
    rgb = img_np[:, :, :3]
    alpha = img_np[:, :, 3] / 255.0

    clip = ImageClip(rgb).set_mask(ImageClip(alpha, ismask=True))
    return clip


def _make_fallback_background(duration: float, size):
    from moviepy.editor import VideoClip
    w, h = size
    base = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / max(h - 1, 1)
        base[y, :, 0] = int(20 + 40 * t)
        base[y, :, 1] = int(10 + 20 * t)
        base[y, :, 2] = int(60 + 80 * (1 - t))

    def make_frame(t):
        return base.copy()

    clip = VideoClip(make_frame, duration=duration)
    return clip.resize(size)


def _apply_color_filter(clip, filter_type: str):
    def cold(image):
        img = image.astype(np.float32)
        img[:, :, 2] = np.clip(img[:, :, 2] * 1.15, 0, 255)
        img[:, :, 0] = np.clip(img[:, :, 0] * 0.95, 0, 255)
        return img.astype("uint8")

    def warm(image):
        img = image.astype(np.float32)
        img[:, :, 0] = np.clip(img[:, :, 0] * 1.15, 0, 255)
        img[:, :, 2] = np.clip(img[:, :, 2] * 0.9, 0, 255)
        return img.astype("uint8")

    def vintage(image):
        img = image.astype(np.float32)
        sepia = np.array([[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]])
        img = np.clip(img @ sepia.T * 0.85, 0, 255)
        return img.astype("uint8")

    fx = {"Cold": cold, "Warm": warm, "Vintage": vintage}.get(filter_type)
    return clip.fl_image(fx) if fx else clip


# ------------------------------------------------------------------------------------
# POP-UP SUBTITLE GENERATOR (Shorts Trend)
# ------------------------------------------------------------------------------------
def _build_popup_subtitle_clips(word_boundaries, template: dict, position: str, size, use_emoji: bool):
    w, h = size
    font_size = max(int(h * template["font_size_ratio"]), 32)
    clips = []
    pos_y = {"top": h * 0.18, "center": h * 0.48, "bottom": h * 0.72}[position]

    # HER EKRANDA MAX 1 VEYA 2 KELİME (Büyük ve Pop-Up Etkisi)
    chunk_size = 2
    for i in range(0, len(word_boundaries), chunk_size):
        group = word_boundaries[i:i + chunk_size]
        if not group:
            continue

        phrase = " ".join(g["text"] for g in group).strip().upper()
        if use_emoji:
            for key, emoji in EMOJI_MAP.items():
                if key in phrase.lower():
                    phrase = f"{phrase} {emoji}"
                    break

        start = group[0]["start"]
        end = group[-1]["start"] + group[-1]["duration"]
        dur = max(end - start, 0.35)

        txt_clip = _create_pil_text_clip(
            text=phrase,
            font_size=font_size,
            color=template["color"],
            bg_color=template["bg_color"],
            stroke_color=template["stroke_color"],
            stroke_width=template["stroke_width"],
        )

        txt_clip = txt_clip.set_start(start).set_duration(dur).set_position(("center", pos_y))
        clips.append(txt_clip)

    return clips


def _build_cta_clip(cta_text: str, size, total_duration: float, position="bottom"):
    w, h = size
    y = h * 0.88 if position == "bottom" else h * 0.06
    font_size = max(int(h * 0.035), 22)

    cta = _create_pil_text_clip(
        text=cta_text,
        font_size=font_size,
        color="white",
        bg_color="red",
        stroke_color=None,
        stroke_width=0,
    )

    interval = 10.0
    fragments = []
    t = 2.0
    while t < total_duration:
        frag = cta.copy().set_start(t).set_duration(min(2.5, max(total_duration - t, 0))).set_position(("center", y))
        fragments.append(frag)
        t += interval
    return fragments


# ------------------------------------------------------------------------------------
# VIDEO COMPOSE & MIXING
# ------------------------------------------------------------------------------------
def compose_video(
    script_text, voice_audio_path, music_audio_path, voice_vol, music_vol,
    word_boundaries, bg_upload_path, video_format,
    fx_flip, fx_color, color_filter_type, subtitle_template_name,
    subtitle_position, fx_emoji, fx_cta, cta_text, fx_anticopy, out_path,
):
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip, vfx

    voice_clip = AudioFileClip(voice_audio_path).volumex(voice_vol / 100.0)
    duration = voice_clip.duration
    size = (1080, 1920) if "Dikey" in video_format else (1920, 1080)

    # Otomatik Kelime Zamanlama Bölücü (Pop-Up Formatı İçin)
    if not word_boundaries and script_text:
        words = script_text.split()
        if words:
            dur_per_word = duration / len(words)
            word_boundaries = [
                {"text": w, "start": i * dur_per_word, "duration": dur_per_word}
                for i, w in enumerate(words)
            ]

    # Fon Müziği Karıştırma (Audio Mixing)
    audio_tracks = [voice_clip]
    if music_audio_path and os.path.exists(music_audio_path):
        music_clip = AudioFileClip(music_audio_path).volumex(music_vol / 100.0)
        if music_clip.duration < duration:
            music_clip = music_clip.fx(vfx.loop, duration=duration)
        else:
            music_clip = music_clip.subclip(0, duration)
        audio_tracks.append(music_clip)

    final_audio = CompositeAudioClip(audio_tracks)

    # Arkaplan Yönetimi
    if bg_upload_path:
        ext = os.path.splitext(bg_upload_path)[1].lower()
        if ext in (".mp4", ".mov"):
            bg = VideoFileClip(bg_upload_path)
            if bg.duration < duration:
                bg = bg.fx(vfx.loop, n=int(duration // bg.duration) + 1)
            bg = bg.subclip(0, duration)
        else:
            bg = ImageClip(bg_upload_path).set_duration(duration)
        bg = bg.resize(height=size[1]) if bg.h / bg.w < size[1] / size[0] else bg.resize(width=size[0])
        bg = bg.crop(x_center=bg.w / 2, y_center=bg.h / 2, width=size[0], height=size[1])
    else:
        bg = _make_fallback_background(duration, size)

    if fx_anticopy:
        bg = bg.fx(vfx.resize, lambda t: 1.0 + 0.03 * (t / max(duration, 1)))
        bg = bg.set_position(("center", "center"))

    if fx_flip:
        bg = bg.fx(vfx.mirror_x)

    if fx_color and color_filter_type:
        bg = _apply_color_filter(bg, color_filter_type)

    bg = bg.set_duration(duration)
    layers = [bg]

    template = SUBTITLE_TEMPLATES[subtitle_template_name]
    if word_boundaries:
        layers.extend(_build_popup_subtitle_clips(word_boundaries, template, subtitle_position, size, fx_emoji))

    if fx_cta:
        layers.extend(_build_cta_clip(cta_text, size, duration))

    final = CompositeVideoClip(layers, size=size).set_duration(duration).set_audio(final_audio)

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
    voice_clip.close()


# ------------------------------------------------------------------------------------
# PIPELINE EXECUTION
# ------------------------------------------------------------------------------------
def run_pipeline():
    st.session_state.logs = []
    st.session_state.final_video_path = None
    progress = progress_placeholder.progress(0, text="Başlatılıyor…")

    try:
        if not groq_api_key:
            log("❌ HATA: Groq API anahtarı girilmedi.")
            render_logs()
            return
        if not topic.strip():
            log("❌ HATA: Video konusu boş olamaz.")
            render_logs()
            return

        lang_info = LANGUAGES[target_language]

        with tempfile.TemporaryDirectory() as tmpdir:
            log(f"▶ Adım 1/4: Senaryo üretiliyor (Groq - Llama 3.3)")
            render_logs()
            progress.progress(10, text="Senaryo yazılıyor…")
            script_text = generate_script(groq_api_key, topic, target_language, video_format)
            log(f"✅ Senaryo hazır ({len(script_text.split())} kelime).")
            render_logs()
            progress.progress(25)

            voice_path = os.path.join(tmpdir, "voice.mp3")
            word_boundaries = []

            if elevenlabs_api_key.strip():
                log("▶ Adım 2/4: İnsansı Ses Üretiliyor (ElevenLabs)")
                render_logs()
                progress.progress(40)
                try:
                    synthesize_elevenlabs(script_text, elevenlabs_api_key.strip(), elevenlabs_voice_id.strip(), voice_path)
                    log("✅ ElevenLabs profesyonel seslendirmesi başarıyla oluşturuldu.")
                except Exception as e:
                    log(f"⚠️ ElevenLabs hatası: {e}. Edge-TTS'e geçiliyor...")
                    word_boundaries = asyncio.run(_synthesize_edge_async(script_text, lang_info["voice"], voice_path))
            else:
                log(f"▶ Adım 2/4: Seslendirme üretiliyor ({lang_info['voice']})")
                render_logs()
                progress.progress(40)
                word_boundaries = asyncio.run(_synthesize_edge_async(script_text, lang_info["voice"], voice_path))
                log(f"✅ Ses hazır.")

            render_logs()
            progress.progress(55)

            # Arkaplan & Müzik dosyalarını temp klasöre kaydetme
            bg_path = None
            if bg_file is not None:
                bg_path = os.path.join(tmpdir, f"bg{os.path.splitext(bg_file.name)[1]}")
                with open(bg_path, "wb") as f:
                    f.write(bg_file.getbuffer())

            music_path = None
            if music_file is not None:
                music_path = os.path.join(tmpdir, f"music{os.path.splitext(music_file.name)[1]}")
                with open(music_path, "wb") as f:
                    f.write(music_file.getbuffer())

            log("▶ Adım 3/4: Video render ediliyor (Pop-Up Altyazılar & Ses Karıştırma)")
            render_logs()
            progress.progress(70)

            out_filename = f"ypp_{uuid.uuid4().hex[:10]}.mp4"
            out_path = os.path.join(OUTPUT_DIR, out_filename)

            compose_video(
                script_text=script_text,
                voice_audio_path=voice_path,
                music_audio_path=music_path,
                voice_vol=voice_volume,
                music_vol=music_volume,
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
            log("✅ Render tamamlandı.")
            render_logs()
            progress.progress(90)

            st.session_state.final_video_path = out_path
            progress.progress(100, text="Tamamlandı 🎉")

    except Exception as e:
        log(f"❌ HATA: {e}")
        log(traceback.format_exc(limit=3))
        render_logs()


if run_clicked:
    st.session_state.is_processing = True
    run_pipeline()
    st.session_state.is_processing = False

render_logs()

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
