import os
import time
import feedparser
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.api_core.exceptions import ResourceExhausted
import sys

# ==========================================
# 1. KONFIGURASI KREDENSIAL & API
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

BLOG_ID = os.environ.get("657637354060844621")
SCOPES = ['https://www.googleapis.com/auth/blogger']
TOKEN_FILE = 'token.json'

try:
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        blogger_service = build('blogger', 'v3', credentials=creds)
        print("✅ Otentikasi Blogger berhasil menggunakan token.json")
    else:
        raise FileNotFoundError(f"File {TOKEN_FILE} tidak ditemukan di sistem!")
except Exception as e:
    print(f"FATAL ERROR: Otentikasi Blogger Gagal: {e}")
    sys.exit(1)

# ==========================================
# 2. DAFTAR SUMBER RSS
# ==========================================
RSS_FEEDS = [
    "http://feeds.bbci.co.uk/sport/rss.xml",
    "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://api.foxsports.com/v1/rss?partnerKey=zBaFxRyGKCfxBagJG9b8pqLyndmvo7UU",
    "https://sports.yahoo.com/rss/"
]

# ==========================================
# 3. FUNGSI UTAMA
# ==========================================
def dapatkan_berita_dari_rss(rss_urls, limit_per_sumber=2):
    semua_berita = []
    for url in rss_urls:
        print(f"Membaca RSS dari: {url}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit_per_sumber]:
                berita = {
                    'judul': entry.title,
                    'link': entry.link,
                    'deskripsi': entry.get('summary', entry.get('description', ''))
                }
                semua_berita.append(berita)
        except Exception as e:
            print(f"Gagal membaca RSS {url}: {e}")
    return semua_berita

def tulis_artikel_dengan_gemini(berita):
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
    5. Berikan kredit sumber berita di akhir artikel dengan format HTML link (Sumber: <a href="{berita['link']}">{berita['link']}</a>).
    """
    
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            return response.text
        except ResourceExhausted:
            wait_time = (attempt + 1) * 30
            print(f"⚠️ Limit API Gemini tercapai. Menunggu {wait_time} detik...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"Error saat memanggil Gemini: {e}")
            return None
            
    print("Gagal membuat artikel setelah beberapa kali percobaan akibat limit API.")
    return None

def posting_ke_blogger(judul, konten_html):
    if not BLOG_ID:
        print("❌ BLOG_ID tidak ditemukan di GitHub Secrets!")
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
# 4. EKSEKUSI PROGRAM
# ==========================================
def main():
    print("=== Memulai Auto-Blogger Olahraga ===")
    
    daftar_berita = dapatkan_berita_dari_rss(RSS_FEEDS, limit_per_sumber=2)
    print(f"Ditemukan {len(daftar_berita)} berita untuk diproses.")
    
    for index, berita in enumerate(daftar_berita):
        print(f"\n[{index + 1}/{len(daftar_berita)}] Memproses berita: {berita['judul']}")
        
        hasil_gemini = tulis_artikel_dengan_gemini(berita)
        
        if hasil_gemini:
            baris_teks = hasil_gemini.split('\n')
            judul_baru = baris_teks[0].replace('<h1>', '').replace('</h1>', '').replace('##', '').replace('**', '').strip()
            konten_artikel = '\n'.join(baris_teks[1:]).replace('```html', '').replace('```', '')
            
            posting_ke_blogger(judul_baru, konten_artikel)
            
            print("⏳ Menunggu 20 detik sebelum memproses berita selanjutnya (Anti-Limit)...")
            time.sleep(20)
        else:
            print(f"Melewati artikel: {berita['judul']}")

    print("\n=== Proses Auto-Blogger Selesai ===")

if __name__ == '__main__':
    main()
