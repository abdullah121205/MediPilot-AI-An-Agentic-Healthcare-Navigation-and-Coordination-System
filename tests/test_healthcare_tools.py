import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date, timedelta
from tools.healthcare_tools import search_providers, check_availability, book_appointment
from tools.triage import retrieve_guidelines

def next_weekday(wd):  # 0=Mon
    d = date.today() + timedelta(days=1)
    while d.weekday() != wd:
        d += timedelta(days=1)
    return d.isoformat()

print("== search_providers('cardiology','Boston','Aetna')")
res = search_providers("cardiology", "Boston", "Aetna")
print(json.dumps(res, indent=2))

print("== urgent care near Back Bay")
print([r["name"] for r in search_providers("urgent care", "Back Bay")])

doc = res[0]["id"]
day = next_weekday(0)
print(f"== check_availability({doc}, {day})")
av = check_availability(doc, day)
print(av)

print("== book_appointment")
slot = f"{day} {av['available_slots'][0]}"
b = book_appointment("Test Patient", doc, slot)
print(b)
print("double-book:", book_appointment("Another", doc, slot))

print("== RAG")
for r in retrieve_guidelines("chest pain spreading to my left arm and sweating", 2):
    print(r["urgency"], "|", r["source"], "|", r["guideline"][:80], "...")
for r in retrieve_guidelines("my toddler has a high temperature and a rash", 2):
    print(r["urgency"], "|", r["source"])