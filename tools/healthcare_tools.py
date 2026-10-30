"""Mock healthcare tools for the agents (Member 3).

Import these in Member 1's agent code:
    from tools.healthcare_tools import search_providers, check_availability, book_appointment
Every function returns plain dicts/lists (JSON-serializable) so they plug
straight into LLM function-calling.
"""
import json, math, os, random, string
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # repo root


def _find_data_dir(filename):
    """Prefer AGENTX_DATA_DIR (judges' contract), fall back to ./data in the repo."""
    env = os.environ.get("AGENTX_DATA_DIR")
    for d in ([Path(env)] if env else []) + [BASE / "data"]:
        if (d / filename).exists():
            return d
    return BASE / "data"


DATA_DIR = _find_data_dir("mock_data.json")
DATA = json.loads((DATA_DIR / "mock_data.json").read_text(encoding="utf-8"))
BOOKINGS_FILE = DATA_DIR / "bookings.json"
DOCTORS = {d["id"]: d for d in DATA["doctors"]}

SPECIALTY_ALIASES = {
    "gp": "general practice", "family doctor": "general practice", "family medicine": "general practice",
    "primary care": "general practice", "cardiologist": "cardiology", "heart": "cardiology",
    "pediatrician": "pediatrics", "child": "pediatrics", "neurologist": "neurology",
    "orthopedic": "orthopedics", "bone": "orthopedics", "dermatologist": "dermatology", "skin": "dermatology",
    "gastroenterologist": "gastroenterology", "stomach": "gastroenterology", "psychiatrist": "psychiatry",
    "mental health": "psychiatry", "pulmonologist": "pulmonology", "lung": "pulmonology",
    "gynecology": "obstetrics and gynecology", "gynecologist": "obstetrics and gynecology",
    "obgyn": "obstetrics and gynecology", "ent specialist": "ent", "endocrinologist": "endocrinology",
    "diabetes": "endocrinology", "er": "emergency room", "emergency": "emergency room",
    "emergency department": "emergency room", "lab": "diagnostic lab", "labs": "diagnostic lab",
    "blood test": "diagnostic lab", "imaging": "diagnostic lab", "walk-in": "urgent care",
}


def _load_bookings():
    if BOOKINGS_FILE.exists():
        return json.loads(BOOKINGS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_bookings(b):
    BOOKINGS_FILE.write_text(json.dumps(b, indent=2), encoding="utf-8")


def _norm(s):
    s = (s or "").strip().lower()
    return SPECIALTY_ALIASES.get(s, s)


def _km(lat1, lng1, lat2, lng2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2)
    return round(12742 * math.asin(math.sqrt(a)), 1)


def _location_score(rec, location):
    """Returns (score 0-1, distance_km or None). location = area/city name or 'lat,lng'."""
    loc = (location or "").strip().lower()
    if not loc:
        return 0.5, None
    try:
        lat, lng = [float(x) for x in loc.split(",")]
        dist = _km(lat, lng, rec["lat"], rec["lng"])
        return max(0.0, 1 - dist / 20), dist
    except ValueError:
        pass
    if loc == rec["area"].lower():
        return 1.0, None
    if loc == rec["city"].lower() or loc in rec["city"].lower() or loc in rec["area"].lower():
        return 0.8, None
    return 0.0, None


def search_providers(specialty: str, location: str, insurance: str = None, top_k: int = 5):
    """Filter doctors + facilities and return the top matches (best first).

    specialty: e.g. "cardiology", "urgent care", "ER", "lab" (aliases like "cardiologist" work)
    location:  city/area name ("Boston", "Back Bay") or "lat,lng"
    insurance: optional insurer name, e.g. "Aetna"; non-accepting providers are excluded
    """
    spec = _norm(specialty)
    results = []
    pool = [("doctor", d, d["specialty"], d["affiliation"]) for d in DATA["doctors"]] + \
           [("facility", f, f["type"], f["name"]) for f in DATA["facilities"]]
    for kind, rec, rec_spec, display in pool:
        if spec and spec not in rec_spec and rec_spec not in spec:
            continue
        if insurance and insurance.lower() not in [i.lower() for i in rec["accepted_insurance"]]:
            continue
        loc_score, dist = _location_score(rec, location)
        if location and loc_score == 0.0:
            continue
        score = round(0.6 * loc_score + 0.4 * rec["rating"] / 5, 3)
        item = {"id": rec["id"], "type": kind, "name": rec["name"], "specialty": rec_spec,
                "location": display, "city": rec["city"], "area": rec["area"],
                "accepted_insurance": rec["accepted_insurance"], "rating": rec["rating"],
                "match_score": score}
        if dist is not None:
            item["distance_km"] = dist
        if kind == "facility":
            item["address"], item["hours"] = rec["address"], rec["hours"]
        results.append(item)
    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results[:top_k]


def _all_slots(doc, date_obj):
    sch = doc["schedule"]
    if date_obj.strftime("%a") not in sch["days"]:
        return []
    t = datetime.combine(date_obj, datetime.strptime(sch["start"], "%H:%M").time())
    end = datetime.combine(date_obj, datetime.strptime(sch["end"], "%H:%M").time())
    out = []
    while t + timedelta(minutes=doc["slot_minutes"]) <= end:
        out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=doc["slot_minutes"])
    return out


def check_availability(doctor_id: str, date: str):
    """Open 30-minute slots for a doctor on date (YYYY-MM-DD)."""
    doc = DOCTORS.get(doctor_id)
    if not doc:
        return {"ok": False, "error": f"Unknown doctor_id '{doctor_id}'"}
    try:
        d = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"ok": False, "error": "date must be YYYY-MM-DD"}
    taken = {b["slot"] for b in _load_bookings().values()
             if b["doctor_id"] == doctor_id and b["slot"].startswith(date) and b["status"] == "confirmed"}
    # deterministic fake "already booked" slots so the demo looks realistic
    rng = random.Random(f"{doctor_id}{date}")
    slots = [s for s in _all_slots(doc, d) if rng.random() > 0.3 and f"{date} {s}" not in taken]
    return {"ok": True, "doctor_id": doctor_id, "doctor": doc["name"], "date": date,
            "available_slots": slots,
            "message": "" if slots else "No open slots (doctor off or fully booked) - try another date."}


def book_appointment(patient_name: str, doctor_id: str, slot: str):
    """Reserve a slot. slot format: 'YYYY-MM-DD HH:MM'. Returns a confirmation ID."""
    if not patient_name or not patient_name.strip():
        return {"ok": False, "error": "patient_name required"}
    try:
        dt = datetime.strptime(slot, "%Y-%m-%d %H:%M")
    except ValueError:
        return {"ok": False, "error": "slot must be 'YYYY-MM-DD HH:MM'"}
    avail = check_availability(doctor_id, dt.strftime("%Y-%m-%d"))
    if not avail["ok"]:
        return avail
    if dt.strftime("%H:%M") not in avail["available_slots"]:
        return {"ok": False, "error": "Slot not available", "available_slots": avail["available_slots"]}
    bookings = _load_bookings()
    cid = "APT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    bookings[cid] = {"confirmation_id": cid, "patient_name": patient_name.strip(),
                     "doctor_id": doctor_id, "slot": slot, "status": "confirmed"}
    _save_bookings(bookings)
    return {"ok": True, "confirmation_id": cid, "patient_name": patient_name.strip(),
            "doctor": DOCTORS[doctor_id]["name"], "location": DOCTORS[doctor_id]["affiliation"], "slot": slot}


# JSON schemas for LLM function calling (OpenAI-style; adapt for Gemini/Claude as needed)
TOOL_SPECS = [
    {"name": "search_providers", "description": "Find doctors/facilities by specialty, location, insurance.",
     "parameters": {"type": "object", "properties": {
         "specialty": {"type": "string"}, "location": {"type": "string"},
         "insurance": {"type": "string"}}, "required": ["specialty", "location"]}},
    {"name": "check_availability", "description": "Open 30-minute slots for a doctor on a date.",
     "parameters": {"type": "object", "properties": {
         "doctor_id": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD"}},
         "required": ["doctor_id", "date"]}},
    {"name": "book_appointment", "description": "Book a slot, returns confirmation ID.",
     "parameters": {"type": "object", "properties": {
         "patient_name": {"type": "string"}, "doctor_id": {"type": "string"},
         "slot": {"type": "string", "description": "YYYY-MM-DD HH:MM"}},
         "required": ["patient_name", "doctor_id", "slot"]}},
]