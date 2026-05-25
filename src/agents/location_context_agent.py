import json

from src.core.gemini_client import GeminiClient
from src.core.json_utils import parse_json_response
from src.tools.location_context_tool import LocationContextTool


class LocationContextAgent:
    """
    Analyzes the environmental context of a coordinate.

    The tool collects OpenStreetMap feature counts.
    The LLM interprets those features as broad location context.

    Important design choice:
    This agent does not perform exact obstacle mapping.
    It does not generate detailed drone operation warnings.
    It only describes the general environmental context.
    """

    def __init__(self):
        self.location_context_tool = LocationContextTool()
        self.llm_client = GeminiClient()

    def analyze(
        self,
        latitude: float,
        longitude: float,
        location_name: str,
    ) -> dict:
        radius_m = 500
        features = self.location_context_tool.get_context_features(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
        )
        prompt = self._build_prompt(latitude, longitude, location_name, radius_m, features)
        parsed = parse_json_response(self.llm_client.generate(prompt), source="LocationContextAgent")
        self._validate_interpretation(parsed)
        return {
            "location_name": location_name,
            "radius_m": radius_m,
            "features": features,
            "classification": parsed,
        }

    def _build_prompt(
        self,
        latitude: float,
        longitude: float,
        location_name: str,
        radius_m: int,
        features: dict,
    ) -> str:
        return f"""
You are the LocationContextAgent of a drone flight suitability system.

Your task is to interpret OpenStreetMap feature counts around a coordinate.

This is NOT exact obstacle mapping.
This is NOT legal authorization.
This is NOT a final flight safety report.

Your goal is only to summarize the broad environmental context:
- Is the area urban, riverside, park-like, open, mixed, etc.?
- Are there water, park/open land, roads, buildings, amenities, or tourism signals?
- Is the surrounding context generally simple, moderate, or complex?

Location:
{location_name}

Coordinates:
latitude={latitude}
longitude={longitude}

Search radius:
{radius_m} meters

OpenStreetMap feature summary:
{json.dumps(features, ensure_ascii=False, indent=2)}

Return ONLY valid JSON.
Do not use markdown.
Do not add explanations outside JSON.

Required JSON schema:
{{
  "environment_type": "string",
  "near_water": true,
  "near_park_or_open_land": true,
  "building_density": "low | medium | high | unknown",
  "road_density": "low | medium | high | unknown",
  "open_area_level": "low | medium | high | unknown",
  "visual_openness": "low | medium | high | unknown",
  "urban_complexity": "low | medium | high | unknown",
  "public_activity_level": "low | medium | high | unknown",
  "wind_exposure": "normal | medium | high | unknown",
  "drone_operation_notes": ["string"],
  "context_summary": "string"
}}

Important rules:
- Use only the provided feature summary.
- Do not invent exact facts that are not supported by the data.
- Do not provide legal or regulatory warnings.
- Do not mention individual sample feature names such as cafes, ATMs, hotels, restaurants, or parking areas.
- sample_features are only examples from OpenStreetMap. Do not base the main classification mainly on sample_features.
- Focus on general location context, not detailed flight advice.
- drone_operation_notes must be a JSON array of short strings (1-2 per location, max 3). Each note must describe one factual environmental observation relevant to drone operations (e.g. "Area is adjacent to a river, increasing wind exposure and crash recovery difficulty."). Do not give regulatory or legal advice in these notes.

If data_available is false:
- Do not pretend that map data was available.
- Set uncertain fields to "unknown" when appropriate.
- context_summary should simply say that map context data could not be retrieved.

Density calibration for a 500 meter radius:
- Do not classify building_density as "high" too easily.
- building_count below 100 should usually be low or medium.
- building_count between 100 and 250 should usually be medium unless the context clearly indicates a very dense urban area.
- building_count above 250 may be high.
- Do not use building_count alone. Consider water_count, park_count, open_land_count, and context_hints together.

Road density calibration:
- OpenStreetMap road_count may include many small road segments.
- Do not classify road_density as "high" too easily only because road_count is numerically large.
- road_count below 200 should usually be low or medium.
- road_count between 200 and 700 should usually be medium unless the context clearly indicates a complex road network.
- road_count above 700 may be high.

Open area and visual openness:
- Do not classify visual_openness or open_area_level as "low" only because building_count is high.
- If water_count is greater than 0, near_water should usually be true.
- If park_count or open_land_count is greater than 0, near_park_or_open_land should usually be true.
- If water, park, grassland, garden, or open land signals exist, visual_openness may be medium even if the wider area is urban.
- A riverside city area may have medium visual openness even with medium urban complexity.

Urban complexity:
- Building, road, amenity, and tourism counts can increase urban_complexity.
- Urban complexity should describe how busy or developed the surrounding context appears.
- Urban complexity should not automatically mean the location is unsuitable.

Wind exposure:
- Water or riverside signals may increase wind_exposure.
- If there is no water or open land signal, wind_exposure can remain normal or unknown.

context_summary style:
- Write only one short sentence.
- Keep it neutral and descriptive.
- Do not give instructions.
- Do not use alarmist language.
- Example style:
  "The area appears to be a mixed urban riverside environment with some open-space signals."
"""

    def _validate_interpretation(self, data: dict) -> None:
        required_fields = [
            "environment_type", "near_water", "near_park_or_open_land",
            "building_density", "road_density", "open_area_level",
            "visual_openness", "urban_complexity", "public_activity_level",
            "wind_exposure", "drone_operation_notes", "context_summary",
        ]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"LocationContextAgent output is missing fields: {missing}")

        density_fields = [
            "building_density", "road_density", "open_area_level",
            "visual_openness", "urban_complexity", "public_activity_level",
        ]
        density_values = {"low", "medium", "high", "unknown"}
        for field in density_fields:
            if data[field] not in density_values:
                raise ValueError(f"Invalid {field}: {data[field]}")

        if data["wind_exposure"] not in {"normal", "medium", "high", "unknown"}:
            raise ValueError(f"Invalid wind_exposure: {data['wind_exposure']}")

        for field in ("environment_type", "context_summary"):
            if not isinstance(data[field], str):
                raise ValueError(f"{field} must be a string.")

        for field in ("near_water", "near_park_or_open_land"):
            if not isinstance(data[field], bool):
                raise ValueError(f"{field} must be a boolean.")

        if not isinstance(data["drone_operation_notes"], list):
            raise ValueError("drone_operation_notes must be a list.")
