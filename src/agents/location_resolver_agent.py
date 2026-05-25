from src.tools.geocoding_tool import GeocodingTool


class LocationResolverAgent:
    """
    Resolves a textual location into geographic coordinates.
    """

    def __init__(self):
        self.geocoding_tool = GeocodingTool()

    def resolve(self, location_text: str) -> dict:
        geocoding_result = self.geocoding_tool.geocode(location_text)

        return {
            "query": geocoding_result["query"],
            "display_name": geocoding_result["display_name"],
            "latitude": geocoding_result["latitude"],
            "longitude": geocoding_result["longitude"],
            "location_type": geocoding_result["raw_type"],
            "location_class": geocoding_result["raw_class"],
        }
