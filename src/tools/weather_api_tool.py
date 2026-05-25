import requests


class WeatherAPITool:
    """
    Fetches hourly weather forecast data from Open-Meteo API.

    Open-Meteo is used because:
    - it supports coordinate-based forecast
    - it provides hourly weather data
    - it does not require an API key
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def get_hourly_forecast(
        self,
        latitude: float,
        longitude: float,
        date: str,
        timezone: str,
    ) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation_probability",
                    "rain",
                    "cloud_cover",
                    "visibility",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "wind_direction_10m",
                ]
            ),
            "wind_speed_unit": "ms",
            "timezone": timezone,
            "start_date": date,
            "end_date": date,
        }

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Weather API request failed. "
                f"Status code: {response.status_code}, "
                f"Response: {response.text}"
            )

        return response.json()
