"""Agent-facing wrappers (Member 3). Each class follows the starter's Tool interface:
name, description, args_doc, execute(**kwargs). Register them in tools/__init__.py."""
import json

from tools import Tool
from tools.clinic_tools import search_clinics_by_specialty, format_clinics
from tools.healthcare_tools import search_providers, check_availability, book_appointment
from tools.triage import retrieve_guidelines


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False)


class ClinicFinder(Tool):
    name = "search_clinics_by_specialty"
    description = ("Find local clinics for a medical specialty from the clinic dataset, "
                   "sorted by shortest wait time. Optionally limit the maximum wait in minutes.")
    args_doc = '{"specialty": "e.g. Orthopedics, Emergency Medicine, Dermatology", "max_wait_time": "int minutes, optional"}'

    def execute(self, specialty="", max_wait_time=None, **_):
        try:
            return format_clinics(search_clinics_by_specialty(specialty, max_wait_time))
        except Exception as e:
            return f"Clinic search failed: {e}"


class ProviderSearch(Tool):
    name = "search_providers"
    description = ("Search doctors and facilities (urgent care, ER, labs) by specialty and location, "
                   "optionally filtered by insurance. Returns ids needed for availability and booking.")
    args_doc = '{"specialty": "e.g. cardiology, urgent care, lab", "location": "city or area, e.g. Boston", "insurance": "optional, e.g. Aetna"}'

    def execute(self, specialty="", location="", insurance=None, **_):
        try:
            return _dump(search_providers(specialty, location, insurance))
        except Exception as e:
            return f"Provider search failed: {e}"


class CheckAvailability(Tool):
    name = "check_availability"
    description = "List open 30-minute appointment slots for a doctor id on a date."
    args_doc = '{"doctor_id": "e.g. DOC001", "date": "YYYY-MM-DD"}'

    def execute(self, doctor_id="", date="", **_):
        try:
            return _dump(check_availability(doctor_id, date))
        except Exception as e:
            return f"Availability check failed: {e}"


class BookAppointment(Tool):
    name = "book_appointment"
    description = "Book an appointment slot for a patient and return a confirmation id."
    args_doc = '{"patient_name": "str", "doctor_id": "e.g. DOC001", "slot": "YYYY-MM-DD HH:MM"}'

    def execute(self, patient_name="", doctor_id="", slot="", **_):
        try:
            return _dump(book_appointment(patient_name, doctor_id, slot))
        except Exception as e:
            return f"Booking failed: {e}"


class TriageGuidelines(Tool):
    name = "triage_guidelines"
    description = ("Look up red-flag triage guidelines (NHS/CDC-style) for described symptoms. "
                   "Use before recommending urgency, and cite the returned source.")
    args_doc = '{"query": "symptom description, e.g. chest pain spreading to arm"}'

    def execute(self, query="", **_):
        try:
            return _dump(retrieve_guidelines(query))
        except Exception as e:
            return f"Guideline lookup failed: {e}"


def healthcare_tools():
    return [ClinicFinder(), ProviderSearch(), CheckAvailability(), BookAppointment(), TriageGuidelines()]