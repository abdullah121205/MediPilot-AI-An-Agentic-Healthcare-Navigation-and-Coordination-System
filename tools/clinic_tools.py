"""Clinic finder tool (Member 3).

search_clinics_by_specialty("orthopedics", max_wait_time=20)
-> matching clinics from data/clinics.csv, shortest wait first (ties: higher rating first).
"""
import csv
import os
from pathlib import Path

CSV_NAME = "clinics.csv"
REPO_ROOT = Path(__file__).resolve().parents[1]  # app/tools/clinic_tools.py -> repo root

# Common words -> specialty names used in the CSV (lowercase)
ALIASES = {
    "ortho": "orthopedics", "orthopedic": "orthopedics", "orthopaedics": "orthopedics",
    "bone": "orthopedics", "joint": "orthopedics", "fracture": "orthopedics",
    "er": "emergency medicine", "emergency": "emergency medicine", "trauma": "emergency medicine",
    "skin": "dermatology", "dermatologist": "dermatology", "rash": "dermatology", "allergy": "dermatology",
    "lung": "pulmonology", "pulmonologist": "pulmonology", "breathing": "pulmonology", "asthma": "pulmonology",
    "gp": "general practice", "family": "general practice", "family medicine": "general practice",
    "primary care": "general practice", "general": "general practice", "general physician": "general practice",
    "heart": "cardiology", "cardiologist": "cardiology", "cardiac": "cardiology",
    "child": "pediatrics", "pediatrician": "pediatrics", "paediatrics": "pediatrics", "kids": "pediatrics",
    "neurologist": "neurology", "brain": "neurology", "headache": "neurology",
    "stomach": "gastroenterology", "gastro": "gastroenterology", "digestive": "gastroenterology",
    "mental health": "psychiatry", "psychiatrist": "psychiatry",
    "gynaecology": "gynecology", "gynecologist": "gynecology", "obgyn": "gynecology", "women": "gynecology",
    "urgent": "urgent care", "walk-in": "urgent care", "ear": "ent", "nose": "ent", "throat": "ent",
    "diabetes": "endocrinology", "thyroid": "endocrinology", "endocrinologist": "endocrinology",
    "eye": "ophthalmology", "ophthalmologist": "ophthalmology",
}


def _csv_path():
    """Prefer AGENTX_DATA_DIR (judges' contract), fall back to <repo>/data."""
    env = os.environ.get("AGENTX_DATA_DIR")
    for folder in ([Path(env)] if env else []) + [REPO_ROOT / "data"]:
        if (folder / CSV_NAME).exists():
            return folder / CSV_NAME
    return REPO_ROOT / "data" / CSV_NAME


def _load_clinics():
    try:
        with open(_csv_path(), newline="", encoding="utf-8") as f:
            rows = []
            for r in csv.DictReader(f):
                try:
                    rows.append({
                        "clinic_name": r["clinic_name"].strip(),
                        "specialty": r["specialty"].strip(),
                        "address": r["address"].strip(),
                        "phone": r["phone"].strip(),
                        "wait_time_mins": int(float(r["wait_time_mins"])),
                        "rating": float(r["rating"]),
                    })
                except (KeyError, ValueError, AttributeError):
                    continue  # skip malformed rows instead of crashing
            return rows
    except OSError:
        return []


def search_clinics_by_specialty(specialty: str, max_wait_time: int = None):
    """Find clinics for a specialty, sorted by shortest wait time.

    specialty:     e.g. "Orthopedics", "ER", "skin", "heart" (case-insensitive, aliases work)
    max_wait_time: optional; only clinics with wait_time_mins <= this value
    Returns a list of dicts (clinic_name, specialty, address, phone, wait_time_mins, rating);
    an empty list if nothing matches or the data file is missing.
    """
    query = (specialty or "").strip().lower()
    query = ALIASES.get(query, query)
    if max_wait_time is not None:
        try:
            max_wait_time = int(max_wait_time)
        except (TypeError, ValueError):
            max_wait_time = None

    matches = []
    for c in _load_clinics():
        spec = c["specialty"].lower()
        if query and query != spec and query not in spec and spec not in query:
            continue
        if max_wait_time is not None and c["wait_time_mins"] > max_wait_time:
            continue
        matches.append(c)
    matches.sort(key=lambda c: (c["wait_time_mins"], -c["rating"]))
    return matches


def format_clinics(clinics):
    """Human-readable text for the agent/UI to display."""
    if not clinics:
        return "No matching clinics found."
    return "\n".join(
        f"{i}. {c['clinic_name']} ({c['specialty']}) - {c['address']}, {c['phone']} | "
        f"wait {c['wait_time_mins']} min | rating {c['rating']}"
        for i, c in enumerate(clinics, 1))