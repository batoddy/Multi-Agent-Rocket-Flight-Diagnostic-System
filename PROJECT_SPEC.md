# Drone Flight Suitability Assistant — Project Specification

## 1. Project Goal

A Python-based multi-agent system that evaluates whether a drone flight is suitable at a given location and time. The user interacts through a conversational terminal interface in natural language (Turkish or English). The system resolves the request, fetches real external data, scores flight conditions with deterministic rules, and produces a human-readable report written by an LLM.

The system answers questions like:

```
Tomorrow at 12:00 I want to fly a drone near Riga National Library. Is it suitable?
```

If the request is missing a location or time, the assistant asks a clarifying question before proceeding.

---

## 2. Architecture

`main.py` runs a simple input loop and delegates everything to `ChatAgent`.

### Full call chain

```
main.py (input loop)
  └── ChatAgent
        ├── _classify_message()       Gemini: NOT_FLIGHT | COMPLETE | ASK_TIME | ASK_LOCATION
        ├── _ask_clarification()      Gemini: asks for missing time or location
        ├── _enrich_with_history()    Gemini: expand follow-up into full standalone query
        ├── _handle_general_chat()    Gemini: direct conversational response
        └── CoordinatorAgent
              ├── _extract_request()        Gemini: NL query → structured JSON
              ├── LocationResolverAgent     OSM Nominatim → lat/lon
              ├── WeatherForecastAgent      Open-Meteo → hourly weather slice
              ├── LocationContextAgent      Overpass API + Gemini → env classification
              ├── SuitabilityScoringAgent   Rule-based → structured evaluations
              └── ReportAgent               Gemini: writes [2] and [3] of report
```

### Which agents use Gemini

| Agent                     | Gemini | Purpose                                                |
| ------------------------- | ------ | ------------------------------------------------------ |
| `ChatAgent`               | ✅ ×3  | Query classification, history enrichment, general chat |
| `CoordinatorAgent`        | ✅ ×1  | NL → structured JSON extraction                        |
| `LocationContextAgent`    | ✅ ×1  | OSM feature counts → environment classification        |
| `ReportAgent`             | ✅ ×1  | Writes Final Verdict + Detailed Analysis sections      |
| `LocationResolverAgent`   | ❌     | Nominatim API wrapper only                             |
| `WeatherForecastAgent`    | ❌     | Open-Meteo API wrapper only                            |
| `SuitabilityScoringAgent` | ❌     | Deterministic rule-based scoring — no LLM by design    |

---

## 3. Folder Structure

```
project/
│
├── main.py
├── requirements.txt
├── .env
├── CLAUDE.md
├── ARCHITECTURE.md
├── PROJECT_SPEC.md
│
├── outputs/
│   └── latest_result.json
│
├── data/
│   └── drone_profiles.json
│
├── test/
│   ├── test_scoring_agent.py
│   ├── test_drone_profile.py
│   ├── test_geocoding.py
│   └── test_location_resolver.py
│
└── src/
    ├── core/
    │   ├── config.py
    │   ├── gemini_client.py
    │   └── json_utils.py
    │
    ├── agents/
    │   ├── chat_agent.py
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

---

## 4. Dependencies and Environment

### requirements.txt

```
requests
python-dotenv
google-genai
```

Do not use the deprecated `google.generativeai`. Use:

```python
from google import genai
```

### .env

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite-preview
DEFAULT_TIMEZONE=Europe/Riga
```

---

## 5. Core Utilities

### src/core/config.py

Loads `.env` into a `Config` class with `GEMINI_API_KEY`, `GEMINI_MODEL`, `DEFAULT_TIMEZONE`.

### src/core/gemini_client.py

Minimal wrapper around `google-genai` SDK. `generate(prompt: str) -> str`. Raises on empty response.

### src/core/json_utils.py

Shared JSON parsing utility used by any agent that receives LLM output:

````python
def parse_json_response(raw_response: str, source: str = "LLM") -> dict:
    cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(f"{source} returned invalid JSON:\n{raw_response}") from error
````

---

## 6. ChatAgent

Entry point for all user interaction. Maintains `self.history` (list of `{role, content}` dicts) across the session.

### Session memory behavior

- Last 10 messages are included as context in Gemini prompts.
- Assistant messages longer than 600 chars are truncated to avoid token bloat.
- History persists for the session only — no disk persistence.

### Classification

A single Gemini call classifies each message:

| Label          | Meaning                                                               |
| -------------- | --------------------------------------------------------------------- |
| `NOT_FLIGHT`   | General question, greeting, thanks — not a flight suitability request |
| `COMPLETE`     | Flight request with both location and time (from message or history)  |
| `ASK_TIME`     | Flight request with location but no time mentioned anywhere           |
| `ASK_LOCATION` | Flight request but no location mentioned anywhere                     |

Falls back to `COMPLETE` if the LLM returns an unexpected label.

### Clarification

If `ASK_TIME` or `ASK_LOCATION`, ChatAgent generates a short natural-language question in the user's language (Turkish or English) rather than routing to CoordinatorAgent.

### Follow-up enrichment

Before routing to CoordinatorAgent, `_enrich_with_history()` expands short follow-ups ("what about 3pm?") into a complete standalone query using the session history.

### Error mapping

`_format_error_response(result)` maps pipeline failure stages to user-friendly messages:

| Stage                     | User message                                                  |
| ------------------------- | ------------------------------------------------------------- |
| `location_not_found`      | Location could not be found — ask for a more specific address |
| `weather_forecast_failed` | Weather data unavailable — try again later                    |
| other                     | Generic error with stage name                                 |

---

## 7. CoordinatorAgent

Orchestrates the full pipeline. All sub-agents are initialized as instance variables on startup.

### \_extract_request output

```json
{
  "intent": "specific_flight_check",
  "location_text": "RTU, Riga Latvia",
  "date": "2026-05-16",
  "time": "12:00",
  "timezone": "Europe/Riga",
  "activity": "drone_flight",
  "drone_model": null,
  "needs_alternative_times": false
}
```

### Error handling

- Location failure → abort, return `stage: "location_not_found"`, `success: false`
- Weather failure → abort, return `stage: "weather_forecast_failed"`, `success: false`
- Location context failure → falls back to conservative "unknown" classification, pipeline continues
- Suitability and Report always run if weather succeeded

### Final return dict keys

`stage`, `success`, `request`, `location`, `weather`, `location_context`, `suitability`, `final_report`

---

## 8. LocationResolverAgent

Wraps `GeocodingTool` (OSM Nominatim). Requires `User-Agent` header. Raises on failure — CoordinatorAgent catches and aborts.

**Output:**

```json
{
  "query": "...",
  "display_name": "...",
  "latitude": 56.95,
  "longitude": 24.1,
  "location_type": "university",
  "location_class": "amenity"
}
```

---

## 9. WeatherForecastAgent

Wraps `WeatherAPITool` (Open-Meteo, no API key). Fetches the full day's hourly forecast, then slices the exact target hour.

Wind unit is always `ms` (m/s) — matches drone profile `max_wind_resistance_mps`.

**Output (one hour slice):**

```json
{
  "time": "2026-05-16T12:00",
  "temperature_2m_c": 12.5,
  "relative_humidity_2m_percent": 65,
  "precipitation_probability_percent": 20,
  "rain_mm": 0.0,
  "cloud_cover_percent": 70,
  "visibility_m": 20000,
  "wind_speed_10m_mps": 5.2,
  "wind_gusts_10m_mps": 8.0,
  "wind_direction_10m_deg": 320
}
```

---

## 10. LocationContextAgent

Two-step: `LocationContextTool` counts OSM features within 500m via Overpass API, then Gemini interprets the counts.

`LocationContextTool` tries two Overpass endpoints and returns a safe fallback dict on failure — it never raises.

### Gemini output schema (classification)

```json
{
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
}
```

`wind_exposure` allowed values: `normal`, `medium`, `high`, `unknown`.
All density/level fields: `low`, `medium`, `high`, `unknown`.

`public_activity_level` is **informational only** — it is shown in the report but causes no score deduction.

---

## 11. SuitabilityScoringAgent

**No LLM.** Fully deterministic. Same inputs always produce the same output.

Score starts at 100. Five evaluation categories, each produces one `{parameter, status, detail}` dict.

### Scoring deductions

| Category             | Max deduction                              | CRITICAL threshold               |
| -------------------- | ------------------------------------------ | -------------------------------- |
| Wind Stability       | −45 (avg) + −40 (gusts)                    | avg or gusts exceed drone limit  |
| Precipitation Risk   | −35 rain + −25 probability                 | rain > 0 on non-waterproof drone |
| Visual Line of Sight | −35                                        | visibility < 1000 m              |
| Battery Temperature  | −25                                        | temperature < −10°C              |
| Environmental Hazard | −10 wind / −5 moderate wind / +5 open area | n/a                              |

Wind deductions scale proportionally to ratio vs. `max_wind_resistance_mps`.

Temperature thresholds: < −10°C → CRITICAL (−25), < 0°C → WARNING (−15), < 5°C → WARNING (−8), > 40°C → WARNING (−10).

`public_activity_level` is informational only — it appears in the `Environmental Hazard` detail text but never causes score deduction.

### Decision thresholds

| Score | Decision                     | Risk Level |
| ----- | ---------------------------- | ---------- |
| ≥ 80  | Suitable                     | Low        |
| ≥ 60  | Suitable with strict caution | Medium     |
| ≥ 40  | Not ideal                    | High       |
| < 40  | Not recommended              | Very High  |

### Output

```json
{
  "score": 65,
  "decision": "Suitable with strict caution",
  "risk_level": "Medium",
  "drone_profile": {
    "display_name": "DJI Mini 4K",
    "max_wind_resistance_mps": 10.7
  },
  "evaluations": [
    {
      "parameter": "Wind Stability",
      "status": "WARNING",
      "detail": "..."
    },
    {
      "parameter": "Precipitation Risk",
      "status": "OK",
      "detail": "..."
    },
    {
      "parameter": "Visual Line of Sight",
      "status": "OK",
      "detail": "..."
    },
    {
      "parameter": "Battery Temperature",
      "status": "OK",
      "detail": "..."
    },
    {
      "parameter": "Environmental Hazard",
      "status": "WARNING",
      "detail": "..."
    }
  ],
  "warnings": []
}
```

Drone profile fallback: if no model specified or model not found → `dji_mini_4k` (a warning is added to `warnings`).

---

## 12. ReportAgent

Produces the final user-facing text. Two parts:

**[1] FLIGHT OVERVIEW** — fixed-formatted, no LLM:

```
SYSTEM REPORT: DRONE FLIGHT SUITABILITY ANALYSIS

[1] FLIGHT OVERVIEW
--------------------------------------------------
Target Location : ...
Target Time     : ... (timezone)
Drone Profile   : ...
Max Wind Resist.: ... m/s
```

**[2] FINAL VERDICT + [3] DETAILED ANALYSIS** — written by Gemini.

Gemini receives: weather values, drone profile, location classification, suitability evaluations, warnings.

Report tone: direct and factual, written for amateur-to-professional drone pilots. Uses actual numbers (m/s, %, °C) with contextual interpretation. Comments on both positive and negative conditions. Does not over-explain drone basics. No regulatory disclaimer.

```
[2] FINAL VERDICT
--------------------------------------------------
2-3 sentences. Bottom-line judgment and key driving factor(s). No numeric score.

[3] DETAILED ANALYSIS
--------------------------------------------------
* WIND STABILITY
* PRECIPITATION RISK
* VISUAL LINE OF SIGHT
* BATTERY TEMPERATURE
* ENVIRONMENTAL HAZARD
```

---

## 13. Drone Profiles

`data/drone_profiles.json` must contain `"dji_mini_4k"` key (mandatory fallback).

Each profile fields: `display_name`, `max_wind_resistance_mps`, `rain_tolerance`, `takeoff_weight_g`, `camera_equipped`, `notes`, `aliases`.

Current profiles: `dji_mini_4k`, `dji_neo`, `dji_mini_3_pro`, `dji_air_3`, `dji_avata_2`.

`DroneProfileTool` raises `FileNotFoundError` on startup if the file is missing, and `ValueError` if `dji_mini_4k` key is absent.

---

## 14. External APIs

| API           | Tool                  | Auth                       | Failure behavior                                         |
| ------------- | --------------------- | -------------------------- | -------------------------------------------------------- |
| Google Gemini | `GeminiClient`        | `GEMINI_API_KEY`           | raises — pipeline aborts                                 |
| OSM Nominatim | `GeocodingTool`       | none (User-Agent required) | raises — CoordinatorAgent catches, returns error stage   |
| Open-Meteo    | `WeatherAPITool`      | none                       | raises — CoordinatorAgent catches, returns error stage   |
| OSM Overpass  | `LocationContextTool` | none                       | returns fallback dict — never raises, pipeline continues |

---

## 15. Design Principles

- **Agents orchestrate, tools only do I/O.** Tools make HTTP calls and return raw data. Agents apply logic, call Gemini, and decide what to do with the data.
- **SuitabilityScoringAgent has no LLM by design.** Scoring must be deterministic and auditable. LLM is used only for interpretation and presentation.
- **LocationContext failure is non-fatal.** If Overpass or Gemini fails, the pipeline continues with a conservative "unknown" classification.
- **ChatAgent enriches short follow-ups before routing.** CoordinatorAgent always receives a self-contained natural language request.
- **All LLM outputs are validated before use.** Both CoordinatorAgent and LocationContextAgent validate required fields and allowed enum values. `parse_json_response()` raises a clear error on invalid JSON.
- **public_activity_level is informational only.** It describes the busyness of the area for context but never subtracts from the score — the pilot is responsible for regulatory decisions.

---

## 16. Running the Project

```bash
# Activate environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the assistant
python main.py

# Run individual test scripts
python test/test_scoring_agent.py
python test/test_drone_profile.py
python test/test_geocoding.py
python test/test_location_resolver.py
```

Exit the chat with: `exit`, `quit`, `bye`, `çıkış`, or `cikis`.

---

## 17. Future Features

- **Alternative time recommendation** — if the requested time is unsuitable, suggest better windows on the same day.
- **Location recommendation** — given a city, suggest drone-friendly scenic spots.
- **Airspace / restriction awareness** — integrate official UAS zone datasets for advisory-level restriction checks.
