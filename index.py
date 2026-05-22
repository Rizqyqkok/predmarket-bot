"""
Prediction Market Bot — arsitektur berbasis Meridian
Platform: Polymarket (default) atau Kalshi
"""
import asyncio
from agent import run_seeker, run_monitor
from state import load_state
from config import CONFIG
from telegram import notify_startup

async def main():
    print("=== Prediction Market Bot ===")
    print(f"Platform : {CONFIG['platform']}")
    print(f"DRY RUN  : {CONFIG['dry_run']}")
    print(f"Max pos  : {CONFIG['max_positions']}")
    print(f"Per trade: ${CONFIG['usdc_per_trade']} USDC")
    print("============================")

    await load_state()
    await notify_startup(CONFIG)

    # Dua agent jalan paralel, mirip Meridian
    await asyncio.gather(
        run_seeker(),   # tiap 30–60 menit — cari market beredge
        run_monitor(),  # tiap 5–10 menit  — kelola posisi aktif
    )

if __name__ == "__main__":
    asyncio.run(main())
