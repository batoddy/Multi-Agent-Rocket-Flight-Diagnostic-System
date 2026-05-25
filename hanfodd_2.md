Haklısınız, önceki yanıtımda dokümanın tamamını yapılandırmak isterken metni "özet bir mimari rapor" formatına dönüştürerek fazla kısaltmışım. Amacımız orijinal dokümanın geniş yapısını ve tüm adımlarını korurken, yalnızca talep ettiğiniz **neden-sonuç ilişkisine dayalı detaylı değerlendirme** ve **sistematik raporlama** kısımlarını entegre etmek olmalıydı.

Aşağıda, gönderdiğiniz orijinal dokümanın tüm bölümlerini (geliştirme adımları, klasör yapısı, API detayları vb.) koruyarak, talep ettiğiniz yapısal değişiklikleri (emoji içermeyen, LLM ve insan okumasına uygun, tüm uçuş parametrelerini kapsayan neden-sonuç analizini) 14. ve 15. maddelere detaylıca işlediğim **tam kapsamlı** versiyonu sunuyorum.

---

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

First test each external API or tool alone. Then connect it to its agent. Then connect that agent to CoordinatorAgent. main.py should remain simple and only call CoordinatorAgent.

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

There is no TimeParserTool in the final direction. The project uses an LLM in CoordinatorAgent. Therefore, date/time/location/drone model extraction should be done by CoordinatorAgent using Gemini.

---

## 5. Dependencies

`requirements.txt` should contain:

```txt
requests
python-dotenv
google-genai

```

Do not use the old `google.generativeai` package because it is deprecated. Use the new SDK:

```python
from google import genai

```

---

## 6. Environment File

`.env`:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite-preview
DEFAULT_TIMEZONE=Europe/Riga

```

---

## 7. Core Files

### 7.1 src/core/config.py

Purpose: Load environment variables and provide global config values.

### 7.2 src/core/gemini_client.py

Purpose: Minimal wrapper around Google Gen AI SDK. Used by LLM-based agents.

---

## 8. CoordinatorAgent Design

### 8.1 Purpose

CoordinatorAgent is the central orchestrator. It understands the user query, extracts structured task information, calls the required agents sequentially, collects intermediate results, and returns the final result.

### 8.2 Current MVP Behavior

Produces structured request data from user query (intent, location_text, date, time, timezone, activity, drone_model).

### 8.3 CoordinatorAgent Workflow

Current specific flight check workflow handles sequential passing of data from LocationResolver to Weather, to Context, to Scoring, and finally to Report.

---

## 9. Geocoding / Location Resolution

### 9.1 src/tools/geocoding_tool.py

Converts text-based location into coordinates using OpenStreetMap Nominatim API. Requires User-Agent header.

### 9.2 src/agents/location_resolver_agent.py

Wraps GeocodingTool and returns clean location data to CoordinatorAgent.

---

## 10. Weather Forecast

### 10.1 src/tools/weather_api_tool.py

Uses Open-Meteo API. Fetches hourly forecast. Wind speed unit must be `ms` (meters per second) to match drone profiles.

### 10.2 src/agents/weather_forecast_agent.py

Calls WeatherAPITool and isolates the exact target hour from hourly forecast data.

---

## 11. Location Context

### 11.1 Design Decision

LocationContextTool collects OSM/Overpass feature counts. LocationContextAgent uses Gemini to interpret those counts for drone flight suitability.

### 11.2 src/tools/location_context_tool.py

Uses OpenStreetMap Overpass API to count features (water, park, road, building, amenity) within a 500m radius. Must include multiple endpoints and a fallback JSON if all endpoints fail (to prevent system crashes).

### 11.3 src/agents/location_context_agent.py

Sends feature summary to Gemini and returns a structured JSON interpretation (e.g., building_density, wind_exposure, public_area_risk).

---

## 12. Output File Writing

`main.py` creates CoordinatorAgent, calls `handle_user_request()`, saves the final dictionary to `outputs/latest_result.json`, and prints to terminal.

---

## 13. Drone Profile Feature

`data/drone_profiles.json` contains hardware limits for drones (takeoff weight, max wind resistance in m/s, rain tolerance, etc.). Provides a fallback default drone if the user does not specify one.

---

## 14. SuitabilityScoringAgent — Core Implementation logic

This agent evaluates all gathered data (weather, location context) against the selected `drone_profile`. The scoring logic must be objective, deterministic, and output detailed cause-and-effect explanations for every parameter.

**Inputs:**

```python
weather: dict
location_context: dict
drone_model: str | None

```

**Evaluation Logic & Cause-and-Effect Rules:**
The system starts with a score of 100. Each parameter is evaluated individually. The evaluation must clearly state the environmental condition, compare it to the drone's hardware limitation or safety regulation, and explain the physical consequence.

- **Wind & Gusts Evaluation:**
- Compare `wind_gusts_10m_mps` with `drone_profile.max_wind_resistance_mps`.
- _Negative Case:_ "Expected wind gusts are [X] m/s. Because the drone's maximum wind resistance is [Y] m/s, the drone will struggle to maintain stability, leading to rapid battery drain and high risk of flyaway." -> Subtract heavily.
- _Positive Case:_ "Expected wind gusts are [X] m/s, which is well below the drone's safe limit of [Y] m/s. Wind conditions are stable for flight." -> No deduction.

- **Precipitation (Rain) Evaluation:**
- Compare `rain_mm` with `drone_profile.rain_tolerance`.
- _Negative Case:_ "Precipitation of [X] mm is expected. Because the drone is not waterproof, moisture will cause short circuits in the exposed electronics, making flight strictly prohibited." -> Subtract heavily.
- _Positive Case:_ "No precipitation is expected (0.0 mm). The weather is dry, eliminating the risk of water damage to the electronics." -> No deduction.

- **Visibility Evaluation:**
- Check `visibility_m`.
- _Negative Case:_ "Visibility is reduced to [X] meters. This severely limits the pilot's Visual Line of Sight (VLOS), increasing the risk of collision with unmapped obstacles." -> Subtract moderately.
- _Positive Case:_ "Visibility is clear at [X] meters, providing excellent Visual Line of Sight (VLOS) for safe piloting." -> No deduction.

- **Temperature Evaluation:**
- Check `temperature_2m_c`.
- _Negative/Cold Case:_ "Temperature is [X] C. Cold weather rapidly decreases lithium-ion battery voltage. Flight time will be significantly reduced, and sudden voltage drops may occur." -> Subtract moderately.
- _Positive Case:_ "Temperature is [X] C. This is within the optimal operating range for lithium-ion batteries, ensuring stable power delivery." -> No deduction.

- **Location Risk Evaluation:**
- Check `location_context.classification.public_area_risk` and `wind_exposure`.
- _Negative Case:_ "The area has high public activity and high wind exposure due to nearby water. Flying over populated areas poses a safety hazard, and water proximity risks unrecoverable crashes." -> Subtract moderately.
- _Positive Case:_ "The area provides open space with low building density, offering safe takeoff/landing zones and clear GPS signal reception." -> Positive adjustment or no deduction.

**Expected Structured JSON Output (for programmatic parsing):**

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
      "detail": "Expected wind gusts are 9.5 m/s. Because the drone's maximum wind resistance is 10.7 m/s, the drone will struggle to maintain stability, leading to rapid battery drain and high risk of flyaway."
    },
    {
      "parameter": "Precipitation Risk",
      "status": "OK",
      "detail": "No precipitation is expected (0.0 mm). The weather is dry, eliminating the risk of water damage to the electronics."
    },
    {
      "parameter": "Visual Line of Sight",
      "status": "OK",
      "detail": "Visibility is clear at 24000 meters, providing excellent Visual Line of Sight (VLOS) for safe piloting."
    },
    {
      "parameter": "Battery Temperature",
      "status": "OK",
      "detail": "Temperature is 15.2 C. This is within the optimal operating range for lithium-ion batteries, ensuring stable power delivery."
    },
    {
      "parameter": "Environmental Hazard",
      "status": "WARNING",
      "detail": "The area has high public activity and high wind exposure due to nearby water. Flying over populated areas poses a safety hazard, and water proximity risks unrecoverable crashes."
    }
  ]
}
```

---

## 15. ReportAgent — Final Formatting Logic

ReportAgent generates the final user-facing text based exclusively on the structured JSON from `SuitabilityScoringAgent`. It must act as a strict text formatter.

**Formatting Rules:**

- The report must be machine-readable and human-readable.
- NO emojis, subjective feelings, or conversational fillers.
- Must use standard markdown lists (`*` or `-`) and clear section headers.
- The cause-and-effect explanations from the `evaluations` array must be directly printed.

**Expected Final Report Format:**

```text
SYSTEM REPORT: DRONE FLIGHT SUITABILITY ANALYSIS

[1] FLIGHT OVERVIEW
--------------------------------------------------
Target Location: Riga National Library area, Riga, Latvia
Target Time: 2026-05-16 12:00:00 (Europe/Riga)
Drone Profile: DJI Mini 4K
Max Wind Resistance: 10.7 m/s

[2] FINAL VERDICT
--------------------------------------------------
Decision: SUITABLE WITH STRICT CAUTION
Flight Suitability Score: 65 / 100
Overall Risk Level: MEDIUM

[3] DETAILED CAUSE-AND-EFFECT EVALUATION
--------------------------------------------------
* WIND STABILITY
  Status: WARNING
  Analysis: Expected wind gusts are 9.5 m/s. Because the drone's maximum wind resistance is 10.7 m/s, the drone will struggle to maintain stability, leading to rapid battery drain and high risk of flyaway.

* PRECIPITATION RISK
  Status: OK
  Analysis: No precipitation is expected (0.0 mm). The weather is dry, eliminating the risk of water damage to the electronics.

* VISUAL LINE OF SIGHT
  Status: OK
  Analysis: Visibility is clear at 24000 meters, providing excellent Visual Line of Sight (VLOS) for safe piloting.

* BATTERY TEMPERATURE
  Status: OK
  Analysis: Temperature is 15.2 C. This is within the optimal operating range for lithium-ion batteries, ensuring stable power delivery.

* ENVIRONMENTAL HAZARD
  Status: WARNING
  Analysis: The area has high public activity and high wind exposure due to nearby water. Flying over populated areas poses a safety hazard, and water proximity risks unrecoverable crashes.

[4] REGULATORY DISCLAIMER
--------------------------------------------------
This system provides preliminary technical and meteorological decision support only. It does not provide legal flight authorization. The pilot in command is strictly responsible for checking official local UAS geographical zones, airspace restrictions, and obtaining required permissions prior to takeoff.

```

---

## 16. Future Features

After MVP, planned features include:
16.1 Alternative Time Recommendation
16.2 Location Recommendation
16.3 Airspace / Restriction Awareness
16.4 Drone Model-Specific Suitability (Covered in current design iterations).

---

## 17. Important Development Rules

Rule 1 — main.py stays simple
Rule 2 — CoordinatorAgent orchestrates everything
Rule 3 — Test tools before integration
Rule 4 — External API failures should not crash the whole system when possible
Rule 5 — Keep LLM output structured (Ask for ONLY valid JSON)
Rule 6 — Do not over-engineer

---

## 18. Current Debug Notes

- Use `google-genai` instead of `google.generativeai`.
- Handle Overpass API status code 406 gracefully by returning fallback context.

---

## 19. Immediate Next Step

1. Create/verify `data/drone_profiles.json`.
2. Implement `src/tools/drone_profile_tool.py`.
3. Test DroneProfileTool alone.
4. Implement `src/agents/suitability_scoring_agent.py` using the detailed logic outlined in Section 14.
5. Add to CoordinatorAgent, then implement `ReportAgent` using Section 15 layout.
6. Run `main.py`.

---

## 20. One-Sentence Summary

This is a simple but modular multi-agent Python system where CoordinatorAgent uses Gemini to understand a drone flight request, then orchestrates location resolution, weather forecast retrieval, LLM-assisted location context interpretation, comprehensive cause-and-effect suitability scoring, and strict text-based report generation, while keeping main.py minimal and saving results to a structured JSON output file.
