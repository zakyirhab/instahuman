# InstaHuman

Bot Instagram human-like berbasis ADB + UIAutomator2.  
Mengotomatiskan interaksi di feed, reels, story, DM, dan notifikasi dengan perilaku yang sangat alami.

## Fitur
- **Perilaku manusiawi**: jeda acak, swipe tidak seragam, ketik huruf per huruf.
- **Multi perangkat**: kendalikan puluhan HP secara paralel dari satu PC.
- **Mode Testing & Loop Task**: verifikasi singkat atau otomatisasi berulang.
- **Filter cerdas**: lewati iklan, konten tidak relevan, hanya interaksi di postingan populer.
- **Screenshot otomatis**: rekam setiap komentar sebagai bukti.
- **Navigasi aman**: swipe kiri untuk hindari widget story, drag handle tutup komentar.

## Persyaratan
- Python 3.10+
- ADB (Android Debug Bridge)
- Perangkat Android dengan USB Debugging aktif

## Instalasi
```bash
git clone https://github.com/zakyirhab/instahuman.git
cd instahuman
pip install -r requirements.txt
