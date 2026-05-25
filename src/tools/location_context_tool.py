import requests


class LocationContextTool:
    """
    Fetches simple OpenStreetMap-based context around a coordinate
    using the Overpass API.

    This tool intentionally stays simple:
    - It counts broad feature groups around the coordinate.
    - It does not perform detailed GIS / obstacle mapping.
    - If Overpass is unavailable, it returns a safe fallback result instead
      of crashing the whole pipeline.
    """

    OVERPASS_URLS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    def get_context_features(
        self,
        latitude: float,
        longitude: float,
        radius_m: int = 500,
    ) -> dict:
        query = self._build_query(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
        )

        last_error = None

        for url in self.OVERPASS_URLS:
            try:
                response = requests.post(
                    url,
                    data=query.encode("utf-8"),
                    headers={
                        "User-Agent": "DroneFlightSuitabilityAssistant/1.0",
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    elements = data.get("elements", [])

                    return self._summarize_elements(
                        elements=elements,
                        radius_m=radius_m,
                    )

                last_error = (
                    f"Overpass request failed at {url}. "
                    f"Status code: {response.status_code}, "
                    f"Response: {response.text[:300]}"
                )

            except Exception as error:
                last_error = str(error)

        return self._fallback_context(
            error_message=last_error,
            radius_m=radius_m,
        )

    def _build_query(
        self,
        latitude: float,
        longitude: float,
        radius_m: int,
    ) -> str:
        return f"""
[out:json][timeout:25];
(
  way(around:{radius_m},{latitude},{longitude})["natural"="water"];
  relation(around:{radius_m},{latitude},{longitude})["natural"="water"];

  way(around:{radius_m},{latitude},{longitude})["waterway"];

  way(around:{radius_m},{latitude},{longitude})["leisure"="park"];
  relation(around:{radius_m},{latitude},{longitude})["leisure"="park"];

  way(around:{radius_m},{latitude},{longitude})["leisure"="garden"];
  way(around:{radius_m},{latitude},{longitude})["landuse"="grass"];
  way(around:{radius_m},{latitude},{longitude})["natural"="grassland"];

  way(around:{radius_m},{latitude},{longitude})["highway"];
  way(around:{radius_m},{latitude},{longitude})["building"];

  node(around:{radius_m},{latitude},{longitude})["amenity"];
  node(around:{radius_m},{latitude},{longitude})["tourism"];
);
out tags center;
"""

    def _summarize_elements(
        self,
        elements: list[dict],
        radius_m: int,
    ) -> dict:
        summary = {
            "source": "overpass_api",
            "data_available": True,
            "radius_m": radius_m,
            "water_count": 0,
            "park_count": 0,
            "open_land_count": 0,
            "road_count": 0,
            "building_count": 0,
            "amenity_count": 0,
            "tourism_count": 0,
            "total_features": len(elements),
            "context_hints": {
                "has_water_or_riverside_signal": False,
                "has_park_or_open_land_signal": False,
                "has_urban_signal": False,
                "has_public_activity_signal": False,
            },
            "sample_features": [],
            "warning": None,
        }

        for element in elements:
            tags = element.get("tags", {})
            feature_type = self._detect_feature_type(tags)

            if not feature_type:
                continue

            self._increment_count(summary, feature_type)

            self._add_sample_feature(
                summary=summary,
                tags=tags,
                feature_type=feature_type,
            )

        summary["context_hints"] = self._build_context_hints(summary)

        return summary

    def _detect_feature_type(self, tags: dict) -> str | None:
        if tags.get("natural") == "water" or "water" in tags:
            return "water"

        if "waterway" in tags:
            return "waterway"

        if tags.get("leisure") == "park":
            return "park"

        if tags.get("leisure") == "garden":
            return "open_land:garden"

        if tags.get("landuse") == "grass":
            return "open_land:grass"

        if tags.get("natural") == "grassland":
            return "open_land:grassland"

        if "highway" in tags:
            return "road"

        if "building" in tags:
            return "building"

        if "amenity" in tags:
            return f"amenity:{tags.get('amenity')}"

        if "tourism" in tags:
            return f"tourism:{tags.get('tourism')}"

        return None

    def _increment_count(self, summary: dict, feature_type: str) -> None:
        if feature_type in {"water", "waterway"}:
            summary["water_count"] += 1

        elif feature_type == "park":
            summary["park_count"] += 1

        elif feature_type.startswith("open_land"):
            summary["open_land_count"] += 1

        elif feature_type == "road":
            summary["road_count"] += 1

        elif feature_type == "building":
            summary["building_count"] += 1

        elif feature_type.startswith("amenity"):
            summary["amenity_count"] += 1

        elif feature_type.startswith("tourism"):
            summary["tourism_count"] += 1

    def _add_sample_feature(
        self,
        summary: dict,
        tags: dict,
        feature_type: str,
    ) -> None:
        """
        Adds only useful broad examples.

        We intentionally avoid adding small detailed features such as:
        - ATM
        - cafe
        - restaurant
        - parking
        - bicycle rental

        Because they make the LLM over-interpret the location context.
        """

        important_sample_types = {
            "water",
            "waterway",
            "park",
            "open_land:garden",
            "open_land:grass",
            "open_land:grassland",
            "building",
            "road",
            "tourism:viewpoint",
        }

        if feature_type not in important_sample_types:
            return

        if len(summary["sample_features"]) >= 5:
            return

        feature_name = tags.get("name")

        sample = {
            "name": feature_name,
            "type": feature_type,
        }

        if sample not in summary["sample_features"]:
            summary["sample_features"].append(sample)

    def _build_context_hints(self, summary: dict) -> dict:
        has_water_or_riverside_signal = summary["water_count"] > 0

        has_park_or_open_land_signal = (
            summary["park_count"] > 0 or summary["open_land_count"] > 0
        )

        has_urban_signal = (
            summary["building_count"] > 0
            or summary["road_count"] > 0
            or summary["amenity_count"] > 0
        )

        has_public_activity_signal = (
            summary["amenity_count"] > 0
            or summary["tourism_count"] > 0
            or summary["road_count"] > 0
        )

        return {
            "has_water_or_riverside_signal": has_water_or_riverside_signal,
            "has_park_or_open_land_signal": has_park_or_open_land_signal,
            "has_urban_signal": has_urban_signal,
            "has_public_activity_signal": has_public_activity_signal,
        }

    def _fallback_context(
        self,
        error_message: str | None,
        radius_m: int,
    ) -> dict:
        return {
            "source": "fallback",
            "data_available": False,
            "radius_m": radius_m,
            "water_count": 0,
            "park_count": 0,
            "open_land_count": 0,
            "road_count": 0,
            "building_count": 0,
            "amenity_count": 0,
            "tourism_count": 0,
            "total_features": 0,
            "context_hints": {
                "has_water_or_riverside_signal": False,
                "has_park_or_open_land_signal": False,
                "has_urban_signal": False,
                "has_public_activity_signal": False,
            },
            "sample_features": [],
            "warning": (
                "OpenStreetMap Overpass data could not be retrieved. "
                "Location context analysis will be conservative."
            ),
            "error": error_message,
        }
