"""
telegram.py — integrasi Telegram bot
Notifikasi: order baru, posisi ditutup, alert, summary harian, error kritis
"""
import httpx
import asyncio
from datetime import datetime
from config import CONFIG

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# ─── Core sender ──────────────────────────────────────────────────────────────

async def send_message(text: str, parse_mode: str = "HTML", silent: bool = False) -> bool:
    """Kirim pesan ke chat_id yang sudah dikonfigurasi"""
    token = CONFIG.get("telegram_bot_token")
    chat_id = CONFIG.get("telegram_chat_id")

    if not token or not chat_id:
        print(f"[TELEGRAM] Tidak dikonfigurasi, skip: {text[:60]}")
        return False

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_notification": silent,
            })
            r.raise_for_status()
            return True
    except Exception as e:
        print(f"[TELEGRAM] Gagal kirim: {e}")
        return False

# ─── Seeker notifications ─────────────────────────────────────────────────────

async def notify_market_found(market: dict, probability: dict):
    """Seeker menemukan market dengan edge — sebelum order"""
    edge = probability["prob"] - market.get("yes_price", 0.5)
    edge_pct = abs(edge) * 100
    side = "YES ✅" if edge > 0 else "NO ❌"

    msg = (
        f"🔍 <b>MARKET DITEMUKAN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ {market.get('question', 'N/A')}\n\n"
        f"📊 <b>Analisis</b>\n"
        f"  Harga pasar YES : {market.get('yes_price', 0)*100:.1f}¢\n"
        f"  Estimasi prob   : {probability['prob']*100:.1f}%\n"
        f"  Edge            : +{edge_pct:.1f}% → masuk <b>{side}</b>\n"
        f"  Confidence      : {probability.get('confidence', 'N/A')}\n\n"
        f"💬 <i>{probability.get('reasoning', '')}</i>\n\n"
        f"📅 Resolusi: {market.get('days_left', '?')} hari lagi\n"
        f"💧 Volume  : ${market.get('volume', 0):,.0f}"
    )
    await send_message(msg)


async def notify_order_placed(market: dict, side: str, amount_usdc: float, dry_run: bool):
    """Order berhasil dieksekusi (atau simulasi)"""
    label = "🟡 DRY RUN" if dry_run else "🟢 ORDER LIVE"
    emoji = "✅" if side == "YES" else "❌"

    msg = (
        f"{label} — <b>ORDER DITEMPATKAN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} <b>{side}</b> @ ${amount_usdc:.2f} USDC\n"
        f"❓ {market.get('question', 'N/A')}\n"
        f"🕐 {_now()}"
    )
    await send_message(msg)

# ─── Monitor notifications ────────────────────────────────────────────────────

async def notify_position_closed(position: dict, reason: str, pnl_pct: float, pnl_usdc: float):
    """Posisi ditutup — SELL atau expired"""
    if pnl_pct >= 0:
        emoji = "💰"
        label = "PROFIT"
    else:
        emoji = "🔴"
        label = "LOSS"

    msg = (
        f"{emoji} <b>POSISI DITUTUP — {label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ {position.get('question', 'N/A')}\n\n"
        f"📈 PnL   : {'+' if pnl_pct >= 0 else ''}{pnl_pct*100:.1f}% "
        f"(${'+' if pnl_usdc >= 0 else ''}{pnl_usdc:.2f})\n"
        f"📌 Alasan: {reason}\n"
        f"🕐 {_now()}"
    )
    await send_message(msg)


async def notify_hedge_placed(market: dict, side: str, amount_usdc: float):
    """Hedge order dipasang"""
    msg = (
        f"🛡️ <b>HEDGE DIPASANG</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ {market.get('question', 'N/A')}\n"
        f"🔄 Beli {side} @ ${amount_usdc:.2f} USDC\n"
        f"🕐 {_now()}"
    )
    await send_message(msg)


async def notify_position_held(position: dict):
    """Monitor memutuskan HOLD — silent, tidak notif user (opsional enable)"""
    # Silent by default agar tidak spam
    print(f"[MONITOR] HOLD: {position.get('question', '')[:60]}")

# ─── Summary & alerts ────────────────────────────────────────────────────────

async def send_daily_summary(state: dict):
    """Ringkasan harian — total PnL, posisi aktif, trades hari ini"""
    open_pos = state.get("open_positions", [])
    history = state.get("trade_history", [])

    # Hitung PnL hari ini
    today = datetime.utcnow().date().isoformat()
    today_trades = [t for t in history if t.get("closed_at", "").startswith(today)]
    today_pnl = sum(t.get("pnl_usdc", 0) for t in today_trades)
    total_pnl = sum(t.get("pnl_usdc", 0) for t in history)

    pnl_emoji = "📈" if today_pnl >= 0 else "📉"

    positions_text = ""
    for p in open_pos:
        pnl = p.get("pnl_pct", 0) * 100
        positions_text += f"\n  • {p.get('question', 'N/A')[:40]}... → {'+' if pnl >= 0 else ''}{pnl:.1f}%"

    msg = (
        f"📊 <b>DAILY SUMMARY</b> — {today}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} PnL hari ini : ${today_pnl:+.2f}\n"
        f"💼 Total PnL    : ${total_pnl:+.2f}\n"
        f"📌 Posisi aktif : {len(open_pos)}\n"
        f"🔄 Trade hari ini: {len(today_trades)}\n"
        f"💵 Balance      : ${state.get('usdc_balance', 0):.2f} USDC"
    )
    if positions_text:
        msg += f"\n\n<b>Open positions:</b>{positions_text}"

    await send_message(msg)


async def notify_error(agent: str, error: str):
    """Error kritis — selalu kirim, tidak silent"""
    msg = (
        f"⚠️ <b>ERROR — {agent}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{error[:300]}</code>\n"
        f"🕐 {_now()}"
    )
    await send_message(msg)


async def notify_startup(config: dict):
    """Bot startup — konfirmasi bot aktif"""
    mode = "🟡 DRY RUN" if config.get("dry_run") else "🟢 LIVE"
    msg = (
        f"🚀 <b>BOT STARTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Platform  : {config.get('platform', '?').upper()}\n"
        f"Mode      : {mode}\n"
        f"Max pos   : {config.get('max_positions', '?')}\n"
        f"Per trade : ${config.get('usdc_per_trade', '?')} USDC\n"
        f"Min edge  : {config.get('min_edge', 0)*100:.0f}%\n"
        f"🕐 {_now()}"
    )
    await send_message(msg)

# ─── Helper ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
