from src.tools.drone_profile_tool import DroneProfileTool


class SuitabilityScoringAgent:
    """
    Scores drone flight suitability using weather, location context, and drone profile.
    Intentionally rule-based — no LLM — to produce explainable, deterministic output.
    """

    def __init__(self):
        self.drone_profile_tool = DroneProfileTool()

    def analyze(
        self,
        weather: dict,
        location_context: dict,
        drone_model: str | None = None,
    ) -> dict:
        drone_profile = self.drone_profile_tool.get_profile(drone_model)

        score = 100
        evaluations = []
        warnings = []

        score, wind_eval = self._evaluate_wind(score, weather, drone_profile)
        evaluations.append(wind_eval)

        score, rain_eval = self._evaluate_rain(score, weather, drone_profile)
        evaluations.append(rain_eval)

        score, visibility_eval = self._evaluate_visibility(score, weather)
        evaluations.append(visibility_eval)

        score, temp_eval = self._evaluate_temperature(score, weather)
        evaluations.append(temp_eval)

        score, context_eval = self._evaluate_location_context(score, location_context)
        evaluations.append(context_eval)

        if "profile_warning" in drone_profile:
            warnings.append(drone_profile["profile_warning"])

        score = max(0, min(100, score))

        return {
            "score": score,
            "decision": self._decision_from_score(score),
            "risk_level": self._risk_level_from_score(score),
            "drone_profile": self._clean_drone_profile(drone_profile),
            "evaluations": evaluations,
            "warnings": warnings,
        }

    def _evaluate_wind(
        self,
        score: int,
        weather: dict,
        drone_profile: dict,
    ) -> tuple[int, dict]:
        wind_speed = weather.get("wind_speed_10m_mps")
        wind_gusts = weather.get("wind_gusts_10m_mps")
        max_wind = drone_profile.get("max_wind_resistance_mps")

        if wind_speed is None or wind_gusts is None or max_wind is None:
            score -= 15
            return score, {
                "parameter": "Wind Stability",
                "status": "WARNING",
                "detail": (
                    "Wind speed, gust, or drone wind resistance data is missing. "
                    "Wind risk cannot be assessed, so a conservative deduction is applied."
                ),
            }

        wind_ratio = wind_speed / max_wind
        gust_ratio = wind_gusts / max_wind

        if gust_ratio > 1.0:
            score -= 40
            status = "CRITICAL"
            detail = (
                f"Expected wind gusts are {wind_gusts} m/s, which exceeds the drone's maximum "
                f"wind resistance of {max_wind} m/s. The drone cannot maintain stable flight, "
                f"creating a high risk of flyaway and uncontrolled descent."
            )
        elif gust_ratio > 0.9:
            score -= 25
            status = "WARNING"
            detail = (
                f"Expected wind gusts are {wind_gusts} m/s, which is very close to the drone's "
                f"wind resistance limit of {max_wind} m/s. Flight stability will be significantly "
                f"degraded, leading to rapid battery drain and reduced control authority."
            )
        elif wind_ratio > 1.0:
            score -= 45
            status = "CRITICAL"
            detail = (
                f"Average wind speed is {wind_speed} m/s, which exceeds the drone's maximum wind "
                f"resistance of {max_wind} m/s. Sustained flight is not safe under these conditions."
            )
        elif wind_ratio > 0.75 or gust_ratio > 0.75:
            score -= 20
            status = "WARNING"
            detail = (
                f"Average wind is {wind_speed} m/s and gusts reach {wind_gusts} m/s against "
                f"a drone limit of {max_wind} m/s. Conditions are challenging and will increase "
                f"battery consumption and reduce flight time significantly."
            )
        elif wind_ratio > 0.5:
            score -= 10
            status = "WARNING"
            detail = (
                f"Average wind is {wind_speed} m/s with gusts of {wind_gusts} m/s. "
                f"Drone wind resistance limit is {max_wind} m/s. Conditions are moderate. "
                f"Extra pilot attention is advised to maintain stable flight."
            )
        else:
            status = "OK"
            detail = (
                f"Expected wind gusts are {wind_gusts} m/s, which is well below the drone's "
                f"safe limit of {max_wind} m/s. Wind conditions are stable for flight."
            )

        return score, {"parameter": "Wind Stability", "status": status, "detail": detail}

    def _evaluate_rain(
        self,
        score: int,
        weather: dict,
        drone_profile: dict,
    ) -> tuple[int, dict]:
        rain_mm = weather.get("rain_mm", 0) or 0
        precipitation_probability = weather.get("precipitation_probability_percent", 0) or 0
        rain_tolerance = drone_profile.get("rain_tolerance", "not_waterproof")

        status = "OK"

        if rain_mm > 0:
            if rain_tolerance == "not_waterproof":
                score -= 35
                status = "CRITICAL"
                detail = (
                    f"Precipitation of {rain_mm} mm is expected. Because the drone is not "
                    f"waterproof, moisture will cause short circuits in the exposed electronics, "
                    f"making flight strictly inadvisable."
                )
            else:
                score -= 15
                status = "WARNING"
                detail = (
                    f"Precipitation of {rain_mm} mm is expected. The drone has some rain "
                    f"tolerance, but wet conditions still reduce reliability and visibility."
                )
        elif precipitation_probability >= 70:
            score -= 25
            status = "WARNING"
            detail = (
                f"No direct rain is expected at the target hour, but precipitation probability "
                f"is high at {precipitation_probability}%. Conditions may deteriorate quickly."
            )
        elif precipitation_probability >= 40:
            score -= 15
            status = "WARNING"
            detail = (
                f"No direct rain is expected at the target hour, but precipitation probability "
                f"is moderate at {precipitation_probability}%. Monitor conditions before takeoff."
            )
        elif precipitation_probability >= 20:
            score -= 5
            detail = (
                f"No precipitation is expected at the target hour. "
                f"Precipitation probability is low at {precipitation_probability}%."
            )
        else:
            detail = (
                f"No precipitation is expected (0.0 mm). The weather is dry, eliminating "
                f"the risk of water damage to the electronics."
            )

        return score, {"parameter": "Precipitation Risk", "status": status, "detail": detail}

    def _evaluate_visibility(
        self,
        score: int,
        weather: dict,
    ) -> tuple[int, dict]:
        visibility_m = weather.get("visibility_m")

        if visibility_m is None:
            score -= 5
            return score, {
                "parameter": "Visual Line of Sight",
                "status": "WARNING",
                "detail": "Visibility data is missing. Visual line of sight cannot be assessed.",
            }

        if visibility_m < 1000:
            score -= 35
            status = "CRITICAL"
            detail = (
                f"Visibility is severely reduced to {visibility_m} meters. This falls well below "
                f"the minimum required for safe Visual Line of Sight (VLOS) operations, creating "
                f"a high risk of collision with unmapped obstacles."
            )
        elif visibility_m < 3000:
            score -= 20
            status = "WARNING"
            detail = (
                f"Visibility is limited to {visibility_m} meters. Maintaining Visual Line of "
                f"Sight (VLOS) will be difficult, increasing the risk of collision with "
                f"obstacles at range."
            )
        elif visibility_m < 5000:
            score -= 10
            status = "WARNING"
            detail = (
                f"Visibility is {visibility_m} meters, which is acceptable but not ideal. "
                f"Visual Line of Sight (VLOS) is possible but reduced."
            )
        else:
            status = "OK"
            detail = (
                f"Visibility is clear at {visibility_m} meters, providing excellent Visual "
                f"Line of Sight (VLOS) for safe piloting."
            )

        return score, {"parameter": "Visual Line of Sight", "status": status, "detail": detail}

    def _evaluate_temperature(
        self,
        score: int,
        weather: dict,
    ) -> tuple[int, dict]:
        temperature_c = weather.get("temperature_2m_c")

        if temperature_c is None:
            score -= 5
            return score, {
                "parameter": "Battery Temperature",
                "status": "WARNING",
                "detail": "Temperature data is missing. Battery performance cannot be assessed.",
            }

        if temperature_c < -10:
            score -= 25
            status = "CRITICAL"
            detail = (
                f"Temperature is {temperature_c} C. Extreme cold rapidly reduces lithium-ion "
                f"battery voltage, causing severe flight time reduction and a high risk of "
                f"sudden voltage collapse mid-flight."
            )
        elif temperature_c < 0:
            score -= 15
            status = "WARNING"
            detail = (
                f"Temperature is {temperature_c} C. Sub-zero temperatures reduce lithium-ion "
                f"battery capacity significantly. Flight time will be reduced and sudden "
                f"power drops may occur. Pre-warm the battery before flight."
            )
        elif temperature_c < 5:
            score -= 8
            status = "WARNING"
            detail = (
                f"Temperature is {temperature_c} C. Cold weather decreases lithium-ion battery "
                f"voltage. Expect reduced flight time. Allow the battery to warm up before takeoff."
            )
        elif temperature_c > 40:
            score -= 10
            status = "WARNING"
            detail = (
                f"Temperature is {temperature_c} C. Excessive heat accelerates battery degradation "
                f"and may trigger thermal protection, causing reduced performance or forced landing."
            )
        else:
            status = "OK"
            detail = (
                f"Temperature is {temperature_c} C. This is within the optimal operating range "
                f"for lithium-ion batteries, ensuring stable power delivery and full flight time."
            )

        return score, {"parameter": "Battery Temperature", "status": status, "detail": detail}

    def _evaluate_location_context(
        self,
        score: int,
        location_context: dict,
    ) -> tuple[int, dict]:
        classification = location_context.get("classification", {})

        wind_exposure = classification.get("wind_exposure", "unknown")
        public_activity_level = classification.get("public_activity_level", "unknown")
        open_area_level = classification.get("open_area_level", "unknown")
        environment_type = classification.get("environment_type", "unknown")
        drone_operation_notes = classification.get("drone_operation_notes", [])

        deduction = 0
        concerns = []

        if wind_exposure == "high":
            deduction += 10
            concerns.append("high wind exposure")
        elif wind_exposure == "medium":
            deduction += 5
            concerns.append("moderate wind exposure")
        elif wind_exposure == "unknown":
            deduction += 5
            concerns.append("unknown wind exposure")

        if open_area_level == "high":
            deduction -= 5
        elif open_area_level == "low":
            deduction += 10
            concerns.append("limited open space for takeoff and landing")
        elif open_area_level == "unknown":
            deduction += 5
            concerns.append("unknown open area level")

        score -= deduction

        activity_note = f" Public activity level in the area is {public_activity_level}." if public_activity_level != "unknown" else ""

        if concerns:
            status = "WARNING"
            concern_str = "; ".join(concerns)
            detail = (
                f"The area is classified as '{environment_type}'.{activity_note} "
                f"Location analysis identified the following concerns: {concern_str}."
            )
        else:
            status = "OK"
            detail = (
                f"The area is classified as '{environment_type}'.{activity_note} "
                f"Location context presents no major environmental concerns for drone operations."
            )

        if drone_operation_notes:
            detail += " Notes: " + " ".join(drone_operation_notes[:3])

        return score, {"parameter": "Environmental Hazard", "status": status, "detail": detail}

    def _decision_from_score(self, score: int) -> str:
        if score >= 80:
            return "Suitable"
        if score >= 60:
            return "Suitable with strict caution"
        if score >= 40:
            return "Not ideal"
        return "Not recommended"

    def _risk_level_from_score(self, score: int) -> str:
        if score >= 80:
            return "Low"
        if score >= 60:
            return "Medium"
        if score >= 40:
            return "High"
        return "Very High"

    def _clean_drone_profile(self, drone_profile: dict) -> dict:
        return {
            "profile_key": drone_profile.get("profile_key"),
            "display_name": drone_profile.get("display_name"),
            "takeoff_weight_g": drone_profile.get("takeoff_weight_g"),
            "max_wind_resistance_mps": drone_profile.get("max_wind_resistance_mps"),
            "camera_equipped": drone_profile.get("camera_equipped"),
            "rain_tolerance": drone_profile.get("rain_tolerance"),
            "notes": drone_profile.get("notes", []),
        }
