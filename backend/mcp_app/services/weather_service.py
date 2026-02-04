from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta

from app.core.time import today_in_app_tz


def http_get_json(url: str, timeout_s: float = 8.0) -> dict:
    """Perform HTTP GET request and parse JSON response."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "rbac-mcp-app/1.0 (Open-Meteo client)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode_location(location: str) -> dict:
    """Geocode location name to get latitude, longitude, and other details."""
    q = urllib.parse.urlencode({"name": location, "count": 5, "language": "en", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{q}"
    data = http_get_json(url)

    results = data.get("results") or []
    if not results:
        raise ValueError(f"Location not found: {location}")

    loc_l = location.strip().lower()
    best = next((r for r in results if (r.get("name") or "").strip().lower() == loc_l), None)
    r0 = best or results[0]

    return {
        "name": r0.get("name"),
        "country": r0.get("country"),
        "admin1": r0.get("admin1"),
        "latitude": r0.get("latitude"),
        "longitude": r0.get("longitude"),
        "timezone": r0.get("timezone"),
    }


def validate_location_input(location: str) -> str:
    """Validate user-provided location string."""
    if not location or not location.strip():
        raise ValueError("Location is required (e.g. 'Prague' or 'Prague, CZ').")

    s = location.strip()
    bad = {
        "here", "my location", "current location", "near me", "me", "home", "local",
        "this city", "where i am", "where i’m", "where i'm",
    }
    if s.lower() in bad:
        raise ValueError(
            "Location must be a real place name (e.g. 'Prague' or 'Prague, CZ'), not a relative location like 'here'."
        )
    return s


def parse_when(when: str | None) -> dict:
    """
    Supported formats:
      - None / "now" / "current" -> current weather
      - "today" -> daily for today
      - "tomorrow" -> daily for tomorrow
      - "next_7_days" / "next7days" -> daily range
      - "next_14_days" / "next14days" -> daily range
      - "YYYY-MM-DD" -> daily for that date
      - "YYYY-MM-DD..YYYY-MM-DD" -> daily range
    """
    if not when:
        return {"mode": "current"}

    s = when.strip().lower()
    today = today_in_app_tz()

    if s in {"now", "current"}:
        return {"mode": "current"}

    if s == "today":
        return {"mode": "daily_range", "start": today, "end": today}

    if s == "tomorrow":
        d = today + timedelta(days=1)
        return {"mode": "daily_range", "start": d, "end": d}

    if s in {"next_7_days", "next7days"}:
        return {"mode": "daily_range", "start": today, "end": today + timedelta(days=6)}

    if s in {"next_14_days", "next14days"}:
        return {"mode": "daily_range", "start": today, "end": today + timedelta(days=13)}

    if ".." in s:
        a, b = s.split("..", 1)
        start = date.fromisoformat(a.strip())
        end = date.fromisoformat(b.strip())
        if end < start:
            raise ValueError("Invalid date range: end before start.")
        return {"mode": "daily_range", "start": start, "end": end}

    try:
        d = date.fromisoformat(s)
        return {"mode": "daily_range", "start": d, "end": d}
    except Exception:
        raise ValueError(
            "Unsupported 'when' format. Use one of: "
            "now|today|tomorrow|next_7_days|next_14_days|YYYY-MM-DD|YYYY-MM-DD..YYYY-MM-DD"
        )


def wmo_desc(code: int | None) -> str:
    """Get WMO weather description from weather code."""
    mapping = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    if code is None:
        return "Unknown"
    return mapping.get(code, f"Unknown (code {code})")


def read_weather(*, location: str, when: str | None, granularity: str = "auto") -> dict:
    """Read weather data for a given location and time."""
    location = validate_location_input(location)
    place = geocode_location(location)

    lat, lon = place["latitude"], place["longitude"]

    units = os.getenv("WEATHER_UNITS", "metric").strip().lower()
    if units not in ("metric", "imperial"):
        units = "metric"

    temperature_unit = "fahrenheit" if units == "imperial" else "celsius"
    windspeed_unit = "mph" if units == "imperial" else "kmh"
    precipitation_unit = "inch" if units == "imperial" else "mm"

    parsed = parse_when(when)
    mode = parsed["mode"]

    if granularity not in {"auto", "current", "daily", "hourly"}:
        raise ValueError("granularity must be one of: auto|current|daily|hourly")

    if granularity == "auto":
        want_current = (mode == "current")
        want_daily = (mode != "current")
    elif granularity == "current":
        want_current, want_daily = True, False
    elif granularity == "daily":
        want_current, want_daily = False, True
    else:
        raise ValueError("granularity=hourly not implemented yet")

    params: dict[str, str] = {
        "latitude": str(lat),
        "longitude": str(lon),
        "timezone": "auto",
        "temperature_unit": temperature_unit,
        "windspeed_unit": windspeed_unit,
        "precipitation_unit": precipitation_unit,
    }

    if want_current:
        params["current_weather"] = "true"

    if want_daily:
        params["daily"] = ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "wind_speed_10m_max",
            ]
        )

        today = today_in_app_tz()
        start: date = parsed["start"]
        end: date = parsed["end"]

        if end < today:
            raise ValueError("Forecast/current only; past dates not supported.")

        days_needed = (end - today).days + 1
        if days_needed > 16:
            raise ValueError("Range too large. Max supported is 16 days ahead.")
        params["forecast_days"] = str(max(1, days_needed))

    q = urllib.parse.urlencode(params)
    url = f"https://api.open-meteo.com/v1/forecast?{q}"
    data = http_get_json(url)

    out: dict[str, object] = {
        "query": {"location": location, "when": when, "granularity": granularity},
        "resolved_location": {
            "name": place["name"],
            "admin1": place["admin1"],
            "country": place["country"],
            "latitude": lat,
            "longitude": lon,
        },
        "units": {
            "system": units,
            "temperature_unit": temperature_unit,
            "windspeed_unit": windspeed_unit,
            "precipitation_unit": precipitation_unit,
        },
        "source": "open-meteo.com",
    }

    if want_current:
        current = data.get("current_weather") or {}
        code = current.get("weathercode")
        out["current"] = {
            "time": current.get("time"),
            "temperature": current.get("temperature"),
            "windspeed": current.get("windspeed"),
            "winddirection": current.get("winddirection"),
            "is_day": current.get("is_day"),
            "weather_code": code,
            "weather": wmo_desc(code),
        }

    if want_daily:
        daily = data.get("daily") or {}
        times = daily.get("time") or []

        today = today_in_app_tz()
        start = parsed["start"]
        end = parsed["end"]

        i0 = (start - today).days
        i1 = (end - today).days

        if i0 < 0 or i1 < 0 or i1 >= len(times):
            raise ValueError("Forecast data unavailable for requested dates.")

        def _slice(arr):
            return arr[i0 : i1 + 1] if isinstance(arr, list) else []

        codes = _slice(daily.get("weather_code") or [])

        out["daily"] = {
            "time": times[i0 : i1 + 1],
            "weather_code": codes,
            "weather": [wmo_desc(c) for c in codes],
            "temperature_2m_max": _slice(daily.get("temperature_2m_max") or []),
            "temperature_2m_min": _slice(daily.get("temperature_2m_min") or []),
            "precipitation_sum": _slice(daily.get("precipitation_sum") or []),
            "wind_speed_10m_max": _slice(daily.get("wind_speed_10m_max") or []),
        }

        daily_out = out["daily"]
        if isinstance(daily_out, dict) and isinstance(daily_out.get("time"), list) and len(daily_out["time"]) == 1:
            out["day"] = {
                "date": daily_out["time"][0],
                "weather": daily_out["weather"][0],
                "temp_max": daily_out["temperature_2m_max"][0],
                "temp_min": daily_out["temperature_2m_min"][0],
                "precipitation_sum": daily_out["precipitation_sum"][0],
                "wind_speed_max": daily_out["wind_speed_10m_max"][0],
            }

    return out
