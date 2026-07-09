import os
import time
import feedparser
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.api_core.exceptions import ResourceExhausted

# ==========================================
# 1. KONFIGURASI KREDENSIAL & API
# ==========================================
# Konfigurasi Gemini API (Diambil dari GitHub Secrets)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

# Konfigurasi Blogger API
BLOG_ID = os.environ.get("BLOG_ID") # Pastikan BLOG_ID ada di GitHub Secrets
SCOPES = ['https://www.googleapis.com/auth/blogger']
SERVICE_ACCOUNT_FILE = 'credentials.json' # Pastikan file ini ada atau di-generate via GitHub Actions

# Otentikasi Blogger API
try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    blogger_service = build('blogger', 'v3', credentials=credentials)
except Exception as e:
    print(f"Gagal melakukan otentikasi Blogger API: {e}")
    blogger_service = None

# ==========================================
# 2. DAFTAR SUMBER RSS (BBC & FOX SPORTS)
# ==========================================
RSS_FEEDS = [
    "http://feeds.bbci.co.uk/sport/rss.xml",
    "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://api.foxsports.com/v1/rss?partnerKey=zBaFxRyGKCfxBagJG9b8pqLyndmvo7UU",
    "https://sports.yahoo.com/rss/"
]

# ==========================================
# 3. FUNGSI-FUNGSI UTAMA
# ==========================================
def dapatkan_berita_dari_rss(rss_urls, limit_per_sumber=2):
    """Mengambil berita terbaru dari daftar URL RSS."""
    semua_berita = []
    for url in rss_urls:
        print(f"Membaca RSS dari: {url}")
        feed = feedparser.parse(url)
        
        # Ambil beberapa berita teratas dari setiap sumber
        for entry in feed.entries[:limit_per_sumber]:
            berita = {
                'judul': entry.title,
                'link': entry.link,
                'deskripsi': entry.get('summary', entry.get('description', ''))
            }
            semua_berita.append(berita)
    return semua_berita

def tulis_artikel_dengan_gemini(berita):
    """Menggunakan Gemini untuk menulis ulang artikel (Menghindari Plagiasi & SEO Friendly)."""
    prompt = f"""
    Bertindaklah sebagai jurnalis olahraga profesional. 
    Tulis ulang berita olahraga berikut ke dalam bahasa Indonesia yang menarik, informatif, dan SEO friendly.
    
    Data Berita Asli:
    Judul: {berita['judul']}
    Deskripsi: {berita['deskripsi']}
    
    Syarat penulisan:
    1. Buat Judul baru yang clickbait tapi tidak menyesatkan.
    2. Tulis isi artikel minimal 3 paragraf.
    3. Format artikel harus menggunakan tag HTML (seperti <h2>, <p>, <strong>) agar siap diposting di Blogger.
    4. Jangan masukkan tag <html>, <head>, atau <body>, cukup isi artikelnya saja.
    5. Berikan kredit sumber berita di akhir artikel (Sumber: {berita['link']}).
    """
    
    # Mekanisme Retry (Penanganan Error 429 Quota Exceeded)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except ResourceExhausted:
            wait_time = (attempt + 1) * 30
            print(f"⚠️ Limit API Gemini tercapai (Error 429). Menunggu {wait_time} detik sebelum mencoba lagi...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"Error saat memanggil Gemini: {e}")
            return None
            
    print("Gagal membuat artikel setelah beberapa kali percobaan akibat limit API.")
    return None

def posting_ke_blogger(judul, konten_html):
    """Mengunggah artikel yang sudah jadi ke Blogspot."""
    if not blogger_service:
        print("Blogger service tidak tersedia. Melewati proses posting.")
        return
        
    post_body = {
        'title': judul,
        'content': konten_html,
        'labels': ['Berita Olahraga', 'Auto Update']
    }
    
    try:
        request = blogger_service.posts().insert(blogId=BLOG_ID, body=post_body)
        response = request.execute()
        print(f"✅ Sukses memposting: {response.get('url')}")
    except Exception as e:
        print(f"❌ Gagal memposting ke Blogger: {e}")

# ==========================================
# 4. EKSEKUSI PROGRAM (MAIN)
# ==========================================
def main():
    print("=== Memulai Auto-Blogger Olahraga ===")
    
    # 1. Ambil berita dari RSS Fox Sports & BBC
    daftar_berita = dapatkan_berita_dari_rss(RSS_FEEDS, limit_per_sumber=2)
    print(f"Ditemukan {len(daftar_berita)} berita untuk diproses.")
    
    # 2. Proses dan Posting satu per satu
    for index, berita in enumerate(daftar_berita):
        print(f"\n[{index + 1}/{len(daftar_berita)}] Memproses berita: {berita['judul']}")
        
        # Ekstrak judul baru dan konten dari output Gemini
        hasil_gemini = tulis_artikel_dengan_gemini(berita)
        
        if hasil_gemini:
            # Mengakali pemisahan Judul dan Konten dari output HTML Gemini
            # Asumsi: Gemini memberikan Judul di baris pertama atau di dalam <h1>/<h2>
            baris_teks = hasil_gemini.split('\n')
            judul_baru = baris_teks[0].replace('<h1>', '').replace('</h1>', '').replace('**', '').strip()
            konten_artikel = '\n'.join(baris_teks[1:])
            
            # Posting ke blog
            posting_ke_blogger(judul_baru, konten_artikel)
            
            # FITUR ANTI-LIMIT: Jeda wajib agar API Gemini gratisan tidak error 429
            print("⏳ Menunggu 20 detik sebelum memproses berita selanjutnya (Mencegah Limit API)...")
            time.sleep(20)
        else:
            print(f"Melewati artikel: {berita['judul']}")

    print("\n=== Proses Auto-Blogger Selesai ===")

if __name__ == '__main__':
    main()
