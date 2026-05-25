from src.tools.drone_profile_tool import DroneProfileTool


def main():
    tool = DroneProfileTool()

    test_models = [
        None,
        "DJI Neo",
        "mini 4k",
        "avata",
        "unknown drone",
    ]

    for model in test_models:
        print()
        print(f"Requested model: {model}")
        profile = tool.get_profile(model)

        for key, value in profile.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
