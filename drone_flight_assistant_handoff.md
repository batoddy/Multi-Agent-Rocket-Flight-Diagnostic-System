# Drone Flight Suitability Assistant — Project Handoff Document

## 1. Project Goal

This project is a Python-based multi-agent software system for evaluating whether a drone flight is suitable at a given location and time.

The system is designed to be:

- working and testable,
- high-quality but simple,
- modular,
- understandable for an academic assignment,
- extendable for future features.

The main idea is not to build a complex GIS or aviation-law platform. The goal is to build a practical AI-assisted decision-support system that uses external tools/APIs during execution.

The system should answer questions like:

```text
Tomorrow at 12:00 I want to fly a drone near Riga National Library. Is it suitable?
```

The system should analyze:

1. user request,
2. target location,
3. target date and time,
4. hourly weather forecast,
5. basic location/environment context,
6. drone flight suitability,
7. final user-facing recommendation.

Later, it can also support:

- alternative time suggestions,
- location recommendations for scenic/historical drone shots,
- optional drone model-specific evaluation,
- basic airspace/restriction awareness.

---

## 2. Current MVP Philosophy

The project should stay simple.

Important design principle:

```text
main.py should only run CoordinatorAgent.
All other agents should be called inside CoordinatorAgent.
```

Correct main flow:

```text
main.py
   ↓
CoordinatorAgent
      ↓
      LocationResolverAgent
      ↓
      WeatherForecastAgent
      ↓
      LocationContextAgent
      ↓
      SuitabilityScoringAgent
      ↓
      ReportAgent
```

The system should not have:

- excessive agent loops,
- unnecessary planner complexity,
- complex microservice architecture,
- full legal authorization automation,
- heavy frontend or map UI in the MVP.

The MVP should be a clean, working Python project.

---

## 3. Current Implemented / Planned MVP Pipeline

Current intended MVP pipeline:

```text
User:
"Tomorrow at 12:00 I want to fly a drone near Riga National Library. Is it suitable?"

main.py
   ↓
CoordinatorAgent
   ↓
Gemini request extraction
   ↓
LocationResolverAgent
   ↓
WeatherForecastAgent
   ↓
LocationContextAgent
   ↓
SuitabilityScoringAgent
   ↓
ReportAgent
   ↓
Final answer
   ↓
outputs/latest_result.json
```

At the current development stage, the system has been built step by step.

The development strategy is:

```text
1. Test Gemini connection.
2. Test CoordinatorAgent JSON extraction.
3. Test GeocodingTool separately.
4. Connect GeocodingTool to LocationResolverAgent.
5. Add LocationResolverAgent to CoordinatorAgent.
6. Test WeatherAPITool separately.
7. Connect WeatherAPITool to WeatherForecastAgent.
8. Add WeatherForecastAgent to CoordinatorAgent.
9. Add LocationContextTool/Agent.
10. Add SuitabilityScoringAgent.
11. Add ReportAgent.
12. Run full pipeline from main.py.
```

The user specifically wants this style of development:

```text
First test each external API or tool alone.
Then connect it to its agent.
Then connect that agent to CoordinatorAgent.
main.py should remain simple and only call CoordinatorAgent.
```

---

## 4. Current Folder Structure

Recommended/current structure:

```text
drone_flight_assistant/
│
├── main.py
├── requirements.txt
├── README.md
├── .env
│
├── outputs/
│   └── latest_result.json
│
├── data/
│   └── drone_profiles.json
│
└── src/
    ├── core/
    │   ├── config.py
    │   └── gemini_client.py
    │
    ├── agents/
    │   ├── coordinator_agent.py
    │   ├── location_resolver_agent.py
    │   ├── weather_forecast_agent.py
    │   ├── location_context_agent.py
    │   ├── suitability_scoring_agent.py
    │   └── report_agent.py
    │
    └── tools/
        ├── geocoding_tool.py
        ├── weather_api_tool.py
        ├── location_context_tool.py
        └── drone_profile_tool.py
```

There is no `TimeParserTool` in the final direction.

Reason:

The project uses an LLM in CoordinatorAgent. Therefore, date/time/location/drone model extraction should be done by CoordinatorAgent using Gemini, not by a separate hardcoded parser.

---

## 5. Dependencies

`requirements.txt` should contain:

```txt
requests
python-dotenv
google-genai
```

Important:

Do not use the old `google.generativeai` package because it is deprecated and shows a warning.

Use the new SDK:

```python
from google import genai
```

---

## 6. Environment File

`.env`:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-1.5-flash
DEFAULT_TIMEZONE=Europe/Riga
```

If the selected Gemini model name causes an error, replace it with a currently available Gemini model.

---

## 7. Core Files

### 7.1 `src/core/config.py`

Purpose:

- Load environment variables.
- Provide global config values.

Expected structure:

```python
import os
from dotenv import load_dotenv


load_dotenv()


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Riga")
```

---

### 7.2 `src/core/gemini_client.py`

Purpose:

- Minimal wrapper around Google Gen AI SDK.
- Used by LLM-based agents.

Expected structure:

```python
from google import genai

from src.core.config import Config


class GeminiClient:
    """
    Minimal Gemini client using the Google Gen AI SDK.
    """

    def __init__(self):
        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing. Please check your .env file.")

        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model_name = Config.GEMINI_MODEL

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        if not response or not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        return response.text.strip()
```

---

## 8. CoordinatorAgent Design

### 8.1 Purpose

CoordinatorAgent is the central orchestrator.

It should not only extract text. It should:

- understand the user query,
- extract structured task information,
- select the correct workflow based on intent,
- call the required agents,
- collect intermediate results,
- return the final result.

For MVP, only one intent is supported:

```text
specific_flight_check
```

Future intents may include:

```text
location_recommendation
alternative_time_check
compare_drone_models
general_drone_safety_question
```

---

### 8.2 Current MVP Behavior

For the query:

```text
Tomorrow at 12:00 I want to fly a drone near Riga National Library. Is it suitable?
```

CoordinatorAgent should produce structured request data:

```json
{
  "intent": "specific_flight_check",
  "location_text": "Riga National Library",
  "date": "YYYY-MM-DD",
  "time": "12:00",
  "timezone": "Europe/Riga",
  "activity": "drone_flight",
  "drone_model": null,
  "needs_alternative_times": false
}
```

If the user says a drone model, for example:

```text
Tomorrow at 12:00 I want to fly DJI Neo near Riga National Library.
```

Then:

```json
"drone_model": "DJI Neo"
```

If no model is mentioned:

```json
"drone_model": null
```

Later, `drone_model: null` means the system will use the default drone profile.

---

### 8.3 CoordinatorAgent Workflow

Current specific flight check workflow:

```text
_handle_specific_flight_check(request_data):
    location_result = LocationResolverAgent.resolve(location_text)
    weather_result = WeatherForecastAgent.analyze(latitude, longitude, date, time, timezone)
    location_context_result = LocationContextAgent.analyze(latitude, longitude, location_name)
    suitability_result = SuitabilityScoringAgent.analyze(weather, location_context, drone_model)
    final_report = ReportAgent.generate(...)
    return all results
```

During development, it is okay if CoordinatorAgent returns partial stages, for example:

```json
{
  "stage": "weather_forecast_retrieved",
  "request": {},
  "location": {},
  "weather": {}
}
```

When the full MVP is done, it should return:

```json
{
  "stage": "final_report_generated",
  "request": {},
  "location": {},
  "weather": {},
  "location_context": {},
  "suitability": {},
  "final_report": "..."
}
```

---

## 9. Geocoding / Location Resolution

### 9.1 `src/tools/geocoding_tool.py`

Purpose:

- Convert text-based location into coordinates.
- Uses OpenStreetMap Nominatim API.

Example input:

```text
Riga National Library
```

Example output:

```json
{
  "query": "Riga National Library",
  "display_name": "Latvijas Nacionālā bibliotēka, ...",
  "latitude": 56.94,
  "longitude": 24.09,
  "raw_type": "library",
  "raw_class": "amenity"
}
```

The tool should use a User-Agent header:

```python
headers = {
    "User-Agent": "DroneFlightSuitabilityAssistant/1.0"
}
```

---

### 9.2 `src/agents/location_resolver_agent.py`

Purpose:

- Wrap GeocodingTool in an agent.
- Return clean location data to CoordinatorAgent.

Expected output:

```json
{
  "query": "Riga National Library",
  "display_name": "...",
  "latitude": 56.94,
  "longitude": 24.09,
  "location_type": "library",
  "location_class": "amenity"
}
```

---

## 10. Weather Forecast

### 10.1 `src/tools/weather_api_tool.py`

Purpose:

- Use Open-Meteo API.
- Fetch hourly forecast for coordinate + date.
- No API key required.

Important:
Use wind speed unit as m/s because drone wind resistance values are usually in m/s.

Request parameters should include:

```python
"wind_speed_unit": "ms"
```

Hourly variables:

```text
temperature_2m
relative_humidity_2m
precipitation_probability
rain
cloud_cover
visibility
wind_speed_10m
wind_gusts_10m
wind_direction_10m
```

---

### 10.2 `src/agents/weather_forecast_agent.py`

Purpose:

- Call WeatherAPITool.
- Select the exact target hour from hourly forecast data.

Example output:

```json
{
  "time": "2026-05-11T12:00",
  "temperature_2m_c": 12.5,
  "relative_humidity_2m_percent": 65,
  "precipitation_probability_percent": 20,
  "rain_mm": 0.0,
  "cloud_cover_percent": 70,
  "visibility_m": 24140,
  "wind_speed_10m_mps": 5.2,
  "wind_gusts_10m_mps": 8.0,
  "wind_direction_10m_deg": 320
}
```

---

## 11. Location Context

### 11.1 Design Decision

The system should collect location context data from APIs/tools, but the interpretation should be done by LLM.

Correct design:

```text
LocationContextTool
   ↓
collects OSM/Overpass feature counts

LocationContextAgent
   ↓
uses Gemini to interpret those counts for drone flight suitability
```

Avoid writing too much rule-based classification manually.

---

### 11.2 `src/tools/location_context_tool.py`

Purpose:

- Use OpenStreetMap Overpass API.
- Count simple map features around the coordinate.
- Radius: currently 500 meters.
- Return summarized feature counts.

Feature groups:

```text
water
park
road
building
amenity
tourism
```

Example output:

```json
{
  "source": "overpass_api",
  "data_available": true,
  "water_count": 3,
  "park_count": 1,
  "road_count": 45,
  "building_count": 62,
  "amenity_count": 18,
  "tourism_count": 4,
  "total_features": 130,
  "sample_features": [
    {
      "name": "Some feature",
      "type": "road"
    }
  ],
  "warning": null
}
```

Important robustness feature:

Overpass API can fail with errors like:

```text
406 Not Acceptable
429 Too Many Requests
504 Gateway Timeout
```

The tool should not crash the full system if Overpass fails.

It should:

1. Try multiple Overpass endpoints.
2. Use headers.
3. Return fallback context if all requests fail.

Recommended endpoints:

```python
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
```

Fallback output:

```json
{
  "source": "fallback",
  "data_available": false,
  "water_count": 0,
  "park_count": 0,
  "road_count": 0,
  "building_count": 0,
  "amenity_count": 0,
  "tourism_count": 0,
  "total_features": 0,
  "sample_features": [],
  "warning": "OpenStreetMap Overpass data could not be retrieved. Location context analysis will be conservative.",
  "error": "..."
}
```

This is important for software quality.

---

### 11.3 `src/agents/location_context_agent.py`

Purpose:

- Call LocationContextTool.
- Send feature summary to Gemini.
- Get structured JSON interpretation.

Expected output:

```json
{
  "location_name": "Latvijas Nacionālā bibliotēka, ...",
  "radius_m": 500,
  "features": {
    "source": "overpass_api",
    "data_available": true,
    "water_count": 3,
    "park_count": 1,
    "road_count": 45,
    "building_count": 62,
    "amenity_count": 18,
    "tourism_count": 4,
    "total_features": 130,
    "sample_features": []
  },
  "classification": {
    "environment_type": "urban_riverside_public_area",
    "near_water": true,
    "near_park": true,
    "building_density": "medium",
    "road_density": "medium",
    "open_area_level": "medium",
    "wind_exposure": "high",
    "public_area_risk": "medium",
    "drone_operation_notes": [
      "The nearby river may increase wind exposure.",
      "The area appears public and urban, so avoid flying over people.",
      "Open green areas nearby may be better for takeoff and landing."
    ]
  }
}
```

Required LLM JSON schema:

```json
{
  "environment_type": "string",
  "near_water": true,
  "near_park": true,
  "building_density": "low | medium | high | unknown",
  "road_density": "low | medium | high | unknown",
  "open_area_level": "low | medium | high | unknown",
  "wind_exposure": "normal | medium | high | unknown",
  "public_area_risk": "low | medium | high | unknown",
  "drone_operation_notes": ["string"]
}
```

Prompt guidance should tell the LLM:

- Use only provided feature summary.
- Do not invent unsupported facts.
- If `data_available` is false, do not pretend map data was available.
- If `data_available` is false, set uncertain fields to `"unknown"` when appropriate.
- Be conservative for drone safety.
- Keep notes practical and short.

---

## 12. Output File Writing

`main.py` should stay simple.

It should:

1. Create CoordinatorAgent.
2. Call `handle_user_request(user_query)`.
3. Save the result to `outputs/latest_result.json`.
4. Print the result to terminal.

Important:

`main.py` should not manually instantiate LocationResolverAgent, WeatherForecastAgent, etc.

---

## 13. Drone Profile Feature

This is optional and should not overcomplicate the MVP.

If the user mentions a drone model, the system should use that model’s profile.

If the user does not mention a drone model, the system should use a default small camera drone profile.

Suggested file:

`data/drone_profiles.json`

Example:

```json
{
  "default": {
    "display_name": "Default Small Camera Drone",
    "takeoff_weight_g": 249,
    "max_wind_resistance_mps": 8.0,
    "camera_equipped": true,
    "rain_tolerance": "not_waterproof",
    "notes": [
      "Generic sub-250g camera drone profile used when the user does not specify a drone model."
    ]
  },
  "dji_neo": {
    "display_name": "DJI Neo",
    "aliases": ["neo", "dji neo"],
    "takeoff_weight_g": 135,
    "max_wind_resistance_mps": 8.0,
    "camera_equipped": true,
    "rain_tolerance": "not_waterproof",
    "notes": [
      "Very lightweight drone; should be evaluated conservatively in windy conditions."
    ]
  },
  "dji_mini_4k": {
    "display_name": "DJI Mini 4K",
    "aliases": ["mini 4k", "dji mini 4k", "mini4k"],
    "takeoff_weight_g": 246,
    "max_wind_resistance_mps": 10.7,
    "camera_equipped": true,
    "rain_tolerance": "not_waterproof",
    "notes": [
      "Sub-250g camera drone with better wind resistance than DJI Neo."
    ]
  },
  "dji_avata_2": {
    "display_name": "DJI Avata 2",
    "aliases": ["avata", "avata 2", "dji avata", "dji avata 2"],
    "takeoff_weight_g": 377,
    "max_wind_resistance_mps": 10.7,
    "camera_equipped": true,
    "rain_tolerance": "not_waterproof",
    "notes": [
      "FPV drone above 250g; may require stricter regulatory consideration."
    ]
  }
}
```

This feature should be used later by SuitabilityScoringAgent.

---

## 14. SuitabilityScoringAgent — Planned Next Step

This is the next major piece to implement.

Inputs:

```python
weather: dict
location_context: dict
drone_model: str | None
```

It should also load a drone profile through DroneProfileTool.

If `drone_model` is null:

```text
use default drone profile
```

Important weather fields:

```text
wind_speed_10m_mps
wind_gusts_10m_mps
precipitation_probability_percent
rain_mm
visibility_m
temperature_2m_c
```

Important location context fields:

```text
classification.wind_exposure
classification.public_area_risk
classification.open_area_level
classification.drone_operation_notes
```

Suggested scoring logic:

```text
Start score = 100

Wind:
- Compare wind_speed_10m_mps with drone max_wind_resistance_mps.
- Compare wind_gusts_10m_mps with drone max_wind_resistance_mps.
- Gusts should be treated more strictly than average wind.

Rain:
- If rain_mm > 0 and drone is not waterproof, subtract strongly.
- If precipitation probability is high, subtract.

Visibility:
- If visibility is low, subtract.

Location:
- If wind_exposure is high, subtract.
- If public_area_risk is medium/high, subtract.
- If open_area_level is high, slightly positive or less negative.
```

Suggested decision classes:

```text
80–100: Suitable
60–79: Suitable with caution
40–59: Not ideal
0–39: Not recommended
```

Expected output:

```json
{
  "score": 68,
  "decision": "Suitable with caution",
  "risk_level": "medium",
  "drone_profile": {
    "display_name": "Default Small Camera Drone",
    "max_wind_resistance_mps": 8.0
  },
  "reasons": [
    "Wind gusts are close to the drone wind resistance limit.",
    "The location may have high wind exposure.",
    "No significant rain is expected."
  ]
}
```

The first implementation can be rule-based. No need to use LLM for scoring.

---

## 15. ReportAgent — Planned Step After Scoring

ReportAgent should generate a final user-facing answer.

It can be template-based at first.

It should include:

1. Overall decision.
2. Score.
3. Location summary.
4. Weather summary.
5. Location context summary.
6. Drone-specific notes if any.
7. Safety/regulatory disclaimer.

Example:

```text
Flight suitability: Suitable with caution
Score: 68/100

Location:
Riga National Library area, Riga, Latvia.

Weather at 12:00:
- Temperature: 12.5°C
- Wind speed: 5.2 m/s
- Wind gusts: 8.0 m/s
- Rain probability: 20%

Location context:
The area appears to be an urban riverside/public area. Wind exposure may be higher near water, and pedestrian activity should be considered.

Decision reason:
The weather is generally acceptable, but wind gusts are close to the default drone profile's safe wind limit. Extra caution is recommended.

Regulatory note:
This system does not provide legal flight permission. The pilot must check official UAS geographical zones and local restrictions before flying.
```

Important safety wording:

```text
The system does not provide legal flight authorization.
It only provides preliminary decision support.
The pilot is responsible for checking official UAS geographical zones and obtaining required permissions.
```

---

## 16. Future Features

After MVP, planned features include:

### 16.1 Alternative Time Recommendation

If requested time is not suitable, suggest better time windows on the same day.

Workflow:

```text
CoordinatorAgent
   ↓
WeatherForecastAgent gets all hourly data for the day
   ↓
SuitabilityScoringAgent scores candidate hours
   ↓
AlternativeTimeAgent ranks best 2–3 hours
   ↓
ReportAgent explains alternatives
```

Candidate hours can initially be simple:

```text
08:00–20:00
```

---

### 16.2 Location Recommendation

Example request:

```text
I am in Riga today and want to shoot scenic/historical drone footage. Where can I fly?
```

Future workflow:

```text
CoordinatorAgent detects location_recommendation intent
   ↓
CandidateLocationAgent provides predefined Riga candidate spots
   ↓
For each candidate:
    WeatherForecastAgent
    LocationContextAgent
    SuitabilityScoringAgent
   ↓
Rank candidates
   ↓
ReportAgent returns best options
```

Initial candidate locations can be stored manually in a JSON file.

Possible candidate types:

```text
open parks
riverside areas
less dense scenic areas
city skyline viewpoints
```

Avoid overcomplicating this with automatic GIS search in the first version.

---

### 16.3 Airspace / Restriction Awareness

This should be implemented carefully.

The system should not claim to provide legal permission.

Possible MVP-level behavior:

```text
AirspaceRestrictionAgent gives a warning:
- official UAS geographical zones must be checked,
- pilot must verify airspace restrictions,
- authorization may be required.
```

More advanced future behavior:

- integrate official datasets if accessible,
- check whether coordinate falls inside a restricted polygon,
- classify result as:
  - clear,
  - caution,
  - authorization required,
  - manual verification required.

But for now, do not make the legal/regulatory part too complex.

---

### 16.4 Drone Model-Specific Suitability

Optional feature.

If user says:

```text
Can I fly DJI Neo near Riga National Library tomorrow at 12?
```

Then use DJI Neo profile.

If user says:

```text
Can I fly near Riga National Library tomorrow at 12?
```

Then use default drone.

Drone model matters for:

```text
max wind resistance
weight
camera equipped or not
rain tolerance
regulatory note
```

This is useful but should remain a secondary feature.

---

## 17. Important Development Rules

Follow these rules while continuing the project:

### Rule 1 — main.py stays simple

```text
main.py only creates CoordinatorAgent and calls handle_user_request().
```

### Rule 2 — CoordinatorAgent orchestrates everything

```text
All agents are called inside CoordinatorAgent.
```

### Rule 3 — Test tools before integration

Before adding a tool/agent to CoordinatorAgent:

```text
1. Test tool alone.
2. Test agent alone.
3. Then integrate into CoordinatorAgent.
```

### Rule 4 — External API failures should not crash the whole system when possible

For example:

```text
If Overpass API fails, use fallback context.
If weather API fails, that is more critical and may stop the analysis.
```

### Rule 5 — Keep LLM output structured

Whenever Gemini is used for extraction or classification:

```text
Ask for ONLY valid JSON.
Parse the JSON.
Validate required fields.
Fail clearly if invalid.
```

### Rule 6 — Do not over-engineer

The target is:

```text
working + high-quality + simple
```

Not:

```text
complex + over-architected + fragile
```

---

## 18. Current Debug Notes

A previous warning appeared:

```text
All support for the google.generativeai package has ended.
```

Solution:

Use:

```text
google-genai
```

and import:

```python
from google import genai
```

A previous error appeared:

```text
RuntimeError: Overpass API request failed. Status code: 406
```

Solution:

Update LocationContextTool to:

- use headers,
- try multiple Overpass endpoints,
- return fallback context instead of crashing.

---

## 19. Immediate Next Step

The next recommended implementation step is:

```text
Implement DroneProfileTool and SuitabilityScoringAgent.
```

Suggested order:

```text
1. Create/verify data/drone_profiles.json.
2. Implement src/tools/drone_profile_tool.py.
3. Test DroneProfileTool alone.
4. Implement src/agents/suitability_scoring_agent.py.
5. Test SuitabilityScoringAgent with sample weather + sample location context.
6. Add SuitabilityScoringAgent to CoordinatorAgent.
7. Run main.py.
8. Save updated output to outputs/latest_result.json.
```

After that:

```text
Implement ReportAgent.
```

Then the MVP will be mostly complete.

---

## 20. One-Sentence Summary

This is a simple but modular multi-agent Python system where CoordinatorAgent uses Gemini to understand a drone flight request, then orchestrates location resolution, weather forecast retrieval, LLM-assisted location context interpretation, drone-aware suitability scoring, and final report generation, while keeping main.py minimal and saving results to a JSON output file.
