import os
import json
import feedparser
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Konfigurasi Sumber Berita dan Blog
RSS_URL = "https://www.antaranews.com/rss/olahraga.xml" 
BLOG_ID = "657637354060844621" # ID Blog Anda

def main():
    print("Memulai proses Auto-Blogging Olahraga...")

    # 1. Autentikasi Gemini AI (Pustaka Klasik & Stabil)
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    
    # 2. Autentikasi Blogger API
    token_info = json.loads(os.environ["BLOGGER_TOKEN"])
    creds = Credentials.from_authorized_user_info(token_info)
    blogger_service = build('blogger', 'v3', credentials=creds)
    
    # 3. Ambil Berita Olahraga Terbaru dari RSS
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Tidak ada berita olahraga ditemukan di RSS saat ini.")
        return
        
    berita_terbaru = feed.entries[0]
    judul_asli = berita_terbaru.title
    link_asli = berita_terbaru.link
    ringkasan_asli = berita_terbaru.summary
    
    print(f"Ditemukan berita asli: {judul_asli}")
    
    # 4. Tulis Ulang & Kategori Otomatis Menggunakan Gemini AI
    prompt = f"""
    Kamu adalah jurnalis dan blogger olahraga profesional yang antusias. Tulis ulang berita olahraga berikut menjadi artikel blog yang seru, informatif, dan menggebu-gebu. Gunakan istilah olahraga yang tepat.

    WAJIB BERIKAN JAWABAN DENGAN FORMAT PERSIS SEPERTI DI BAWAH INI:
    LABEL: (Isi dengan 1 nama cabang olahraga utama dari berita ini, misal: Sepakbola, Bulutangkis, MotoGP, Basket, dll)
    JUDUL: (Isi dengan judul baru yang bombastis dan menarik)
    KONTEN: (Isi dengan artikel lengkap berformat HTML menggunakan tag <p>. Di paragraf paling akhir, sertakan kode ini: <p><em>Sumber: <a href='{link_asli}'>Link Artikel Asli</a></em></p>)
    
    Berita Asli:
    Judul: {judul_asli}
    Ringkasan: {ringkasan_asli}
    """
    
    print("Mengirim instruksi ke Gemini...")
    # Menggunakan model 1.5 Flash yang benar
    model = genai.GenerativeModel('gemini-3.5-flash')
    response = model.generate_content(prompt)
    hasil_ai = response.text.strip()
    
    # 5. Memisahkan Label, Judul Baru, dan Isi Konten
    try:
        label_start = hasil_ai.find("LABEL:") + len("LABEL:")
        judul_start = hasil_ai.find("JUDUL:")
        konten_start = hasil_ai.find("KONTEN:")
        
        label_baru = hasil_ai[label_start:judul_start].strip()
        judul_baru = hasil_ai[judul_start + len("JUDUL:"):konten_start].strip()
        isi_konten = hasil_ai[konten_start + len("KONTEN:"):].strip()
        
        # Membersihkan simbol Markdown
        label_baru = label_baru.replace('[', '').replace(']', '').replace('*', '')
        judul_baru = judul_baru.replace('[', '').replace(']', '').replace('**', '').replace('<h1>', '').replace('</h1>', '')
        
    except Exception as e:
        print("Format AI meleset, menggunakan data aman (fallback).")
        label_baru = "Olahraga"
        judul_baru = judul_asli
        isi_konten = hasil_ai 
    
    # 6. Susun Data untuk Diposting ke Blogger
    body = {
        "kind": "blogger#post",
        "title": judul_baru,
        "content": isi_konten,
        "labels": [label_baru]
    }
    
    # 7. Eksekusi Pengiriman ke Blogger
    print("Mengunggah artikel ke Blogger...")
    posts = blogger_service.posts()
    res = posts.insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
    
    print(f"SUKSES! Artikel diposting dengan Label '{label_baru}'. Link: {res.get('url')}")

if __name__ == '__main__':
    main()
