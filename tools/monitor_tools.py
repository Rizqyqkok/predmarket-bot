"""tools/monitor_tools.py — tools yang bisa dipanggil Monitor Agent"""
import httpx
from config import CONFIG
from state import STATE

async def get_positions() -> dict:
    """Ambil semua posisi aktif dari state lokal + update harga live"""
    positions = STATE.get("open_positions", [])
    if not positions:
        return {"positions": [], "message": "Tidak ada posisi aktif"}

    enriched = []
    for pos in positions:
        live_price = await _get_live_price(pos["market_id"], pos["side"])
        entry_price = pos.get("entry_price", 0.5)
        pnl_pct = (live_price - entry_price) / entry_price if entry_price > 0 else 0

        enriched.append({
            **pos,
            "current_price": live_price,
            "pnl_pct": round(pnl_pct, 4),
            "pnl_usdc": round(pnl_pct * pos.get("amount_usdc", 0), 2),
        })

    return {"positions": enriched}

async def _get_live_price(market_id: str, side: str) -> float:
    """Ambil harga terkini dari Polymarket"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://clob.polymarket.com/midpoint",
                params={"token_id": market_id}
            )
            r.raise_for_status()
            data = r.json()
            mid = float(data.get("mid", 0.5))
            return mid if side == "YES" else round(1 - mid, 4)
    except Exception:
        return 0.5  # fallback

async def get_market_status(market_id: str) -> dict:
    """Cek status market — apakah sudah resolved? ada update berita?"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://gamma-api.polymarket.com/markets/{market_id}"
            )
            r.raise_for_status()
            m = r.json()

        return {
            "market_id": market_id,
            "question": m.get("question"),
            "closed": m.get("closed", False),
            "resolved": m.get("resolved", False),
            "resolution_result": m.get("resolutionResult"),
            "end_date": m.get("endDateIso"),
            "current_yes_price": float(m.get("bestAsk", 0.5)),
        }
    except Exception as e:
        return {"error": str(e), "market_id": market_id}

async def sell_position(position_id: str, amount_usdc: float = None) -> dict:
    """Jual posisi — full atau partial"""
    pos = next((p for p in STATE["open_positions"] if p["id"] == position_id), None)
    if not pos:
        return {"error": f"Posisi {position_id} tidak ditemukan di state"}

    sell_amount = amount_usdc or pos.get("amount_usdc", 0)

    if CONFIG["dry_run"]:
        result = {
            "status": "DRY_RUN",
            "action": "SELL",
            "position_id": position_id,
            "amount_usdc": sell_amount,
            "message": "Simulasi sell — tidak ada transaksi nyata",
        }
        print(f"[DRY RUN] sell_position: {result}")
        # Notifikasi Telegram
        from telegram import notify_position_closed
        pnl_pct = pos.get("pnl_pct", 0)
        pnl_usdc = pos.get("pnl_usdc", 0)
        await notify_position_closed(
            pos,
            reason="DRY RUN SELL",
            pnl_pct=pnl_pct,
            pnl_usdc=pnl_usdc,
        )
        # Hapus dari state jika full sell
        if not amount_usdc or amount_usdc >= pos.get("amount_usdc", 0):
            STATE["open_positions"] = [
                p for p in STATE["open_positions"] if p["id"] != position_id
            ]
        return result

    # Live: implementasi via CLOB client
    return {"status": "NOT_IMPLEMENTED"}

async def hedge_position(market_id: str, side: str, amount_usdc: float) -> dict:
    """Beli sisi berlawanan untuk hedge risiko"""
    if CONFIG["dry_run"]:
        result = {
            "status": "DRY_RUN",
            "action": "HEDGE",
            "market_id": market_id,
            "side": side,
            "amount_usdc": amount_usdc,
            "message": "Simulasi hedge",
        }
        print(f"[DRY RUN] hedge_position: {result}")
        return result

    return {"status": "NOT_IMPLEMENTED"}
