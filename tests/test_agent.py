"""Offline unit tests for MediPilot Multi-Agent Graph (No API key needed).
Run: python -m unittest discover tests
"""
import unittest
from agent.state import AgentState
from agent.nodes import _check_allergy_contraindications, _parse_json
from agent.graph import route_after_triage


class TestMediPilotAgent(unittest.TestCase):

    def test_json_parser_robustness(self):
        """Verify markdown code fences and noisy responses are parsed cleanly."""
        text = "Here is the assessment: ```json\n{\"urgency_level\": \"Routine\", \"esi_level\": 4}\n```"
        parsed = _parse_json(text)
        self.assertEqual(parsed.get("urgency_level"), "Routine")
        self.assertEqual(parsed.get("esi_level"), 4)

    def test_emergency_halt_routing(self):
        """Verify conditional edge halts workflow immediately on ESI 1 or Emergency."""
        emergency_state: AgentState = {
            "messages": [],
            "patient_profile": {},
            "extracted_symptoms": ["chest pain"],
            "urgency_level": "Emergency",
            "esi_level": 2,
            "triage_reason": "High risk",
            "is_emergency": True,
            "clinical_warnings": [],
            "recommended_specialty": [],
            "navigation_advice": "",
            "tool_results": {},
            "care_summary": {}
        }
        destination = route_after_triage(emergency_state)
        self.assertEqual(destination, "emergency_halt")

    def test_routine_navigation_routing(self):
        """Verify routine complaints route to navigation node."""
        routine_state: AgentState = {
            "messages": [],
            "patient_profile": {},
            "extracted_symptoms": ["knee swelling"],
            "urgency_level": "Routine",
            "esi_level": 4,
            "triage_reason": "Stable",
            "is_emergency": False,
            "clinical_warnings": [],
            "recommended_specialty": [],
            "navigation_advice": "",
            "tool_results": {},
            "care_summary": {}
        }
        destination = route_after_triage(routine_state)
        self.assertEqual(destination, "navigation")

    def test_allergy_contraindication_check(self):
        """Verify automated drug safety warnings trigger on allergy conflicts."""
        profile = {"allergies": ["Ibuprofen / NSAIDs"]}
        complaint = "Severe knee joint pain and swelling"
        warnings = _check_allergy_contraindications(profile, complaint)
        self.assertTrue(len(warnings) > 0)
        self.assertIn("CONTRAINDICATION", warnings[0])


if __name__ == "__main__":
    unittest.main()