<p align="center">
  <img src="logo.png" width="128" height="128" alt="JabriX Logo" />
</p>

<h1 align="center">JabriX</h1>

<p align="center">
  <strong>Ultra-Lightweight, Modern & Lightning-Fast XMPP / Jabber Desktop Client for Windows</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python%203.14-blue.svg" alt="Python 3.14" />
  <img src="https://img.shields.io/badge/Core-Slixmpp%20%2B%20Rust-orange.svg" alt="Rust Extension" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6.svg" alt="Windows" />
  <img src="https://img.shields.io/badge/Launcher%20Size-~97%20KB-success.svg" alt="Size" />
  <img src="https://img.shields.io/badge/Antivirus-Clean-brightgreen.svg" alt="Defender Clean" />
</p>

---

## ✨ Fitur Utama

- ⚡ **Ekstensi Rust Terintegrasi (`slixmpp.jid`):** Menggunakan stringprep berbasis Rust yang dikompilasi secara native untuk pemrosesan JID ultra-cepat tanpa *warning*.
- 🚀 **Launcher C Asli Super Ringan (`JabriX.exe` ~97 KB):**
  - Bukan bundel PyInstaller yang berat (50–100 MB).
  - Berjalan langsung di subsistem Win32 GUI tanpa jeda dekompresi `%TEMP%` dan tanpa kilatan jendela konsol/CMD.
  - 100% bebas dari alarm palsu (*false positive*) Windows Defender.
- 🎨 **Desain Flat 2D Minimalis:** Logo dan antarmuka modern yang bersih dan responsif.
- 🔑 **Ingat Password & Auto-Login:** Dilengkapi opsi penyimpanan kredensial ke database lokal SQLite (`~/.xmpp_chat.db`) dan fitur *toggle* tampilkan password (👁).
- 🔍 **Pencarian Kontak Real-Time (Live Search):** Filter daftar teman secara instan saat mengetik.
- 💬 **Indikator Status Kontak:** Menampilkan status langsung (Online, Away, DND, Offline) pada header percakapan.
- 🧹 **Bersihkan Riwayat Chat:** Opsi untuk menghapus percakapan dengan kontak tertentu tanpa menghapus teman dari roster.
- 📋 **Menu Konteks Klik Kanan:** Fitur *Salin* (Copy) dan *Pilih Semua* (Select All) di jendela riwayat chat.
- 📊 **Status Bar Terpadu:** Menampilkan akun aktif dan rasio teman yang sedang online.

---

## 📁 Struktur Direktori

```text
├── JabriX.exe         # Executable launcher native C (~97 KB)
├── xmpp_chat.py       # Aplikasi utama GUI (Tkinter + Slixmpp)
├── icon.ico           # Ikon Windows multi-resolusi
├── logo.png           # Logo flat 2D resolusi tinggi
├── logo_small.png     # Thumbnail logo untuk layar login
├── launcher.c         # Kode sumber C launcher native
├── resource.rc        # Resource file Windows (Metadata & Icon)
├── build.bat          # Skrip kompilasi launcher (Clang/LLVM)
├── requirements.txt   # Dependensi Python
└── README.md          # Dokumentasi proyek
```

---

## 🚀 Cara Menjalankan

### Opsi 1: Klik Ganda `JabriX.exe` (Direkomendasikan)
Cukup klik ganda [`JabriX.exe`](JabriX.exe) untuk membuka aplikasi secara instan.

### Opsi 2: Menggunakan Terminal Python
```bash
# 1. Pasang dependensi
pip install -r requirements.txt

# 2. Jalankan aplikasi
python xmpp_chat.py
```

---

## 🛠️ Kompilasi Ulang Launcher (Opsional)
Jika Anda ingin mengompilasi ulang file `.exe` dari kode sumber C:
```bash
./build.bat
```
*(Membutuhkan `clang` dan `windres` dari LLVM-MinGW atau MinGW-w64)*.

---

## 📄 Lisensi
Didistribusikan di bawah lisensi MIT.
