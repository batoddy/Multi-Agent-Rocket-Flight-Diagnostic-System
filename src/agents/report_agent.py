import json

from src.core.gemini_client import GeminiClient


class ReportAgent:
    """
    Generates the final user-facing report using Gemini.

    [1] FLIGHT OVERVIEW is fixed-formatted (facts only).
    [2] FINAL VERDICT and [3] DETAILED ANALYSIS are written by the LLM,
    which interprets both positive and negative conditions using actual numbers.
    """

    SEPARATOR = "-" * 50

    def __init__(self):
        self.llm_client = GeminiClient()

    def generate(
        self,
        request_data: dict,
        location: dict,
        weather: dict,
        location_context: dict,
        suitability: dict,
    ) -> str:
        overview = self._build_overview(request_data, location, weather, suitability)
        prompt = self._build_prompt(weather, location_context, suitability)
        return overview + "\n" + self.llm_client.generate(prompt)

    def _build_overview(
        self,
        request_data: dict,
        location: dict,
        weather: dict,
        suitability: dict,
    ) -> str:
        drone_profile = suitability.get("drone_profile", {})
        target_time = weather.get("time", "Unknown")
        timezone = request_data.get("timezone", "")

        lines = [
            "SYSTEM REPORT: DRONE FLIGHT SUITABILITY ANALYSIS",
            "",
            "[1] FLIGHT OVERVIEW",
            self.SEPARATOR,
            f"Target Location : {location.get('display_name', 'Unknown')}",
            f"Target Time     : {target_time} ({timezone})",
            f"Drone Profile   : {drone_profile.get('display_name', 'Unknown')}",
            f"Max Wind Resist.: {drone_profile.get('max_wind_resistance_mps', 'Unknown')} m/s",
        ]

        return "\n".join(lines)

    def _build_prompt(
        self,
        weather: dict,
        location_context: dict,
        suitability: dict,
    ) -> str:
        drone_profile = suitability.get("drone_profile", {})
        classification = location_context.get("classification", {})
        evaluations = suitability.get("evaluations", [])
        warnings = suitability.get("warnings", [])

        return f"""You are writing the analysis section of a drone flight suitability report.

You will receive structured flight data. Your job is to write two sections:
[2] FINAL VERDICT and [3] DETAILED ANALYSIS.

Write in plain English. No markdown, no bullet points using -, no emojis.
Use * for parameter headers in [3] as shown in the format below.
Be direct and concise. Your audience is amateur to professional drone pilots — they already
understand drone fundamentals. Do not over-explain basics like "rain damages electronics"
or "low visibility makes it hard to see". Instead, get straight to the point for this
specific flight: what the numbers mean in context, what the pilot should watch out for,
and what conditions actually work in their favor. Treat them as competent pilots.
Comment on both good and bad conditions.

---

FLIGHT DATA:

Weather at target time:
{json.dumps(weather, indent=2)}

Drone profile:
{json.dumps(drone_profile, indent=2)}

Location classification:
{json.dumps(classification, indent=2)}

Suitability decision: {suitability.get("decision")}
Suitability score: {suitability.get("score")} / 100
Risk level: {suitability.get("risk_level")}

Parameter evaluations (use these as your source of truth, but write your own sentences):
{json.dumps(evaluations, indent=2)}

Profile warnings (include these naturally if present):
{json.dumps(warnings, indent=2)}

---

OUTPUT FORMAT (follow this structure exactly, including the section headers and separator lines):

[2] FINAL VERDICT
--------------------------------------------------
2-3 sentences. State the bottom line and the key factor(s) driving it.
Do not mention the numeric score.

[3] DETAILED ANALYSIS
--------------------------------------------------
* WIND STABILITY
2-3 sentences. Reference actual m/s values and the drone's limit. Be specific about
the margin — is it comfortable, tight, or over the limit?

* PRECIPITATION RISK
2-3 sentences. Use actual mm and probability figures. Call out any meaningful risk or
confirm it is a non-issue.

* VISUAL LINE OF SIGHT
1-2 sentences. State the visibility figure and whether it is a limiting factor or not.

* BATTERY TEMPERATURE
1-2 sentences. State the temperature and whether it affects performance at this session.

* ENVIRONMENTAL HAZARD
2-3 sentences. Cover what the location actually offers — open space, water proximity,
urban density. Note both advantages and risks for this specific site.
"""

