"""
Streamlit Camera Taraması — HTML5 MediaDevices API ile kamera erişimi
"""
import streamlit as st
import streamlit.components.v1 as components
import base64
from pathlib import Path


def kamera_tarama_component():
    """
    Tarayıcı kamerasından sınav kağıdı fotoğrafı çek.
    Base64 image döner.

    Returns:
        dict: {"status": "captured", "image_base64": "...", "mime": "image/jpeg"}
        veya {"status": "cancelled", "image_base64": None}
    """

    # HTML + JavaScript component
    html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; margin: 0; }
            .camera-container { max-width: 100%; }
            #camera-preview {
                width: 100%;
                max-width: 600px;
                background: #000;
                border-radius: 8px;
                margin-bottom: 10px;
            }
            canvas { display: none; }
            .btn-group {
                display: flex;
                gap: 10px;
                margin-top: 10px;
            }
            button {
                flex: 1;
                padding: 12px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
            }
            .btn-capture {
                background: #1f77b4;
                color: white;
            }
            .btn-capture:hover {
                background: #1f77b4cc;
            }
            .btn-retake {
                background: #ff7f0e;
                color: white;
            }
            .btn-retake:hover {
                background: #ff7f0ecc;
            }
            .btn-cancel {
                background: #d62728;
                color: white;
            }
            .btn-cancel:hover {
                background: #d62728cc;
            }
            .btn-confirm {
                background: #2ca02c;
                color: white;
            }
            .btn-confirm:hover {
                background: #2ca02ccc;
            }
            #captured-image {
                width: 100%;
                max-width: 600px;
                margin-bottom: 10px;
                border-radius: 8px;
            }
            .info-text {
                color: #666;
                font-size: 12px;
                margin-top: 10px;
            }
            .error-text {
                color: #d62728;
                margin: 10px 0;
            }
        </style>
    </head>
    <body>
        <div class="camera-container">
            <div id="camera-section">
                <video id="camera-preview" autoplay playsinline></video>
                <canvas id="canvas"></canvas>
                <div class="btn-group">
                    <button class="btn-capture" onclick="capturePhoto()">📷 Fotoğraf Çek</button>
                    <button class="btn-cancel" onclick="cancelCamera()">✕ İptal</button>
                </div>
                <p class="info-text">💡 Fotoğrafı düz açıyla ve iyi aydınlatmada çek</p>
            </div>

            <div id="preview-section" style="display: none;">
                <img id="captured-image" src="" />
                <div class="btn-group">
                    <button class="btn-retake" onclick="retakePhoto()">🔄 Yeniden Çek</button>
                    <button class="btn-confirm" onclick="confirmPhoto()">✓ Onay</button>
                </div>
            </div>

            <div id="error-section" style="display: none;">
                <p class="error-text" id="error-message"></p>
                <button class="btn-cancel" onclick="closeError()">Kapat</button>
            </div>
        </div>

        <script>
            let stream = null;
            let capturedBase64 = null;

            async function startCamera() {
                try {
                    stream = await navigator.mediaDevices.getUserMedia({
                        video: {
                            facingMode: 'environment',
                            width: { ideal: 1280 },
                            height: { ideal: 960 }
                        }
                    });
                    const video = document.getElementById('camera-preview');
                    video.srcObject = stream;
                } catch (err) {
                    showError('Kamera erişimi başarısız: ' + err.message);
                }
            }

            function capturePhoto() {
                const video = document.getElementById('camera-preview');
                const canvas = document.getElementById('canvas');
                const ctx = canvas.getContext('2d');

                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);

                // JPEG olarak base64 encode et
                capturedBase64 = canvas.toDataURL('image/jpeg', 0.85);

                // Preview göster
                document.getElementById('captured-image').src = capturedBase64;
                document.getElementById('camera-section').style.display = 'none';
                document.getElementById('preview-section').style.display = 'block';
            }

            function retakePhoto() {
                capturedBase64 = null;
                document.getElementById('camera-section').style.display = 'block';
                document.getElementById('preview-section').style.display = 'none';
            }

            function confirmPhoto() {
                // Streamlit'e data gönder
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: {
                        status: 'captured',
                        image_base64: capturedBase64,
                        mime: 'image/jpeg'
                    }
                }, '*');
            }

            function cancelCamera() {
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                }
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: {
                        status: 'cancelled',
                        image_base64: null,
                        mime: null
                    }
                }, '*');
            }

            function showError(message) {
                document.getElementById('error-message').textContent = message;
                document.getElementById('camera-section').style.display = 'none';
                document.getElementById('preview-section').style.display = 'none';
                document.getElementById('error-section').style.display = 'block';
            }

            function closeError() {
                cancelCamera();
            }

            // Başlat
            startCamera();
        </script>
    </body>
    </html>
    """

    result = components.html(html_code, height=600)
    return result


def csv_ogrenci_listesi_yukle():
    """
    CSV dosyasından öğrenci listesi yükle (Yalova UBS format).

    Format:
        A: Öğrenci No (9 hane: 202310001)
        B: Öğrenci Adı (Ad Soyad veya sadece Soyadı)

    Returns:
        list[dict]: [{"no": "202310001", "ad": "Ahmet Yılmaz"}, ...]
    """
    import pandas as pd

    st.subheader("📋 Öğrenci Listesi (CSV/Excel)")
    st.caption("Format: Sütun A = Öğrenci No, Sütun B = Öğrenci Adı")

    uploaded = st.file_uploader(
        "CSV veya Excel dosyasını yükle",
        type=["csv", "xlsx", "xls"],
        key="student_list_upload"
    )

    ogrenci_listesi = []

    if uploaded:
        try:
            if uploaded.name.endswith('.csv'):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)

            # Sütunları algıla (Index 0 ve 1 veya headers)
            if len(df.columns) < 2:
                st.error("❌ Dosyada en az 2 sütun olmalı!")
                return ogrenci_listesi

            col_no = df.columns[0]
            col_ad = df.columns[1]

            for _, row in df.iterrows():
                try:
                    no = str(row[col_no]).strip()
                    ad = str(row[col_ad]).strip()

                    if no and ad and no != "nan":
                        ogrenci_listesi.append({"no": no, "ad": ad})
                except:
                    pass

            st.success(f"✅ {len(ogrenci_listesi)} öğrenci yüklendi")

            # Preview
            with st.expander("📊 Önizleme"):
                preview_df = pd.DataFrame(ogrenci_listesi)
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"❌ Dosya okuma hatası: {e}")

    return ogrenci_listesi
