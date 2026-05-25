from datetime import datetime
from zoneinfo import ZoneInfo

from src.core.config import Config
from src.core.gemini_client import GeminiClient
from src.core.json_utils import parse_json_response
from src.agents.location_resolver_agent import LocationResolverAgent
from src.agents.weather_forecast_agent import WeatherForecastAgent
from src.agents.location_context_agent import LocationContextAgent
from src.agents.suitability_scoring_agent import SuitabilityScoringAgent
from src.agents.report_agent import ReportAgent


class CoordinatorAgent:
    """
    Main orchestrator. Extracts the user request with Gemini, then runs
    LocationResolver → WeatherForecast → LocationContext → SuitabilityScoring → ReportAgent
    sequentially and returns the full result dict.
    """

    def __init__(self):
        self.llm_client = GeminiClient()
        self.timezone = Config.DEFAULT_TIMEZONE

        self.location_resolver_agent = LocationResolverAgent()
        self.weather_forecast_agent = WeatherForecastAgent()
        self.location_context_agent = LocationContextAgent()
        self.suitability_scoring_agent = SuitabilityScoringAgent()
        self.report_agent = ReportAgent()

    def handle_user_request(self, user_query: str) -> dict:
        request_data = self._extract_request(user_query)
        return self._handle_specific_flight_check(request_data)

    def _handle_specific_flight_check(self, request_data: dict) -> dict:
        try:
            location_result = self.location_resolver_agent.resolve(
                request_data["location_text"]
            )

        except Exception as error:
            return {
                "stage": "location_not_found",
                "success": False,
                "request": request_data,
                "location": {
                    "query": request_data.get("location_text"),
                    "found": False,
                    "display_name": None,
                    "latitude": None,
                    "longitude": None,
                },
                "weather": None,
                "location_context": None,
                "suitability": None,
                "final_report": (
                    "Location could not be found. Please provide a more specific location."
                ),
                "error": str(error),
            }

        try:
            weather_result = self.weather_forecast_agent.analyze(
                latitude=location_result["latitude"],
                longitude=location_result["longitude"],
                date=request_data["date"],
                time=request_data["time"],
                timezone=request_data["timezone"],
            )

        except Exception as error:
            return {
                "stage": "weather_forecast_failed",
                "success": False,
                "request": request_data,
                "location": location_result,
                "weather": None,
                "location_context": None,
                "suitability": None,
                "final_report": (
                    "Weather forecast could not be retrieved for the selected location and time."
                ),
                "error": str(error),
            }

        try:
            location_context_result = self.location_context_agent.analyze(
                latitude=location_result["latitude"],
                longitude=location_result["longitude"],
                location_name=location_result["display_name"],
            )

        except Exception as error:
            location_context_result = {
                "location_name": location_result["display_name"],
                "radius_m": 500,
                "features": {
                    "source": "fallback",
                    "data_available": False,
                    "warning": "Location context analysis failed. Conservative fallback context was used.",
                    "error": str(error),
                },
                "classification": {
                    "environment_type": "unknown",
                    "near_water": False,
                    "near_park_or_open_land": False,
                    "building_density": "unknown",
                    "road_density": "unknown",
                    "open_area_level": "unknown",
                    "visual_openness": "unknown",
                    "urban_complexity": "unknown",
                    "public_activity_level": "unknown",
                    "wind_exposure": "unknown",
                    "drone_operation_notes": [
                        "Location context could not be analyzed. Assessment is conservative."
                    ],
                    "context_summary": "Location context data could not be retrieved.",
                },
            }

        suitability_result = self.suitability_scoring_agent.analyze(
            weather=weather_result,
            location_context=location_context_result,
            drone_model=request_data["drone_model"],
        )

        final_report = self.report_agent.generate(
            request_data=request_data,
            location=location_result,
            weather=weather_result,
            location_context=location_context_result,
            suitability=suitability_result,
        )

        return {
            "stage": "complete",
            "success": True,
            "request": request_data,
            "location": location_result,
            "weather": weather_result,
            "location_context": location_context_result,
            "suitability": suitability_result,
            "final_report": final_report,
        }

    def _extract_request(self, user_query: str) -> dict:
        now = datetime.now(ZoneInfo(self.timezone))

        prompt = self._build_extraction_prompt(
            user_query=user_query,
            current_datetime=now.isoformat(),
        )

        raw_response = self.llm_client.generate(prompt)
        parsed = parse_json_response(raw_response, source="CoordinatorAgent")
        self._validate_request_data(parsed)

        return parsed

    def _build_extraction_prompt(
        self,
        user_query: str,
        current_datetime: str,
    ) -> str:
        return f"""
You are the CoordinatorAgent of a drone flight suitability system.

Your job is to understand the user request and create a structured workflow input.

Current datetime:
{current_datetime}

Default timezone:
{self.timezone}

User request:
{user_query}

Return ONLY valid JSON. Do not use markdown. Do not add explanations.

Supported MVP intent:
- "specific_flight_check": the user wants to know whether a drone flight is suitable at a specific place and time.

Required JSON schema:
{{
  "intent": "specific_flight_check",
  "location_text": string,
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "timezone": "{self.timezone}",
  "activity": "drone_flight",
  "drone_model": string or null,
  "needs_alternative_times": boolean
}}

Rules:
- Resolve relative dates such as "today" and "tomorrow" using the current datetime.
- Tomorrow means +1 day to today.
- Yesterday means -1 day to today.
- Use 24-hour time format.
- If the user says "noon", convert it to "12:00".
- If the user says "morning" without exact time, choose "09:00".
- If the user says "afternoon" without exact time, choose "15:00".
- If the user says "evening" without exact time, choose "18:00".
- Extract the location as written by the user.
- If the user does not mention a drone model, set "drone_model" to null.
- If the user asks for better times or says "if not suitable", set "needs_alternative_times" to true.
- Otherwise set "needs_alternative_times" to false.
- Do not invent a drone model.
- Do not invent a location.
"""

    def _validate_request_data(self, data: dict) -> None:
        required_fields = [
            "intent",
            "location_text",
            "date",
            "time",
            "timezone",
            "activity",
            "drone_model",
            "needs_alternative_times",
        ]

        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise ValueError(
                f"CoordinatorAgent output is missing fields: {missing_fields}"
            )

        if data["intent"] != "specific_flight_check":
            raise ValueError(f"Unsupported intent for MVP: {data['intent']}")

        if not data["location_text"]:
            raise ValueError("location_text cannot be empty.")

        if data["activity"] != "drone_flight":
            raise ValueError(f"Unsupported activity for MVP: {data['activity']}")
