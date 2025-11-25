import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List

import requests


# === 1. 러닝 코스 정의 ===

@dataclass
class Course:
    id: str
    name: str
    lat: float
    lon: float


COURSES = [
    {"name": "서호공원",         "lat": 37.280325,   "lon": 126.990396},
    {"name": "청소년문화센터",         "lat": 37.274248,   "lon": 127.034519},
    {"name": "광교호수공원",     "lat": 37.283439, "lon": 127.065989},
    {"name": "성균관대학교", "lat": 37.293788, "lon": 126.974365},
    {"name": "원천리천(신동)",           "lat": 37.248469, "lon": 1127.041965},
    {"name": "팔달산(수원화성, 행궁동)",     "lat": 37.277614, "lon": 127.010650},
    {"name": "수원천",     "lat": 37.266571, "lon": 127.015022},
    {"name": "광교산",           "lat": 37.328633, "lon": 127.038172},
    {"name": "수원월드컵경기장", "lat": 37.286545, "lon": 127.036871},
    {"name": "동탄여울공원",     "lat": 37.198689, "lon": 127.086609},
    {"name": "영흥숲공원",       "lat": 37.261067, "lon": 127.070470},
    {"name": "마중공원",         "lat": 37.236832, "lon": 127.020592},
]



# === 2. Open-Meteo KMA 호출 부분 (나중에 기상청 API로 교체 가능하도록 분리) ===

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"


def fetch_open_meteo_kma(course: Course) -> dict:
    """주어진 코스에 대해 Open-Meteo KMA seamless 모델로 현재/최근 3시간 데이터를 가져옵니다."""
    params = {
        "latitude": course.lat,
        "longitude": course.lon,
        "hourly": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "wind_speed_10m",
                "wind_direction_10m",
            ]
        ),
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "wind_speed_10m",
                "wind_direction_10m",
            ]
        ),
        "timezone": "Asia/Seoul",
        "models": "kma_seamless",
        "past_hours": 3,
        "forecast_hours": 0,
    }

    resp = requests.get(OPEN_METEO_BASE, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# === 3. 러닝용 정보로 가공 ===

def summarize_course_weather(course: Course, raw: dict) -> dict:
    current = raw["current"]
    hourly = raw["hourly"]

    # 최근 3시간 비 합계
    recent_rain = sum(hourly.get("rain", []) or [])

    # 노면 상태 배지
    if recent_rain == 0:
        wet_badge = {"text": "노면 건조", "level": "good"}
    elif recent_rain < 1:
        wet_badge = {"text": "약간 젖음", "level": "wet"}
    else:
        wet_badge = {"text": "많이 젖음", "level": "bad"}

    # 간단 러닝 코멘트 (나중에 더 정교하게 바꿀 수 있음)
    apparent = current["apparent_temperature"]
    wind_speed = current["wind_speed_10m"]

    if apparent < 0:
        temp_comment = "매우 춥습니다. 방한 장비 필수 ⚠️"
    elif apparent < 5:
        temp_comment = "쌀쌀합니다. 긴팔/바람막이 추천 🧥"
    elif apparent < 20:
        temp_comment = "러닝하기 좋은 온도 👍"
    else:
        temp_comment = "더울 수 있습니다. 수분 보충 필수 💧"

    if wind_speed < 2:
        wind_comment = "바람 거의 없음"
    elif wind_speed < 5:
        wind_comment = "약한 바람"
    else:
        wind_comment = "바람이 강한 편입니다. 체감온도 주의 🌬"

    comment = f"{temp_comment} · {wind_comment}"

    return {
        "id": course.id,
        "name": course.name,
        "updated_at": current["time"],  # ISO 문자열 (Asia/Seoul)
        "temperature": current["temperature_2m"],
        "apparent_temperature": apparent,
        "wind_speed": wind_speed,
        "wind_direction": current["wind_direction_10m"],
        "rain_now": current["rain"],
        "recent_rain_3h": recent_rain,
        "wet_badge": wet_badge,
        "comment": comment,
    }


# === 4. JSON 파일로 저장 ===

def main() -> None:
    results = []

    for course in COURSES:
        print(f"[INFO] Fetching weather for {course.name} ({course.lat}, {course.lon})")
        raw = fetch_open_meteo_kma(course)
        summary = summarize_course_weather(course, raw)
        results.append(summary)

    output = {
        "generated_at": datetime.now().isoformat(),
        "courses": results,
    }

    out_path = Path("data") / "suwon_weather.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[INFO] Saved {out_path} ({len(results)} courses)")


if __name__ == "__main__":
    main()
