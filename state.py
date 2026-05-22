"""state.py — global state mirip Meridian"""
import json, os

STATE = {
    "usdc_balance": 0.0,
    "open_positions": [],   # list of position dicts
    "trade_history": [],    # closed trades
}

STATE_FILE = "state.json"

async def load_state():
    global STATE
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            STATE.update(json.load(f))
    print(f"[STATE] Balance: ${STATE['usdc_balance']:.2f} | Posisi aktif: {len(STATE['open_positions'])}")

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(STATE, f, indent=2)
