"""lessons.py — sistem pembelajaran, sama persis dengan Meridian"""
import json, os
from datetime import datetime

LESSONS_FILE = "lessons.json"

def load_lessons() -> list:
    if not os.path.exists(LESSONS_FILE):
        return []
    with open(LESSONS_FILE) as f:
        return json.load(f)

def save_lesson(lesson: str, agent: str = "unknown"):
    lessons = load_lessons()
    lessons.append({
        "timestamp": datetime.utcnow().isoformat(),
        "agent": agent,
        "lesson": lesson,
    })
    with open(LESSONS_FILE, "w") as f:
        json.dump(lessons, f, indent=2)
    print(f"[LESSON] Disimpan: {lesson[:80]}")

def evolve_thresholds(config: dict) -> dict:
    """
    Analisis lessons dan update threshold otomatis.
    Contoh: kalau banyak loss di market low-volume, naikkan min_volume.
    Implementasi bisa pakai LLM untuk parsing lessons dan suggest config baru.
    """
    lessons = load_lessons()
    # TODO: parse lessons → suggest threshold adjustments via LLM
    return config
