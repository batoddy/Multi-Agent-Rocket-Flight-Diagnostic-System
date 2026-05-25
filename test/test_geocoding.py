from src.tools.geocoding_tool import GeocodingTool


def main():
    tool = GeocodingTool()

    result = tool.geocode("Riga National Library")

    print("GeocodingTool result:")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
