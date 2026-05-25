import requests


class GeocodingTool:
    """
    Converts a text-based location into coordinates using OpenStreetMap Nominatim API.
    """

    BASE_URL = "https://nominatim.openstreetmap.org/search"

    def geocode(self, location_text: str, limit: int = 1) -> dict:
        if not location_text or not location_text.strip():
            raise ValueError("Location text is empty.")

        params = {
            "q": location_text,
            "format": "json",
            "limit": limit,
            "addressdetails": 1,
        }

        headers = {"User-Agent": "DroneFlightSuitabilityAssistant/1.0"}

        response = requests.get(
            self.BASE_URL,
            params=params,
            headers=headers,
            timeout=15,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Geocoding request failed. "
                f"Status code: {response.status_code}, "
                f"Response: {response.text[:300]}"
            )

        results = response.json()

        if not results:
            raise ValueError(f"Location could not be found for: {location_text}")

        best_match = results[0]

        return {
            "query": location_text,
            "display_name": best_match.get("display_name"),
            "latitude": float(best_match["lat"]),
            "longitude": float(best_match["lon"]),
            "raw_type": best_match.get("type"),
            "raw_class": best_match.get("class"),
        }
