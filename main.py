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
model = genai.GenerativeModel('gemini-1.5-flash')

BLOG_ID = os.environ.get("BLOG_ID")
SCOPES = ['https://www.googleapis.com/auth/blogger']
TOKEN_FILE = 'token.json'

try:
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        blogger_service = build('blogger', 'v3', credentials=creds)
        print("✅ Otentikasi Blogger berhasil.")
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
def ambil_riwayat_postingan():
    """Mengambil riwayat artikel di Blogger untuk mengecek duplikat."""
    riwayat_konten = []
    if not BLOG_ID:
        return riwayat_konten
        
    try:
        # Mengambil 20 postingan terakhir dari blog
        request = blogger_service.posts().list(blogId=BLOG_ID, maxResults=20)
        response = request.execute()
        posts = response.get('items', [])
        
        for post in posts:
            riwayat_konten.append(post.get('content', ''))
            
        print(f"🔍 Sistem Anti-Duplikat aktif: Memeriksa {len(posts)} artikel terdahulu.")
    except Exception as e:
        print(f"⚠️ Gagal mengambil riwayat artikel (Anti-duplikat mungkin kurang akurat): {e}")
        
    return riwayat_konten

def dapatkan_berita_dari_rss(rss_urls, limit_per_sumber=3):
    semua_berita = []
    for url in rss_urls:
        print(f"Membaca RSS dari: {url}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit_per_sumber]:
                gambar_url = ""
                try:
                    if 'media_content' in entry and len(entry.media_content) > 0:
                        gambar_url = entry.media_content[0].get('url', '')
                    elif 'links' in entry:
                        for link in entry.links:
                            if link.get('rel') == 'enclosure' and 'image' in link.get('type', ''):
                                gambar_url = link.get('href', '')
                                break
                    elif 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
                        gambar_url = entry.media_thumbnail[0].get('url', '')
                except Exception:
                    pass

                berita = {
                    'judul': entry.title,
                    'link': entry.link,
                    'deskripsi': entry.get('summary', entry.get('description', '')),
                    'gambar': gambar_url
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
        print("❌ BLOG_ID tidak ditemukan!")
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
    
    # Ambil riwayat artikel dari blog untuk anti-duplikat
    riwayat_postingan = ambil_riwayat_postingan()
    link_sesi_ini = set() # Untuk menyimpan link yang baru diproses hari ini
    
    daftar_berita = dapatkan_berita_dari_rss(RSS_FEEDS, limit_per_sumber=3)
    print(f"Ditemukan total {len(daftar_berita)} berita dari RSS.")
    
    for index, berita in enumerate(daftar_berita):
        print(f"\n[{index + 1}/{len(daftar_berita)}] Mengecek berita: {berita['judul']}")
        
        # --- CEK DUPLIKAT ---
        # 1. Cek apakah link berita ini ada di artikel yang sudah diposting sebelumnya
        sudah_diposting = any(berita['link'] in konten for konten in riwayat_postingan)
        
        # 2. Cek apakah berita ini sudah diproses di sesi (hari) yang sama
        if sudah_diposting or (berita['link'] in link_sesi_ini):
            print("⏩ Melewati berita: Sudah pernah diposting (Duplikat).")
            continue
            
        # Masukkan link ke sesi ini agar tidak diulang jika RSS lain memuat berita sama
        link_sesi_ini.add(berita['link'])
        # --------------------

        hasil_gemini = tulis_artikel_dengan_gemini(berita)
        
        if hasil_gemini:
            baris_teks = hasil_gemini.split('\n')
            judul_baru = baris_teks[0].replace('<h1>', '').replace('</h1>', '').replace('##', '').replace('**', '').strip()
            konten_artikel = '\n'.join(baris_teks[1:]).replace('```html', '').replace('```', '')
            
            if berita['gambar']:
                tag_gambar = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{berita["gambar"]}" alt="{judul_baru}" style="max-width: 100%; height: auto; border-radius: 8px;" /></div>\n'
                konten_artikel = tag_gambar + konten_artikel

            posting_ke_blogger(judul_baru, konten_artikel)
            
            print("⏳ Menunggu 20 detik sebelum memproses berita selanjutnya (Anti-Limit)...")
            time.sleep(20)
        else:
            print(f"Gagal di-generate, melewati artikel: {berita['judul']}")

    print("\n=== Proses Auto-Blogger Selesai ===")

if __name__ == '__main__':
    main()
