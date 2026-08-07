import os
import time
import feedparser
import urllib.parse
from groq import Groq 
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import sys

# ==========================================
# 1. KONFIGURASI KREDENSIAL & API
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "llama3-70b-8192" 

BLOG_ID = os.environ.get("BLOG_ID")
SCOPES = ['https://www.googleapis.com/auth/blogger']
TOKEN_FILE = 'token.json'
HISTORY_FILE = 'history.txt'

# --- Inisialisasi Blogger API ---
try:
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        blogger_service = build('blogger', 'v3', credentials=creds)
        print("✅ Otentikasi Blogger berhasil.")
    else:
        raise FileNotFoundError(f"File {TOKEN_FILE} tidak ditemukan di sistem!")
except Exception as e:
    print(f"FATAL ERROR: Otentikasi Blogger Gagal: {e}")
    sys.exit(1)

# ==========================================
# 2. DAFTAR SUMBER RSS (OLAHRAGA UMUM)
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
def muat_riwayat_lokal():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def simpan_riwayat_lokal(link):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{link}\n")

def dapatkan_berita_dari_rss(rss_urls, limit_per_sumber=3):
    semua_berita = []
    for url in rss_urls:
        print(f"Membaca RSS dari: {url}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit_per_sumber]:
                gambar_url = ""
                link_asli = entry.get('link', entry.get('id', ''))
                
                try:
                    if 'media_content' in entry and len(entry.media_content) > 0:
                        gambar_url = entry.media_content[0].get('url', '')
                    elif 'links' in entry:
                        for link in entry.links:
                            if link.get('rel') == 'enclosure' and 'image' in link.get('type', ''):
                                gambar_url = link.get('href', '')
                                break
                                
                    if not gambar_url:
                        print("  > Gambar asli tidak ada. Menyiapkan gambar AI...")
                        prompt_gambar = f"High quality cinematic sports photography, dramatic lighting, illustration of: {entry.title}"
                        prompt_aman = urllib.parse.quote(prompt_gambar)
                        gambar_url = f"https://image.pollinations.ai/prompt/{prompt_aman}?width=800&height=400&nologo=true"
                except Exception:
                    pass

                berita = {
                    'judul': entry.title,
                    'link': link_asli,
                    'deskripsi': entry.get('summary', entry.get('description', '')),
                    'gambar': gambar_url
                }
                semua_berita.append(berita)
        except Exception as e:
            print(f"Gagal membaca RSS {url}: {e}")
    return semua_berita

def tulis_artikel_dengan_groq(berita):
    prompt = f"""
    Bertindaklah sebagai jurnalis olahraga dan pandit profesional yang tajam, bersemangat, dan informatif. 
    Tulis ulang berita olahraga berikut ke dalam bahasa Indonesia yang memancing rasa penasaran, mendalam, dan SEO friendly. 
    
    Data Berita Asli (Bahasa Inggris):
    Judul: {berita['judul']}
    Deskripsi: {berita['deskripsi']}
    
    Syarat penulisan:
    1. Buat Judul baru yang sangat clickbait, heboh, namun tetap relevan dengan isi berita dan tidak hoaks.
    2. Tulis isi artikel minimal 4 paragraf dengan gaya bahasa asyik ala komentator olahraga.
    3. Format artikel harus menggunakan tag HTML (seperti <h2>, <p>, <strong>, <em>).
    4. Jangan masukkan tag <html>, <head>, atau <body>, cukup isi artikelnya saja.
    5. Berikan kredit sumber berita di akhir artikel (Sumber: <a href="{berita['link']}">{berita['link']}</a>).
    """
    
    for attempt in range(3):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=GROQ_MODEL,
                temperature=0.7,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            wait_time = (attempt + 1) * 30
            print(f"⚠️ Error/Limit API Groq: {e}. Menunggu {wait_time} detik...")
            time.sleep(wait_time)
            
    return None

def posting_ke_blogger(judul, konten_html):
    if not BLOG_ID:
        print("❌ BLOG_ID tidak ditemukan!")
        return False

    post_body = {
        'title': judul,
        'content': konten_html,
        'labels': ['Berita Olahraga', 'Highlight Olahraga']
    }
    
    try:
        request = blogger_service.posts().insert(blogId=BLOG_ID, body=post_body)
        response = request.execute()
        post_url = response.get('url')
        print(f"✅ Sukses memposting: {post_url}")
        return True
    except Exception as e:
        print(f"❌ Gagal memposting ke Blogger: {e}")
        return False

# ==========================================
# 4. EKSEKUSI PROGRAM
# ==========================================
def main():
    print("=== Memulai Auto-Blogger Olahraga (Didukung Groq AI) ===")
    
    riwayat_lokal = muat_riwayat_lokal()
    print(f"📂 Ditemukan {len(riwayat_lokal)} riwayat di history.txt")
    
    link_sesi_ini = set() 
    
    daftar_berita = dapatkan_berita_dari_rss(RSS_FEEDS, limit_per_sumber=3)
    print(f"Ditemukan total {len(daftar_berita)} berita dari RSS.")
    
    for index, berita in enumerate(daftar_berita):
        print(f"\n[{index + 1}/{len(daftar_berita)}] Mengecek berita: {berita['judul']}")
        
        if not berita['link'] or len(berita['link']) < 5:
            continue

        # Cek duplikat lewat history lokal
        if (berita['link'] in riwayat_lokal) or (berita['link'] in link_sesi_ini):
            print("⏩ Melewati berita: Sudah diposting sebelumnya (Duplikat).")
            continue
            
        link_sesi_ini.add(berita['link'])
        hasil_ai = tulis_artikel_dengan_groq(berita)
        
        if hasil_ai:
            baris_teks = hasil_ai.split('\n')
            judul_baru = baris_teks[0].replace('<h1>', '').replace('</h1>', '').replace('##', '').replace('**', '').strip()
            konten_artikel = '\n'.join(baris_teks[1:]).replace('```html', '').replace('```', '')
            
            tag_pelacak = f"\n"
            konten_artikel = tag_pelacak + konten_artikel
            
            if berita['gambar']:
                tag_gambar = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{berita["gambar"]}" alt="{judul_baru}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" /></div>\n'
                konten_artikel = tag_gambar + konten_artikel

            # Iklan
            kode_iklan = """
            <div style="margin-top: 30px; margin-bottom: 20px; text-align: center;">
                <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5762789427984759" crossorigin="anonymous"></script>
            </div>
            """
            konten_artikel = konten_artikel + kode_iklan

            # Posting dan catat history
            if posting_ke_blogger(judul_baru, konten_artikel):
                simpan_riwayat_lokal(berita['link'])
                riwayat_lokal.add(berita['link'])
            
            print("⏳ Menunggu 20 detik sebelum memproses berita selanjutnya...")
            time.sleep(20)
        else:
            print(f"Gagal di-generate, melewati artikel: {berita['judul']}")

    print("\n=== Proses Auto-Blogger Selesai ===")

if __name__ == '__main__':
    main()
