from src.tools.weather_api_tool import WeatherAPITool


class WeatherForecastAgent:
    """
    Retrieves hourly weather forecast for a resolved location and target time.
    """

    def __init__(self):
        self.weather_api_tool = WeatherAPITool()

    def analyze(
        self,
        latitude: float,
        longitude: float,
        date: str,
        time: str,
        timezone: str,
    ) -> dict:
        forecast_data = self.weather_api_tool.get_hourly_forecast(
            latitude=latitude,
            longitude=longitude,
            date=date,
            timezone=timezone,
        )

        target_hour = f"{date}T{time}"
        hourly = forecast_data.get("hourly", {})

        available_times = hourly.get("time", [])

        if target_hour not in available_times:
            raise ValueError(
                f"Target hour {target_hour} was not found in weather forecast data."
            )

        index = available_times.index(target_hour)

        return {
            "time": hourly["time"][index],
            "temperature_2m_c": hourly["temperature_2m"][index],
            "relative_humidity_2m_percent": hourly["relative_humidity_2m"][index],
            "precipitation_probability_percent": hourly["precipitation_probability"][
                index
            ],
            "rain_mm": hourly["rain"][index],
            "cloud_cover_percent": hourly["cloud_cover"][index],
            "visibility_m": hourly["visibility"][index],
            "wind_speed_10m_mps": hourly["wind_speed_10m"][index],
            "wind_gusts_10m_mps": hourly["wind_gusts_10m"][index],
            "wind_direction_10m_deg": hourly["wind_direction_10m"][index],
        }
