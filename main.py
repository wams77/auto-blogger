import os
import json
import feedparser
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Konfigurasi
RSS_URL = "https://www.antaranews.com/rss/terkini.xml" 
BLOG_ID = "657637354060844621" # ID Blog Anda

def main():
    print("Memulai proses Auto-Blogging...")

    # 1. Autentikasi Gemini AI
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    
    # 2. Autentikasi Blogger API
    token_info = json.loads(os.environ["BLOGGER_TOKEN"])
    creds = Credentials.from_authorized_user_info(token_info)
    blogger_service = build('blogger', 'v3', credentials=creds)
    
    # 3. Ambil Berita Terbaru dari RSS
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Tidak ada berita ditemukan di RSS.")
        return
        
    berita_terbaru = feed.entries[0]
    judul_asli = berita_terbaru.title
    link_asli = berita_terbaru.link
    ringkasan_asli = berita_terbaru.summary
    
    print(f"Ditemukan berita asli: {judul_asli}")
    
    # 4. Tulis Ulang Menggunakan Gemini AI
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Kamu adalah blogger profesional. Tulis ulang berita berikut menjadi artikel blog yang unik, santai, namun informatif.
    Ubah judulnya menjadi lebih menarik (jangan tulis kata 'Judul:').
    Format isi artikel menggunakan tag HTML dasar (gunakan tag <p> untuk paragraf).
    Di akhir artikel, tambahkan kalimat: "<p><em>Sumber: <a href='{link_asli}'>Link Artikel Asli</a></em></p>"
    
    Berikut data beritanya:
    Judul Asli: {judul_asli}
    Ringkasan: {ringkasan_asli}
    """
    
    print("Mengirim ke Gemini untuk ditulis ulang...")
    response = model.generate_content(prompt)
    hasil_ai = response.text.strip()
    
    # Memisahkan Judul Baru dan Isi Konten
    # Asumsi baris pertama hasil AI adalah judul
    baris_teks = hasil_ai.split('\n')
    judul_baru = baris_teks[0].replace('<h1>', '').replace('</h1>', '').replace('**', '').strip()
    isi_konten = '\n'.join(baris_teks[1:]).strip()
    
    # 5. Posting ke Blogger
    body = {
        "kind": "blogger#post",
        "title": judul_baru,
        "content": isi_konten
    }
    
    print("Mengunggah artikel ke Blogger...")
    posts = blogger_service.posts()
    res = posts.insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
    
    print(f"SUKSES! Artikel berhasil diposting. Link: {res.get('url')}")

if __name__ == '__main__':
    main()
