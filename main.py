import streamlit as st
import google.generativeai as genai
from PIL import Image
import json

# ==========================================
# 1. AYARLAR & HAFIZA
# ==========================================
st.set_page_config(page_title="AI Sınav Asistanı v3.9", layout="wide")

# --- API ANAHTARI YÖNETİMİ ---
with st.sidebar:
    st.header("🔑 Ayarlar")
    # Kullanıcıdan anahtar al veya st.secrets'tan çek
    api_key_input = st.text_input("Gemini API Anahtarı", type="password")
    
    # Eğer st.secrets tanımlıysa oradan da okuyabilir (Gelişmiş kullanım)
    if not api_key_input and "GOOGLE_API_KEY" in st.secrets:
        api_key_input = st.secrets["GOOGLE_API_KEY"]

    if not api_key_input:
        st.warning("Lütfen API anahtarını girin.")
        st.stop() # Anahtar yoksa uygulamayı durdur

# API Yapılandırması
genai.configure(api_key=api_key_input)

# Hafıza Ayarları
if 'yuklenen_resimler_v3' not in st.session_state:
    st.session_state.yuklenen_resimler_v3 = []

# Yükleyici Anahtarları
if 'cam_key' not in st.session_state: st.session_state.cam_key = 0
if 'file_key' not in st.session_state: st.session_state.file_key = 0

def reset_cam(): st.session_state.cam_key += 1
def reset_file(): st.session_state.file_key += 1

def listeyi_temizle():
    st.session_state.yuklenen_resimler_v3 = []
    st.session_state.cam_key += 1
    st.session_state.file_key += 1
    st.rerun()

# ==========================================
# 2. ARAYÜZ
# ==========================================
st.title("🧠 AI Sınav Okuma (Mod Seçmeli v3.9)")
st.markdown("---")

col_sol, col_sag = st.columns([1, 1], gap="large")

# --- SOL SÜTUN: KRİTERLER ---
with col_sol:
    st.header("1. Kriterler")
    ogretmen_promptu = st.text_area(
        "Öğretmen Notu:", 
        height=100, 
        placeholder="Örn: 4 kelimenin de açıklanması gerekiyor. Eksik varsa puan kır."
    )
    
    with st.expander("Cevap Anahtarı Yükle (İsteğe Bağlı)"):
        rubrik_dosyasi = st.file_uploader("Fotoğraf Seç", type=["jpg", "png", "jpeg"], key="rubrik_up")
        rubrik_img = Image.open(rubrik_dosyasi) if rubrik_dosyasi else None
        if rubrik_img: st.image(rubrik_img, width=200)

# --- SAĞ SÜTUN: ÖĞRENCİ KAĞIDI ---
with col_sag:
    st.subheader("2. Öğrenci Kağıdı")
    
    mod = st.radio(
        "Çalışma Modunu Seçin:", 
        ["📂 Dosya Yükle (PC / Galeri)", "📸 Canlı Kamera (Sadece Mobil)"], 
        horizontal=True
    )
    
    st.markdown("---")
    
    # MOD A: DOSYA
    if "Dosya" in mod:
        st.info("Bilgisayardan dosya seçmek veya mobilde galeri için:")
        uploaded_file = st.file_uploader(
            "Dosya Seç", 
            type=["jpg", "png", "jpeg"], 
            key=f"file_{st.session_state.file_key}"
        )
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.session_state.yuklenen_resimler_v3.append(img)
            reset_file()
            st.rerun()

    # MOD B: KAMERA
    else:
        st.warning("PC'de webcam, mobilde kamerayı açar.")
        cam_img = st.camera_input("Fotoğrafı Çek", key=f"cam_{st.session_state.cam_key}")
        if cam_img:
            img = Image.open(cam_img)
            st.session_state.yuklenen_resimler_v3.append(img)
            reset_cam()
            st.rerun()

    # --- HAVUZ GÖRÜNTÜLEME ---
    if len(st.session_state.yuklenen_resimler_v3) > 0:
        st.success(f"📎 Toplam **{len(st.session_state.yuklenen_resimler_v3)} sayfa** hafızada.")
        
        cols = st.columns(4)
        for i, img in enumerate(st.session_state.yuklenen_resimler_v3):
            with cols[i % 4]:
                st.image(img, use_container_width=True, caption=f"Sayfa {i+1}")
        
        if st.button("🗑️ HEPSİNİ SİL (Yeni Öğrenci)", use_container_width=True, type="secondary"):
            listeyi_temizle()

# ==========================================
# 3. İŞLEM (ANALİZ)
# ==========================================
st.markdown("---")

if st.button("✅ KAĞIDI OKU VE DEĞERLENDİR", type="primary", use_container_width=True):
    if len(st.session_state.yuklenen_resimler_v3) == 0:
        st.warning("Lütfen önce kağıt yükleyin.")
    else:
        with st.spinner("Yapay zeka analiz yapıyor... (Gemini 1.5 Flash)"):
            try:
                # MODEL AYARLARI (JSON Output Garantili)
                generation_config = {
                    "temperature": 0.4,
                    "top_p": 0.95,
                    "top_k": 64,
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json", # <--- SİHİRLİ DOKUNUŞ
                }

                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config=generation_config,
                )
                
                # --- PROMPT ---
                base_prompt = """
                Rol: Deneyimli Türk Öğretmeni.
                Görev: Öğrenci kağıdını analiz et.
                
                Yönerge:
                1. Kağıttaki el yazısını dikkatlice oku.
                2. Kimlik bilgilerini (Ad, Soyad, Sınıf, No) bul.
                3. Her soruyu verilen cevap anahtarına veya öğretmen notuna göre puanla.
                
                ÇIKTI FORMATI (Kesinlikle bu JSON yapısına uy):
                {
                  "kimlik": { "ad_soyad": "Str", "sinif": "Str", "numara": "Str" },
                  "degerlendirme": [
                    {
                      "no": "1",
                      "soru": "Soru özeti",
                      "cevap": "Öğrenci cevabı",
                      "puan": 10,
                      "tam_puan": 10,
                      "yorum": "Neden bu puanı verdin?"
                    }
                  ]
                }
                """
                
                prompt_parts = [base_prompt]
                if ogretmen_promptu: prompt_parts.append(f"ÖĞRETMEN NOTU: {ogretmen_promptu}")
                if rubrik_img:
                    prompt_parts.append("CEVAP ANAHTARI:")
                    prompt_parts.append(rubrik_img)
                
                prompt_parts.append("ÖĞRENCİ KAĞITLARI:")
                for img in st.session_state.yuklenen_resimler_v3:
                    prompt_parts.append(img)
                
                # API Çağrısı
                response = model.generate_content(prompt_parts)
                
                # JSON Yükleme (Artık regex/split gerekmez)
                data = json.loads(response.text)
                
                kimlik = data.get("kimlik", {})
                sorular = data.get("degerlendirme", [])
                
                st.balloons()
                
                # Puan Hesapla
                try:
                    toplam = sum([float(x.get('puan', 0)) for x in sorular])
                    max_toplam = sum([float(x.get('tam_puan', 0)) for x in sorular])
                except:
                    toplam, max_toplam = 0, 0
                
                # --- SONUÇ KARTI ---
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("👤 Öğrenci", kimlik.get("ad_soyad", "-"))
                    c2.metric("🏫 Sınıf", kimlik.get("sinif", "-"))
                    c3.metric("🔢 No", kimlik.get("numara", "-"))
                    c4.markdown(f"<h1 style='color:#28a745; margin:0;'>{int(toplam)} / {int(max_toplam)}</h1>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # SORULAR LİSTESİ
                for soru in sorular:
                    p = float(soru.get('puan', 0))
                    tp = float(soru.get('tam_puan', 0))
                    
                    # Renk Mantığı
                    if tp > 0 and (p/tp) >= 0.8: renk, ikon = "green", "✅"
                    elif p == 0: renk, ikon = "red", "❌"
                    else: renk, ikon = "orange", "⚠️"
                    
                    with st.container(border=True):
                        c1, c2 = st.columns([9, 1])
                        c1.markdown(f"#### {ikon} Soru {soru.get('no')}: {soru.get('soru')}")
                        c2.markdown(f"### :{renk}[{int(p)}/{int(tp)}]")
                        st.caption(f"**Öğrenci:** {soru.get('cevap', '-')}")
                        if renk == "green": st.success(soru.get('yorum'))
                        elif renk == "orange": st.warning(soru.get('yorum'))
                        else: st.error(soru.get('yorum'))

            except Exception as e:
                st.error("Bir hata oluştu. Lütfen tekrar deneyin.")
                with st.expander("Teknik Hata Detayı"):
                    st.code(str(e))
