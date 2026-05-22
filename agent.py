"""
agent.py — ReAct loop untuk Seeker & Monitor Agent
Pola: LLM reason dulu → call tool → act → repeat
"""
import asyncio
import json
import httpx
from config import CONFIG
from state import STATE
from prompt import build_seeker_prompt, build_monitor_prompt
from lessons import load_lessons
from tools.seeker_tools import search_markets, get_orderbook, estimate_probability, place_order
from tools.monitor_tools import get_positions, get_market_status, sell_position, hedge_position
from telegram import notify_error, notify_startup

TOOLS_SEEKER = {
    "search_markets": search_markets,
    "get_orderbook": get_orderbook,
    "estimate_probability": estimate_probability,
    "place_order": place_order,
}

TOOLS_MONITOR = {
    "get_positions": get_positions,
    "get_market_status": get_market_status,
    "sell_position": sell_position,
    "hedge_position": hedge_position,
}

# ─── ReAct Loop Core ─────────────────────────────────────────────────────────

async def react_loop(agent_name: str, system_prompt: str, tools: dict, max_steps: int = 10):
    """
    ReAct loop: LLM reason → pilih tool → execute → observe → repeat
    Sama persis dengan pola Meridian, hanya tool-nya berbeda.
    """
    messages = []
    messages.append({
        "role": "user",
        "content": "Begin your analysis cycle now. Think step by step before taking action."
    })

    print(f"\n[{agent_name}] Memulai siklus analisis...")

    for step in range(max_steps):
        response = await call_llm(system_prompt, messages)
        content = response.get("content", "")
        messages.append({"role": "assistant", "content": content})

        print(f"[{agent_name}] Step {step+1}: {content[:120]}...")

        # Parse tool call dari response LLM
        tool_call = parse_tool_call(content)

        if tool_call is None:
            print(f"[{agent_name}] Siklus selesai — tidak ada tool call.")
            break

        tool_name = tool_call.get("tool")
        tool_args = tool_call.get("args", {})

        if tool_name not in tools:
            print(f"[{agent_name}] Tool tidak dikenal: {tool_name}")
            break

        print(f"[{agent_name}] Memanggil: {tool_name}({tool_args})")
        result = await tools[tool_name](**tool_args)

        observation = f"Tool result [{tool_name}]: {json.dumps(result, indent=2)}"
        messages.append({"role": "user", "content": observation})

    return messages

# ─── Seeker Agent ─────────────────────────────────────────────────────────────

async def run_seeker():
    """Seeker Agent — berjalan tiap 30 menit, cari market beredge"""
    while True:
        try:
            lessons = load_lessons()
            prompt = build_seeker_prompt(STATE, lessons, CONFIG)
            await react_loop("SEEKER", prompt, TOOLS_SEEKER)
        except Exception as e:
            print(f"[SEEKER] Error: {e}")
            await notify_error("SEEKER", str(e))

        interval = CONFIG["seeker_interval_sec"]
        print(f"[SEEKER] Tidur {interval//60} menit...")
        await asyncio.sleep(interval)

# ─── Monitor Agent ────────────────────────────────────────────────────────────

async def run_monitor():
    """Monitor Agent — berjalan tiap 5 menit, kelola posisi aktif"""
    while True:
        try:
            if STATE["open_positions"]:
                lessons = load_lessons()
                prompt = build_monitor_prompt(STATE, lessons, CONFIG)
                await react_loop("MONITOR", prompt, TOOLS_MONITOR)
            else:
                print("[MONITOR] Tidak ada posisi aktif, skip siklus.")
        except Exception as e:
            print(f"[MONITOR] Error: {e}")
            await notify_error("MONITOR", str(e))

        interval = CONFIG["monitor_interval_sec"]
        print(f"[MONITOR] Tidur {interval//60} menit...")
        await asyncio.sleep(interval)

# ─── LLM Call ─────────────────────────────────────────────────────────────────

async def call_llm(system_prompt: str, messages: list) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {CONFIG['openrouter_api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": CONFIG["model"],
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "temperature": 0.2,
                "max_tokens": 1500,
            }
        )
        r.raise_for_status()
        data = r.json()
        return {"content": data["choices"][0]["message"]["content"]}

# ─── Tool Call Parser ─────────────────────────────────────────────────────────

def parse_tool_call(text: str) -> dict | None:
    """
    LLM diinstruksikan output tool call dalam format JSON:
    <tool>{"tool": "search_markets", "args": {"category": "crypto"}}</tool>
    """
    import re
    match = re.search(r"<tool>(.*?)</tool>", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None
