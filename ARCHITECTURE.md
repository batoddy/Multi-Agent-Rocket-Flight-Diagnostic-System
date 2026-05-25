# System Architecture

## Overview

A Python multi-agent system that evaluates drone flight suitability at a given location and time.
The user communicates via a conversational terminal interface in natural language.
The system resolves the request, fetches real external data, scores flight conditions with deterministic rules,
and produces a human-readable report written by an LLM.

---

## Top-Level Call Chain

```
main.py
  └── ChatAgent
        │
        ├── [general question] ──► Gemini (direct response)
        │
        └── [flight query]
              │
              ├── _enrich_with_history()   # expand short follow-ups using session history
              │
              └── CoordinatorAgent
                    │
                    ├── 1. _extract_request()         Gemini
                    │      NL query → structured JSON (location, date, time, drone model)
                    │
                    ├── 2. LocationResolverAgent
                    │      location text → lat / lon        [OSM Nominatim API]
                    │
                    ├── 3. WeatherForecastAgent
                    │      lat / lon / date / time → hourly weather slice    [Open-Meteo API]
                    │
                    ├── 4. LocationContextAgent
                    │      lat / lon → OSM feature counts → env classification    [Overpass API + Gemini]
                    │
                    ├── 5. SuitabilityScoringAgent
                    │      weather + context + drone profile → score + evaluations    [rule-based]
                    │
                    └── 6. ReportAgent
                           all results → formatted text report    [Gemini]
```

---

## Layer Structure

```
src/
├── core/               shared infrastructure
│   ├── config.py       reads .env into Config class
│   ├── gemini_client.py  thin wrapper around google-genai SDK
│   └── json_utils.py   shared parse_json_response() utility
│
├── agents/             decision-making layer
│   ├── chat_agent.py           session management, query routing
│   ├── coordinator_agent.py    pipeline orchestration
│   ├── location_resolver_agent.py
│   ├── weather_forecast_agent.py
│   ├── location_context_agent.py
│   ├── suitability_scoring_agent.py
│   └── report_agent.py
│
└── tools/              external API wrappers (no logic, only I/O)
    ├── geocoding_tool.py         OSM Nominatim
    ├── weather_api_tool.py       Open-Meteo
    ├── location_context_tool.py  OSM Overpass
    └── drone_profile_tool.py     data/drone_profiles.json

data/
└── drone_profiles.json   hardware specs for known drone models

outputs/
└── latest_result.json    full pipeline result of the last flight query
```

---

## Component Details

### ChatAgent  `src/agents/chat_agent.py`

Entry point for all user interaction. Maintains `self.history` across the session (last 10 messages,
content truncated to 600 chars when passed to Gemini to avoid token bloat).

| Method | What it does |
|---|---|
| `chat(message)` | Routes message, updates history, returns response string |
| `_is_flight_query()` | Gemini yes/no: is this a flight suitability question? |
| `_enrich_with_history()` | Gemini: expand "what about 3pm?" into a full standalone query |
| `_handle_general_chat()` | Gemini: respond conversationally with history context |
| `_handle_flight_query()` | Calls CoordinatorAgent, saves JSON, returns final_report |
| `_format_error_response()` | Maps pipeline failure stage to user-friendly message |

---

### CoordinatorAgent  `src/agents/coordinator_agent.py`

Orchestrates the full pipeline. Owns all sub-agents as instance variables (initialized once on startup).

**Extraction output (`_extract_request`):**
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

**Error handling strategy:**
- Location failure → abort, return `stage: location_not_found`
- Weather failure → abort, return `stage: weather_forecast_failed`
- Location context failure → continue with conservative "unknown" fallback classification
- Scoring and Report always run if weather succeeded

**Final return dict keys:**
`stage`, `success`, `request`, `location`, `weather`, `location_context`, `suitability`, `final_report`

---

### LocationResolverAgent  `src/agents/location_resolver_agent.py`

Wraps `GeocodingTool`. No logic, just cleans the output.

**Output:**
```json
{ "query": "...", "display_name": "...", "latitude": 56.95, "longitude": 24.10,
  "location_type": "university", "location_class": "amenity" }
```

---

### WeatherForecastAgent  `src/agents/weather_forecast_agent.py`

Wraps `WeatherAPITool`. Fetches the full day's hourly forecast, then slices the exact target hour.

**Output (one hour slice):**
```json
{ "time": "2026-05-16T12:00", "temperature_2m_c": 12.5,
  "relative_humidity_2m_percent": 65, "precipitation_probability_percent": 20,
  "rain_mm": 0.0, "cloud_cover_percent": 70, "visibility_m": 20000,
  "wind_speed_10m_mps": 5.2, "wind_gusts_10m_mps": 8.0, "wind_direction_10m_deg": 320 }
```

Wind unit is always `m/s` — matches drone profile `max_wind_resistance_mps`.

---

### LocationContextAgent  `src/agents/location_context_agent.py`

Two-step process: fetch raw OSM feature counts via Overpass API, then send to Gemini for interpretation.

**Step 1 — `LocationContextTool`** counts features within 500m radius:
`water_count`, `park_count`, `open_land_count`, `road_count`, `building_count`, `amenity_count`, `tourism_count`

**Step 2 — Gemini** interprets counts and returns `classification`:
```json
{
  "environment_type": "urban_riverside_area",
  "near_water": true,
  "near_park_or_open_land": true,
  "building_density": "medium",
  "road_density": "medium",
  "open_area_level": "medium",
  "visual_openness": "medium",
  "urban_complexity": "medium",
  "public_activity_level": "medium",
  "wind_exposure": "medium",
  "drone_operation_notes": ["Area is adjacent to a river, increasing wind exposure."],
  "context_summary": "Mixed urban riverside environment with open-space signals."
}
```

`wind_exposure` values: `normal | medium | high | unknown`
All other categorical fields: `low | medium | high | unknown`

The Overpass tool tries two endpoints and returns a safe fallback dict (never raises) if both fail.

---

### SuitabilityScoringAgent  `src/agents/suitability_scoring_agent.py`

**No LLM.** Fully deterministic rule-based scoring. Same inputs always produce the same score.

Score starts at 100. Five evaluation categories, each returns one `{parameter, status, detail}` dict.

| Category | Max deduction | CRITICAL threshold |
|---|---|---|
| Wind Stability | −45 (avg) + −40 (gusts) | avg or gusts exceed drone limit |
| Precipitation Risk | −35 rain + −25 probability | rain > 0 on non-waterproof drone |
| Visual Line of Sight | −35 | visibility < 1000 m |
| Battery Temperature | −25 | temperature < −10°C |
| Environmental Hazard | −10 wind / −10 open area | n/a |

`public_activity_level` is **informational only** — it appears in the detail text but causes no score deduction.

Decision thresholds:

| Score | Decision | Risk Level |
|---|---|---|
| ≥ 80 | Suitable | Low |
| ≥ 60 | Suitable with strict caution | Medium |
| ≥ 40 | Not ideal | High |
| < 40 | Not recommended | Very High |

Drone profile fallback: if no model specified or model not found → `dji_mini_4k` (with a warning in the output).

---

### ReportAgent  `src/agents/report_agent.py`

Produces the final user-facing text. Two-part output:

**[1] FLIGHT OVERVIEW** — fixed-formatted, no LLM:
```
Target Location : ...
Target Time     : ...
Drone Profile   : ...
Max Wind Resist.: ... m/s
```

**[2] FINAL VERDICT + [3] DETAILED ANALYSIS** — written by Gemini.
Receives: weather values, drone profile, location classification, suitability evaluations, warnings.
Tone: direct and factual, written for amateur-to-professional drone pilots.
Uses actual numbers with contextual interpretation. Calls out both positive and negative conditions.
No regulatory disclaimer (intentionally removed).

---

## External Dependencies

| Service | Used by | Auth | Failure behavior |
|---|---|---|---|
| Google Gemini | `GeminiClient` | `GEMINI_API_KEY` in `.env` | raises — pipeline aborts |
| OSM Nominatim | `GeocodingTool` | none (User-Agent header required) | raises — CoordinatorAgent catches, returns error stage |
| Open-Meteo | `WeatherAPITool` | none | raises — CoordinatorAgent catches, returns error stage |
| OSM Overpass | `LocationContextTool` | none | returns fallback dict — pipeline continues |

---

## Data Flow (single query)

```
User text
  │
  ▼
ChatAgent._is_flight_query()  ──[no]──► Gemini response → terminal
  │ [yes]
  ▼
ChatAgent._enrich_with_history()  →  full standalone query string
  │
  ▼
CoordinatorAgent._extract_request()
  │   Gemini → { location_text, date, time, drone_model, ... }
  ▼
LocationResolverAgent.resolve(location_text)
  │   Nominatim → { latitude, longitude, display_name }
  ▼
WeatherForecastAgent.analyze(lat, lon, date, time)
  │   Open-Meteo → { wind_speed, wind_gusts, rain_mm, visibility_m, temperature_2m_c, ... }
  ▼
LocationContextAgent.analyze(lat, lon, location_name)
  │   Overpass → feature counts → Gemini → { environment_type, wind_exposure, open_area_level, ... }
  ▼
SuitabilityScoringAgent.analyze(weather, location_context, drone_model)
  │   rules → { score, decision, risk_level, evaluations[], warnings[] }
  ▼
ReportAgent.generate(request_data, location, weather, location_context, suitability)
  │   Gemini → formatted report text
  ▼
ChatAgent → terminal output + outputs/latest_result.json
```

---

## Key Design Decisions

**Agents orchestrate, tools only do I/O.**
Tools (`geocoding_tool`, `weather_api_tool`, etc.) make HTTP calls and return raw data.
Agents apply logic, call Gemini, and decide what to do with the data.

**SuitabilityScoringAgent has no LLM by design.**
Scoring must be deterministic and auditable. The LLM is used only for interpretation and presentation
(LocationContextAgent, ReportAgent), not for numerical judgment.

**LocationContext failure is non-fatal.**
If Overpass or Gemini fails during context analysis, the pipeline continues with a conservative
"unknown" fallback classification. This avoids losing the whole flight check over a map data issue.

**ChatAgent enriches short follow-ups before routing.**
"What about 3pm?" is expanded into a complete query via Gemini before CoordinatorAgent sees it,
so CoordinatorAgent always receives a self-contained natural language request.

**All LLM outputs are validated before use.**
Both CoordinatorAgent and LocationContextAgent validate required fields and allowed enum values
on every Gemini response. `parse_json_response()` in `src/core/json_utils.py` strips markdown
fences and raises a clear error on invalid JSON.
