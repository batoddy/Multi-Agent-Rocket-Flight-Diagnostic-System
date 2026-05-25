from src.agents.suitability_scoring_agent import SuitabilityScoringAgent


def print_result(result: dict):
    print(f"Score     : {result['score']}")
    print(f"Decision  : {result['decision']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Drone     : {result['drone_profile']['display_name']}")

    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"  [!] {warning}")

    print("Evaluations:")
    for evaluation in result["evaluations"]:
        print(f"  * {evaluation['parameter']}")
        print(f"    Status  : {evaluation['status']}")
        print(f"    Analysis: {evaluation['detail']}")


def main():
    print("Scoring agent test started.")

    weather = {
        "time": "2026-05-11T12:00",
        "temperature_2m_c": 12.5,
        "relative_humidity_2m_percent": 65,
        "precipitation_probability_percent": 20,
        "rain_mm": 0.0,
        "cloud_cover_percent": 70,
        "visibility_m": 20000,
        "wind_speed_10m_mps": 5.2,
        "wind_gusts_10m_mps": 8.0,
        "wind_direction_10m_deg": 320,
    }

    location_context = {
        "classification": {
            "environment_type": "urban_riverside_area",
            "near_water": True,
            "near_park_or_open_land": True,
            "building_density": "medium",
            "road_density": "medium",
            "open_area_level": "medium",
            "visual_openness": "medium",
            "urban_complexity": "medium",
            "public_activity_level": "medium",
            "wind_exposure": "medium",
            "drone_operation_notes": [
                "Area is adjacent to a river, increasing wind exposure."
            ],
            "context_summary": (
                "The area appears to be a mixed urban riverside environment "
                "with some open-space signals."
            ),
        }
    }

    agent = SuitabilityScoringAgent()

    print("\n=== Test 1: No model specified, should use default profile ===")
    result = agent.analyze(
        weather=weather,
        location_context=location_context,
        drone_model=None,
    )
    print_result(result)

    print("\n=== Test 2: DJI Neo ===")
    result = agent.analyze(
        weather=weather,
        location_context=location_context,
        drone_model="DJI Neo",
    )
    print_result(result)

    print("\n=== Test 3: Unknown model, should fallback to default profile ===")
    result = agent.analyze(
        weather=weather,
        location_context=location_context,
        drone_model="random drone model",
    )
    print_result(result)

    print("\nScoring agent test finished.")


if __name__ == "__main__":
    main()
