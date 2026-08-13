import os
import time
import feedparser
import urllib.parse
import requests  # <-- Tambahan library untuk Ping Sitemap
from urllib.parse import urlparse
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

GROQ_MODEL = "llama-3.3-70b-versatile" 

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

# --- Inisialisasi Indexing API ---
INDEXING_SCOPES = ['https://www.googleapis.com/auth/indexing']
INDEXING_KEY_FILE = 'service_account.json'
indexing_service = None
try:
    if os.path.exists(INDEXING_KEY_FILE):
        idx_creds = service_account.Credentials.from_service_account_file(INDEXING_KEY_FILE, scopes=INDEXING_SCOPES)
        indexing_service = build('indexing', 'v3', credentials=idx_creds)
        print("✅ Google Indexing API siap digunakan.")
    else:
        print("⚠️ File service_account.json tidak ditemukan. Melewati Indexing API.")
except Exception as e:
    print(f"⚠️ Gagal menginisialisasi Indexing API: {e}")

# ==========================================
# 2. DAFTAR SUMBER RSS (3 KATEGORI SPESIFIK)
# ==========================================
RSS_FEEDS = {
    "Sepak Bola": [
        "https://news.google.com/rss/search?q=Sepak+Bola+OR+Liga+Inggris+OR+Liga+Champions+when:1d&hl=id&gl=ID&ceid=ID:id",
        "https://feeds.bbci.co.uk/sport/football/rss.xml"
    ],
    "Bulu Tangkis": [
        "https://news.google.com/rss/search?q=Bulu+Tangkis+OR+BWF+OR+Badminton+Indonesia+when:1d&hl=id&gl=ID&ceid=ID:id",
        "https://www.antaranews.com/rss/olahraga/bulu-tangkis.xml"
    ],
    "Tinju": [
        "https://news.google.com/rss/search?q=Tinju+Dunia+OR+Boxing+when:1d&hl=id&gl=ID&ceid=ID:id",
        "https://www.boxingnews24.com/feed/"
    ]
}

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

def dapatkan_berita_dari_rss(kategori_rss, limit_per_sumber=2):
    semua_berita = []
    for kategori, daftar_url in kategori_rss.items():
        for url in daftar_url:
            print(f"Membaca RSS [{kategori}] dari: {url}")
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
                            # Modifikasi prompt gambar agar sesuai kategorinya
                            prompt_gambar = f"High quality cinematic {kategori} sports photography, dramatic lighting, illustration of: {entry.title}"
                            prompt_aman = urllib.parse.quote(prompt_gambar)
                            gambar_url = f"https://image.pollinations.ai/prompt/{prompt_aman}?width=800&height=400&nologo=true"
                    except Exception:
                        pass

                    berita = {
                        'judul': entry.title,
                        'link': link_asli,
                        'deskripsi': entry.get('summary', entry.get('description', '')),
                        'gambar': gambar_url,
                        'kategori': kategori # <-- Menyimpan label kategori olahraga
                    }
                    semua_berita.append(berita)
            except Exception as e:
                print(f"Gagal membaca RSS {url}: {e}")
    return semua_berita

def tulis_artikel_dengan_groq(berita):
    prompt = f"""
    Bertindaklah sebagai jurnalis olahraga senior dan analis/pandit profesional. 
    Tugas Anda tidak hanya menulis ulang berita, tetapi juga memberikan OPINI tajam dan ANALISIS berbasis DATA terkait cabang olahraga {berita['kategori']} dengan mengambil dari basis pengetahuan luas yang Anda miliki.
    
    Data Berita Asli (Terjemahkan ke Indonesia jika dari bahasa asing):
    Judul: {berita['judul']}
    Deskripsi: {berita['deskripsi']}
    
    Syarat penulisan:
    1. Buat Judul baru yang sangat clickbait, heboh, namun tetap relevan dan tidak hoaks.
    2. Struktur Artikel (Minimal 5 Paragraf panjang):
       - Pembukaan: Sampaikan inti berita dengan gaya bahasa asyik ala komentator {berita['kategori']}.
       - Fakta Utama: Elaborasi lebih lanjut dari deskripsi berita asli.
       - Analisis Berbasis Data: [PENTING] Masukkan wawasan Anda sendiri terkait data historis, perbandingan statistik, rekor masa lalu, atau analisis taktis yang relevan dengan berita tersebut.
       - Opini Pandit & Prediksi: Berikan argumen, pandangan pro/kontra, serta prediksi Anda tentang dampak peristiwa ini ke depannya.
    3. Format artikel HARUS menggunakan tag HTML yang rapi (gunakan <h2> untuk sub-judul analisis/opini, <p> untuk paragraf, <strong> untuk penekanan data penting).
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

def posting_ke_blogger(judul, konten_html, kategori_olahraga):
    if not BLOG_ID:
        print("❌ BLOG_ID tidak ditemukan!")
        return False

    # Label akan otomatis menyesuaikan dengan Kategori Berita
    post_body = {
        'title': judul,
        'content': konten_html,
        'labels': [kategori_olahraga, 'Berita Olahraga', 'Opini Pandit']
    }
    
    try:
        request = blogger_service.posts().insert(blogId=BLOG_ID, body=post_body)
        response = request.execute()
        post_url = response.get('url')
        print(f"✅ Sukses memposting dengan Label '{kategori_olahraga}': {post_url}")
        
        # ==========================================
        # FITUR SEO & INDEXING TINGKAT LANJUT
        # ==========================================
        if post_url:
            # 1. Pastikan URL Canonical (Bersih tanpa ?m=1)
            parsed_url = urlparse(post_url)
            clean_url = f"https://{parsed_url.netloc}{parsed_url.path}"
            
            # 2. Submit ke Google Indexing API
            if indexing_service:
                try:
                    notification = {'url': clean_url, 'type': 'URL_UPDATED'}
                    indexing_service.urlNotifications().publish(body=notification).execute()
                    print(f"🚀 [AUTO-INDEX] API berhasil submit URL Canonical ke Google.")
                except Exception as idx_err:
                    print(f"⚠️ [AUTO-INDEX] Gagal submit API: {idx_err}")
            
            # 3. Ping Google Sitemap
            try:
                sitemap_url = f"https://{parsed_url.netloc}/sitemap.xml"
                ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
                res = requests.get(ping_url)
                if res.status_code == 200:
                    print(f"🎯 [SEO PING] Sukses memaksa Googlebot membaca ulang Sitemap!")
            except Exception as e:
                pass
                
        return True
    except Exception as e:
        print(f"❌ Gagal memposting ke Blogger: {e}")
        return False

# ==========================================
# 4. EKSEKUSI PROGRAM
# ==========================================
def main():
    print("=== Memulai Auto-Blogger Olahraga (Fokus: Sepak Bola, Bulu Tangkis, Tinju) ===")
    print("✨ Fitur Analisis Pandit & Opini Berbasis Data AKTIF ✨")
    
    riwayat_lokal = muat_riwayat_lokal()
    print(f"📂 Ditemukan {len(riwayat_lokal)} riwayat di history.txt")
    
    link_sesi_ini = set() 
    
    # Mengambil berita menggunakan format Dictionary Kategori
    daftar_berita = dapatkan_berita_dari_rss(RSS_FEEDS, limit_per_sumber=2)
    print(f"Ditemukan total {len(daftar_berita)} berita dari RSS.")
    
    for index, berita in enumerate(daftar_berita):
        print(f"\n[{index + 1}/{len(daftar_berita)}] Mengecek berita [{berita['kategori']}]: {berita['judul']}")
        
        if not berita['link'] or len(berita['link']) < 5:
            continue

        if (berita['link'] in riwayat_lokal) or (berita['link'] in link_sesi_ini):
            print("⏩ Melewati berita: Sudah diposting sebelumnya (Duplikat).")
            continue
            
        link_sesi_ini.add(berita['link'])
        hasil_ai = tulis_artikel_dengan_groq(berita)
        
        if hasil_ai:
            baris_teks = hasil_ai.split('\n')
            judul_baru = baris_teks[0].replace('<h1>', '').replace('</h1>', '').replace('##', '').replace('**', '').strip()
            konten_artikel = '\n'.join(baris_teks[1:]).replace('```html', '').replace('```', '')
            
            # PERBAIKAN BUG: Tag Pelacak sudah dikembalikan agar tidak terjadi duplikat!
            tag_pelacak = f"<!-- PELACAK_SUMBER: {berita['link']} -->\n"
            konten_artikel = tag_pelacak + konten_artikel
            
            if berita['gambar']:
                tag_gambar = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{berita["gambar"]}" alt="{judul_baru}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" /></div>\n'
                konten_artikel = tag_gambar + konten_artikel

            kode_iklan = """
            <div style="margin-top: 30px; margin-bottom: 20px; text-align: center;">
                <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5762789427984759" crossorigin="anonymous"></script>
            </div>
            """
            konten_artikel = konten_artikel + kode_iklan

            # Menyisipkan Label Kategori ke fungsi posting
            if posting_ke_blogger(judul_baru, konten_artikel, berita['kategori']):
                simpan_riwayat_lokal(berita['link'])
                riwayat_lokal.add(berita['link'])
            
            print("⏳ Menunggu 20 detik sebelum memproses berita selanjutnya...")
            time.sleep(20)
        else:
            print(f"Gagal di-generate, melewati artikel: {berita['judul']}")

    print("\n=== Proses Auto-Blogger Selesai ===")

if __name__ == '__main__':
    main()
