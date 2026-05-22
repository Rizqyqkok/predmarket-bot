# predmarket-bot

Prediction market bot berbasis dua agent async untuk mencari peluang market dan
mengelola posisi aktif. Bot ini dirancang untuk Polymarket sebagai default, dengan
struktur awal untuk Kalshi.

> Status: aman untuk eksperimen karena default berjalan dalam `DRY_RUN=true`.
> Live trading belum diimplementasikan penuh.

## Cara Kerja

Bot berjalan dari `index.py` dan menjalankan dua agent secara paralel:

1. `Seeker Agent`
   - Mencari market aktif di Polymarket atau Kalshi.
   - Memfilter berdasarkan volume, edge minimum, waktu resolusi, dan skor kredibilitas.
   - Mengambil orderbook untuk cek likuiditas.
   - Mengestimasi probabilitas dengan berita terbaru, Metaculus, dan LLM.
   - Menempatkan order jika semua filter lolos.

2. `Monitor Agent`
   - Membaca posisi aktif dari `state.json`.
   - Mengambil harga live untuk menghitung PnL.
   - Mengecek status market.
   - Memutuskan `HOLD`, `SELL`, atau `HEDGE`.

## Struktur Project

```text
.
|-- index.py                  # Entrypoint utama
|-- agent.py                  # ReAct loop Seeker dan Monitor
|-- config.py                 # Konfigurasi dari .env
|-- prompt.py                 # System prompt agent
|-- state.py                  # State lokal bot
|-- lessons.py                # Penyimpanan lesson/history sederhana
|-- telegram.py               # Notifikasi Telegram
|-- tools/
|   |-- seeker_tools.py       # Search market, orderbook, estimasi probabilitas
|   `-- monitor_tools.py      # Posisi, harga live, sell, hedge
|-- requirements.txt
`-- .env.example
```

## Setup

Clone repo:

```bash
git clone https://github.com/Rizqyqkok/predmarket-bot.git
cd predmarket-bot
```

Buat virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

Buat file `.env` dari contoh:

```bash
copy .env.example .env
```

Isi minimal:

```env
OPENROUTER_API_KEY=sk-or-...
DRY_RUN=true
PLATFORM=polymarket
```

Opsional untuk data berita dan notifikasi:

```env
NEWSAPI_KEY=
GNEWS_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Jalankan bot:

```bash
python index.py
```

## Konfigurasi Penting

Semua konfigurasi ada di `.env` dan dibaca oleh `config.py`.

```env
MAX_POSITIONS=3
USDC_PER_TRADE=10
MIN_BALANCE_USDC=5
MIN_VOLUME=5000
MIN_EDGE=0.05
MAX_DAYS_RESOLUTION=7
SELL_PROFIT=0.15
CUT_LOSS=-0.30
SEEKER_INTERVAL=1800
MONITOR_INTERVAL=300
```

## Catatan Safety

- Jangan set `DRY_RUN=false` sebelum implementasi live order benar-benar selesai.
- `POLYMARKET_PRIVATE_KEY` tidak boleh di-commit ke GitHub.
- File `.env`, `state.json`, dan `lessons.json` sudah masuk `.gitignore`.
- Kode live trading saat ini masih placeholder `NOT_IMPLEMENTED`.

## Roadmap

- Simpan posisi dry-run ke `state.json`.
- Panggil `save_state()` setelah order/sell/hedge.
- Integrasikan `save_lesson()` ke siklus agent.
- Implementasi live trading dengan `py-clob-client`.
- Tambah unit test untuk parser tool call dan state transition.
