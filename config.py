"""config.py — semua parameter bot"""
import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    # Platform: "polymarket" atau "kalshi"
    "platform": os.getenv("PLATFORM", "polymarket"),

    # Safety — selalu true dulu sampai siap live
    "dry_run": os.getenv("DRY_RUN", "true").lower() == "true",

    # Manajemen risiko
    "max_positions": int(os.getenv("MAX_POSITIONS", "3")),
    "usdc_per_trade": float(os.getenv("USDC_PER_TRADE", "10")),      # USDC per posisi
    "min_balance_usdc": float(os.getenv("MIN_BALANCE_USDC", "5")),   # buffer gas/fee

    # Filter Seeker Agent
    "min_volume": float(os.getenv("MIN_VOLUME", "5000")),             # USD
    "min_edge": float(os.getenv("MIN_EDGE", "0.05")),                 # 5% selisih prob vs harga
    "max_days_to_resolution": int(os.getenv("MAX_DAYS_RESOLUTION", "7")),
    "min_credibility_score": int(os.getenv("MIN_CREDIBILITY", "70")),

    # Monitor Agent
    "sell_profit_threshold": float(os.getenv("SELL_PROFIT", "0.15")), # jual kalau PnL +15%
    "cut_loss_threshold": float(os.getenv("CUT_LOSS", "-0.30")),      # cut loss -30%

    # Interval polling
    "seeker_interval_sec": int(os.getenv("SEEKER_INTERVAL", "1800")),  # 30 menit
    "monitor_interval_sec": int(os.getenv("MONITOR_INTERVAL", "300")), # 5 menit

    # API
    "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
    "polymarket_private_key": os.getenv("POLYMARKET_PRIVATE_KEY"),
    "kalshi_api_key": os.getenv("KALSHI_API_KEY"),
    "model": os.getenv("LLM_MODEL", "anthropic/claude-3-5-haiku"),

    # News feed — minimal salah satu diisi
    # NewsAPI: https://newsapi.org (gratis 100 req/hari untuk dev)
    # GNews  : https://gnews.io   (gratis 100 req/hari)
    "newsapi_key": os.getenv("NEWSAPI_KEY", ""),
    "gnews_key":   os.getenv("GNEWS_KEY", ""),

    # Telegram
    "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id":   os.getenv("TELEGRAM_CHAT_ID", ""),
}
