import json
from pathlib import Path


class DroneProfileTool:
    """
    Loads drone capability profiles from src/data/drone_profiles.json.

    If the user does not specify a drone model, DJI Mini 4K is used.
    If the user specifies an unknown drone model, DJI Mini 4K is used with a warning.
    """

    DRONE_PROFILE_PATH = "data/drone_profiles.json"
    FALLBACK_PROFILE_KEY = "dji_mini_4k"

    def __init__(self, profiles_path: str = DRONE_PROFILE_PATH):
        self.profiles_path = Path(profiles_path)
        self.profiles = self._load_profiles()

    def get_profile(self, drone_model: str | None = None) -> dict:
        if not drone_model:
            fallback_profile = self._get_fallback_profile()
            fallback_profile["profile_warning"] = (
                "No drone model was specified. DJI Mini 4K was used as the fallback drone profile."
            )
            return fallback_profile

        normalized_query = self._normalize(drone_model)

        for profile_key, profile in self.profiles.items():
            if self._normalize(profile_key) == normalized_query:
                return self._with_profile_key(profile_key, profile)

            display_name = profile.get("display_name", "")
            if self._normalize(display_name) == normalized_query:
                return self._with_profile_key(profile_key, profile)

            aliases = profile.get("aliases", [])
            for alias in aliases:
                if self._normalize(alias) == normalized_query:
                    return self._with_profile_key(profile_key, profile)

        fallback_profile = self._get_fallback_profile()
        fallback_profile["requested_model"] = drone_model
        fallback_profile["profile_warning"] = (
            f"Drone model '{drone_model}' was not found. "
            "DJI Mini 4K was used as the fallback drone profile."
        )

        return fallback_profile

    def _load_profiles(self) -> dict:
        if not self.profiles_path.exists():
            raise FileNotFoundError(
                f"Drone profile file not found: {self.profiles_path}"
            )

        with open(self.profiles_path, "r", encoding="utf-8") as file:
            profiles = json.load(file)

        if self.FALLBACK_PROFILE_KEY not in profiles:
            raise ValueError(
                f"drone_profiles.json must contain '{self.FALLBACK_PROFILE_KEY}' "
                "because it is used as the fallback profile."
            )

        return profiles

    def _get_fallback_profile(self) -> dict:
        return self._with_profile_key(
            self.FALLBACK_PROFILE_KEY,
            self.profiles[self.FALLBACK_PROFILE_KEY],
        )

    def _with_profile_key(self, profile_key: str, profile: dict) -> dict:
        copied_profile = dict(profile)
        copied_profile["profile_key"] = profile_key
        return copied_profile

    def _normalize(self, text: str) -> str:
        return text.lower().strip().replace("-", " ").replace("_", " ")
