import os
import json
import feedparser
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Konfigurasi Sumber Berita dan Blog
RSS_URL = "https://www.antaranews.com/rss/olahraga.xml"
RSS_URL = "http://feeds.bbci.co.uk/sport/rss.xml"
BLOG_ID = "3159636106094545632"
BLOG_ID = "657637354060844621" # ID Blog Anda

def list_model_names():
    """Fungsi pembantu untuk mengecek model yang aktif jika terjadi error"""
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model aktif ditemukan: {m.name}")
    except Exception as e:
        pass

def ambil_gambar_dari_feed(entry):
    """Fungsi pembantu untuk mendeteksi url gambar dari RSS Feed Antara"""
    if 'enclosures' in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('url')
    if 'links' in entry:
        for link in entry.links:
            if link.get('type', '').startswith('image/'):
                return link.get('href')
    return None

def main():
    print("Memulai proses Auto-Blogging Olahraga Teroptimasi SEO...")

    # 1. Autentikasi Gemini AI
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
    
    # Deteksi gambar asli berita
    url_gambar = ambil_gambar_dari_feed(berita_terbaru)
    
    print(f"Ditemukan berita asli: {judul_asli}")
    
    # Kustomisasi Tag Gambar HTML ramah SEO dengan alt-text dan lazy loading
    tag_gambar_html = f"<p align='center'><img src='{url_gambar}' alt='Analisis Berita {judul_asli}' title='{judul_asli}' loading='lazy' style='max-width:100%; height:auto; border-radius:8px;'/></p><br/>" if url_gambar else ""

    # 4. Tulis Ulang & Kategori Otomatis Menggunakan Gemini AI dengan standar SEO Ketat
    prompt = f"""
    Kamu adalah pakar SEO dan jurnalis olahraga profesional senior. Tulis ulang berita olahraga di bawah ini menjadi sebuah artikel blog yang sangat menarik, mendalam, ramah SEO, dan berpotensi peringkat 1 di Google.
    
    Aturan SEO yang wajib kamu ikuti:
    1. Buat judul baru yang memicu rasa penasaran (Clickbait yang aman) dan mengandung kata kunci utama dari berita.
    2. Struktur artikel harus lengkap menggunakan sub-heading menarik dengan tag <h2> dan <h3> secara terstruktur.
    3. Gunakan tag <p> untuk paragraf. Tebalkan kata kunci penting menggunakan tag <strong> secara natural.
    4. Artikel harus mengalir, menggunakan bahasa Indonesia yang santai, seru, mudah dipahami, dan tidak terlihat kaku seperti bot.

    WAJIB BERIKAN JAWABAN DENGAN FORMAT STRUKTUR BERIKUT:
    LABEL: (Isi hanya dengan 1 nama cabang olahraga utama dari berita ini, misal: Sepakbola, Bulutangkis, MotoGP, Basket, dll)
    JUDUL: (Isi dengan judul baru hasil optimasi SEO Anda tanpa tanda bintang atau tag h1)
    KONTEN: (Sisipkan teks gambar ini di baris pertama tanpa modifikasi: {tag_gambar_html} Setelah itu lanjutkan dengan artikel HTML penuh buatanmu yang kaya akan tag <h2>, <h3>, <strong>, dan <p>. Di baris paling akhir, tutup dengan kode: <p><em>Sumber rujukan resmi: <a href='{link_asli}' rel='nofollow'>Antara News</a></em></p>)
    
    Berita Asli yang Harus Diolah:
    Judul: {judul_asli}
    Ringkasan: {ringkasan_asli}
    """
    
    print("Mengirim instruksi optimasi SEO ke Gemini...")
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
        
        # Pembersihan tag ilegal agar tidak merusak layout Blogger
        label_baru = label_baru.replace('[', '').replace(']', '').replace('*', '')
        judul_baru = judul_baru.replace('[', '').replace(']', '').replace('**', '').replace('<h1>', '').replace('</h1>', '')
        
    except Exception as e:
        print("Format AI meleset, mengaktifkan mode pemulihan format.")
        label_baru = "Olahraga"
        judul_baru = judul_asli
        isi_konten = tag_gambar_html + hasil_ai 
    
    # 6. Susun Data untuk Diposting ke Blogger
    body = {
        "kind": "blogger#post",
        "title": judul_baru,
        "content": isi_konten,
        "labels": [label_baru]
    }
    
    # 7. Eksekusi Pengiriman ke Blogger
    print("Mengunggah artikel teroptimasi ke Blogger...")
    posts = blogger_service.posts()
    res = posts.insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
    
    print(f"SUKSES BESAR! Artikel SEO berhasil terbit dengan kategori '{label_baru}'. URL: {res.get('url')}")

if __name__ == '__main__':
    main()
