# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python multi-agent system that evaluates drone flight suitability at a given location and time. The user interacts via a conversational terminal interface — asking natural-language questions and receiving a structured, LLM-written analysis report.

## Commands

```bash
# Run the assistant (conversational loop)
python main.py

# Run a specific test script (not pytest — scripts use if __name__ == "__main__")
python test/test_scoring_agent.py
python test/test_drone_profile.py
python test/test_geocoding.py
python test/test_location_resolver.py

# Install dependencies
.venv\Scripts\activate
pip install -r requirements.txt
```

## Architecture

`main.py` runs a simple input loop and delegates everything to `ChatAgent`.

**Full call chain:**

```
main.py (input loop)
  └── ChatAgent
        ├── _is_flight_query()        # Gemini: yes/no classification
        ├── _enrich_with_history()    # Gemini: expand follow-up into full query
        ├── _handle_general_chat()    # Gemini: direct conversational response
        └── CoordinatorAgent
              ├── _extract_request()        # Gemini: NL query → structured JSON
              ├── LocationResolverAgent     # OSM Nominatim → lat/lon
              ├── WeatherForecastAgent      # Open-Meteo → hourly weather slice
              ├── LocationContextAgent      # Overpass API + Gemini → env classification
              ├── SuitabilityScoringAgent   # Rule-based → structured evaluations
              └── ReportAgent               # Gemini: writes [2] and [3] of report
```

**Which agents use Gemini:**

| Agent                     | Gemini | Purpose                                                |
| ------------------------- | ------ | ------------------------------------------------------ |
| `ChatAgent`               | ✅ ×3  | Query classification, history enrichment, general chat |
| `CoordinatorAgent`        | ✅ ×1  | NL → structured JSON extraction                        |
| `LocationContextAgent`    | ✅ ×1  | OSM feature counts → environment classification        |
| `ReportAgent`             | ✅ ×1  | Writes Final Verdict + Detailed Analysis sections      |
| `LocationResolverAgent`   | ❌     | Nominatim API wrapper                                  |
| `WeatherForecastAgent`    | ❌     | Open-Meteo API wrapper                                 |
| `SuitabilityScoringAgent` | ❌     | Deterministic rule-based scoring                       |

## Report Format

`ReportAgent` produces a 3-section report:

- **[1] FLIGHT OVERVIEW** — fixed-formatted facts (location, time, drone profile). No LLM.
- **[2] FINAL VERDICT** — Gemini-written, 2-3 sentences, bottom-line judgment.
- **[3] DETAILED ANALYSIS** — Gemini-written per parameter: Wind Stability, Precipitation Risk, Visual Line of Sight, Battery Temperature, Environmental Hazard.

Report tone: written for amateur-to-professional pilots. No over-explaining of basics. Both positive and negative conditions are called out. Actual numbers (m/s, %, °C) are used with contextual interpretation. No regulatory disclaimer (removed by design).

## Scoring Logic

Score starts at 100. `SuitabilityScoringAgent` is fully rule-based — no LLM.

Output key: `evaluations` — a list of `{parameter, status, detail}` dicts (one per category). Statuses: `OK`, `WARNING`, `CRITICAL`.

Deductions per category:

- **Wind**: up to −45 (avg) + −40 (gusts) based on ratio to `max_wind_resistance_mps`
- **Rain**: −35 if rain > 0 and `not_waterproof`; additional −25 if probability ≥ 70%
- **Visibility**: −35 if < 1000 m, −20 if < 3000 m, −10 if < 5000 m
- **Temperature**: −25 if < −10°C, −15 if < 0°C, −8 if < 5°C, −10 if > 40°C
- **Location context**: −10 for high wind exposure, −5 moderate; +5 bonus for high open area level. Public activity level is informational only — no score deduction.

Decision thresholds: ≥80 → Suitable, ≥60 → Suitable with strict caution, ≥40 → Not ideal, <40 → Not recommended. Risk levels: Low / Medium / High / Very High.

## LocationContextAgent Schema

Fields returned in `classification`:
`environment_type`, `near_water`, `near_park_or_open_land`, `building_density`, `road_density`, `open_area_level`, `visual_openness`, `urban_complexity`, `public_activity_level`, `wind_exposure`, `drone_operation_notes` (list), `context_summary`.

`wind_exposure` allowed values: `"normal"`, `"medium"`, `"high"`, `"unknown"`.
All density/level fields: `"low"`, `"medium"`, `"high"`, `"unknown"`.

## External APIs

| API           | Tool                  | Notes                                                                                     |
| ------------- | --------------------- | ----------------------------------------------------------------------------------------- |
| Google Gemini | `GeminiClient`        | `GEMINI_API_KEY` required. Use `google-genai` SDK — not deprecated `google.generativeai`. |
| OSM Nominatim | `GeocodingTool`       | Free, requires `User-Agent` header.                                                       |
| Open-Meteo    | `WeatherAPITool`      | Free, no key. Wind unit must be `ms` (m/s).                                               |
| OSM Overpass  | `LocationContextTool` | Two fallback endpoints. Never raises — returns safe fallback dict on failure.             |

## Environment

`.env` must contain:

```
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite-preview
DEFAULT_TIMEZONE=Europe/Riga
```

## Data

`data/drone_profiles.json` — must contain `"dji_mini_4k"` key (mandatory fallback). Each profile needs: `display_name`, `max_wind_resistance_mps`, `rain_tolerance`, `takeoff_weight_g`, `camera_equipped`, `notes`, `aliases`.

Current profiles: `dji_mini_4k`, `dji_neo`, `dji_mini_3_pro`, `dji_air_3`, `dji_avata_2`.

`DroneProfileTool` raises `FileNotFoundError` on startup if the file is missing, and `ValueError` if `dji_mini_4k` key is absent.

## ChatAgent Conversation Memory

`ChatAgent` keeps `self.history` (list of `{role, content}` dicts). Last 10 messages are used as context. Assistant messages longer than 600 chars are truncated when passed back to Gemini to avoid token bloat. History persists for the session only — no disk persistence.

## Pipeline Error Handling

`CoordinatorAgent._handle_specific_flight_check` catches failures at each stage:

- Location failure → returns `stage: "location_not_found"` with `success: False`
- Weather failure → returns `stage: "weather_forecast_failed"` with `success: False`
- Location context failure → falls back to conservative "unknown" classification (does not abort)
- Suitability and Report always run if weather succeeds

`ChatAgent._format_error_response()` maps stage names to user-friendly messages.
