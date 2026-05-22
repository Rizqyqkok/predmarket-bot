"""tools/seeker_tools.py — tools yang bisa dipanggil Seeker Agent"""
import httpx
import json
from config import CONFIG
from state import STATE

async def search_markets(category: str = "all", min_volume: float = None, max_days: int = None) -> dict:
    """Cari markets di Polymarket via GraphQL API"""
    min_vol = min_volume or CONFIG["min_volume"]
    max_d   = max_days   or CONFIG["max_days_to_resolution"]

    if CONFIG["platform"] == "polymarket":
        return await _search_polymarket(category, min_vol, max_d)
    else:
        return await _search_kalshi(category, min_vol, max_d)

async def _search_polymarket(category: str, min_volume: float, max_days: int) -> dict:
    """Polymarket Gamma API — markets endpoint"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://gamma-api.polymarket.com/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": 50,
                    "tag": category if category != "all" else None,
                }
            )
            r.raise_for_status()
            markets = r.json()

        # Filter sesuai config
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=max_days)

        filtered = []
        for m in markets:
            volume = float(m.get("volume", 0))
            end_dt_str = m.get("endDateIso") or m.get("end_date_iso")
            if not end_dt_str:
                continue
            end_dt = datetime.fromisoformat(end_dt_str.replace("Z", "+00:00"))

            if volume >= min_volume and end_dt <= deadline:
                filtered.append({
                    "id": m.get("id"),
                    "question": m.get("question"),
                    "volume": volume,
                    "yes_price": float(m.get("bestAsk", 0.5)),
                    "no_price": round(1 - float(m.get("bestAsk", 0.5)), 3),
                    "end_date": end_dt_str,
                    "days_left": (end_dt - now).days,
                })

        return {"markets": filtered[:15], "total": len(filtered)}

    except Exception as e:
        return {"error": str(e), "markets": []}

async def _search_kalshi(category: str, min_volume: float, max_days: int) -> dict:
    """Kalshi REST API — markets endpoint"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {"Authorization": f"Token {CONFIG['kalshi_api_key']}"}
            r = await client.get(
                "https://trading-api.kalshi.com/trade-api/v2/markets",
                headers=headers,
                params={"status": "open", "limit": 50}
            )
            r.raise_for_status()
            data = r.json()

        markets = data.get("markets", [])
        filtered = [m for m in markets if float(m.get("volume", 0)) >= min_volume]

        return {"markets": filtered[:15], "total": len(filtered)}
    except Exception as e:
        return {"error": str(e), "markets": []}

async def get_orderbook(market_id: str) -> dict:
    """Cek kedalaman orderbook sebelum masuk posisi"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://clob.polymarket.com/book",
                params={"token_id": market_id}
            )
            r.raise_for_status()
            book = r.json()

        bids = book.get("bids", [])
        asks = book.get("asks", [])
        total_bid_size = sum(float(b.get("size", 0)) for b in bids[:5])
        total_ask_size = sum(float(a.get("size", 0)) for a in asks[:5])

        return {
            "market_id": market_id,
            "best_bid": bids[0] if bids else None,
            "best_ask": asks[0] if asks else None,
            "bid_liquidity_top5": total_bid_size,
            "ask_liquidity_top5": total_ask_size,
            "sufficient_liquidity": total_ask_size >= CONFIG["usdc_per_trade"],
        }
    except Exception as e:
        return {"error": str(e)}

async def estimate_probability(market_id: str, question: str) -> dict:
    """
    Estimasi probabilitas real menggunakan:
    1. Fetch berita terkini via NewsAPI (atau GNews sebagai fallback gratis)
    2. Fetch community forecast dari Metaculus (jika ada market yang match)
    3. Feed semua ke LLM → reasoning step-by-step → output probabilitas angka
    """
    # Step 1: ambil berita terkini
    headlines = await _fetch_news(question)

    # Step 2: Metaculus community forecast (opsional, best-effort)
    metaculus = await _fetch_metaculus(question)

    # Step 3: LLM reasoning dengan semua data
    probability = await _llm_estimate(question, headlines, metaculus)

    return {
        "market_id": market_id,
        "question": question,
        "estimated_probability": probability["prob"],
        "confidence": probability["confidence"],
        "reasoning": probability["reasoning"],
        "news_headlines": headlines[:5],
        "metaculus_forecast": metaculus,
    }


async def _fetch_news(query: str) -> list[str]:
    """
    Ambil headline berita terkini.
    Prioritas: NewsAPI (akurat, butuh key) → GNews (gratis, limit 100/hari)
    """
    headlines = []

    # Coba NewsAPI dulu
    if CONFIG.get("newsapi_key"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query[:100],
                        "sortBy": "publishedAt",
                        "pageSize": 10,
                        "language": "en",
                        "apiKey": CONFIG["newsapi_key"],
                    }
                )
                r.raise_for_status()
                articles = r.json().get("articles", [])
                headlines = [
                    f"{a['title']} ({a['source']['name']}, {a['publishedAt'][:10]})"
                    for a in articles if a.get("title")
                ]
                if headlines:
                    return headlines
        except Exception as e:
            print(f"[NEWS] NewsAPI error: {e}")

    # Fallback: GNews (gratis, 100 req/hari)
    if CONFIG.get("gnews_key"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://gnews.io/api/v4/search",
                    params={
                        "q": query[:100],
                        "lang": "en",
                        "max": 10,
                        "token": CONFIG["gnews_key"],
                    }
                )
                r.raise_for_status()
                articles = r.json().get("articles", [])
                headlines = [
                    f"{a['title']} ({a['source']['name']}, {a['publishedAt'][:10]})"
                    for a in articles if a.get("title")
                ]
        except Exception as e:
            print(f"[NEWS] GNews error: {e}")

    return headlines or ["No recent news found for this query."]


async def _fetch_metaculus(question: str) -> dict | None:
    """
    Cari forecast dari Metaculus berdasarkan keyword question.
    Metaculus punya API publik, tidak butuh key.
    """
    try:
        # Ambil 3 kata kunci terpenting dari question
        keywords = " ".join(question.split()[:5])
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://www.metaculus.com/api2/questions/",
                params={
                    "search": keywords,
                    "status": "open",
                    "order_by": "-activity",
                    "limit": 3,
                },
                headers={"User-Agent": "PredMarketBot/1.0"}
            )
            r.raise_for_status()
            results = r.json().get("results", [])

        if not results:
            return None

        best = results[0]
        community = best.get("community_prediction", {})
        return {
            "title": best.get("title"),
            "url": f"https://www.metaculus.com/questions/{best.get('id')}",
            "community_yes_prob": community.get("full", {}).get("q2"),  # median
            "forecaster_count": best.get("number_of_forecasters", 0),
        }
    except Exception as e:
        print(f"[METACULUS] Error: {e}")
        return None


async def _llm_estimate(question: str, headlines: list, metaculus: dict | None) -> dict:
    """
    Feed berita + Metaculus ke LLM, minta estimasi probabilitas dengan reasoning.
    Pakai model ringan (haiku) karena ini dipanggil sering.
    """
    news_block = "\n".join(f"- {h}" for h in headlines[:8])
    metaculus_block = (
        f"Metaculus community forecast: {metaculus['community_yes_prob']*100:.1f}% YES "
        f"({metaculus['forecaster_count']} forecasters) — {metaculus['title']}"
        if metaculus and metaculus.get("community_yes_prob")
        else "No Metaculus data available."
    )

    prompt = f"""You are a superforecaster. Estimate the probability of this prediction market resolving YES.

Question: {question}

Recent news headlines:
{news_block}

External forecasts:
{metaculus_block}

Instructions:
1. Analyze the news headlines — do they suggest YES or NO?
2. Consider base rates for this type of event.
3. Weight the Metaculus forecast if available.
4. Give a final probability estimate as a number between 0.01 and 0.99.
5. Rate your confidence: LOW / MEDIUM / HIGH

Respond ONLY in this JSON format (no markdown, no extra text):
{{"prob": 0.65, "confidence": "MEDIUM", "reasoning": "2-3 sentence explanation"}}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {CONFIG['openrouter_api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CONFIG["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 300,
                }
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            # strip markdown fence jika ada
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
    except Exception as e:
        print(f"[LLM ESTIMATE] Error: {e}")
        return {"prob": 0.5, "confidence": "LOW", "reasoning": f"LLM error: {e}"}

async def place_order(market_id: str, side: str, amount_usdc: float) -> dict:
    """
    Eksekusi order — DRY_RUN tidak kirim request nyata
    side: "YES" atau "NO"
    """
    if CONFIG["dry_run"]:
        result = {
            "status": "DRY_RUN",
            "market_id": market_id,
            "side": side,
            "amount_usdc": amount_usdc,
            "message": "Simulasi — tidak ada order nyata dikirim",
        }
        print(f"[DRY RUN] place_order: {result}")
        # Notifikasi Telegram
        from telegram import notify_order_placed
        await notify_order_placed(
            {"question": f"Market {market_id}", "market_id": market_id},
            side, amount_usdc, dry_run=True
        )
        return result

    # Live order — implementasi via py-clob-client untuk Polymarket
    # from py_clob_client.client import ClobClient
    # client = ClobClient(host="https://clob.polymarket.com", key=CONFIG["polymarket_private_key"])
    # order = client.create_market_order(...)
    return {"status": "NOT_IMPLEMENTED", "note": "Tambahkan py-clob-client untuk live trading"}
