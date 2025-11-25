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


COURSES: List[Course] = [
    Course(
        id="seoho-park",
        name="서호공원",
        lat=37.280325,
        lon=126.990396,
    ),
    Course(
        id="youth-center",
        name="청소년문화센터",
        lat=37.274248,
        lon=127.034519,
    ),
    Course(
        id="gwanggyo-lake-park",
        name="광교호수공원",
        lat=37.283439,
        lon=127.065989,
    ),
    Course(
        id="skku",
        name="성균관대학교",
        lat=37.293788,
        lon=126.974365,
    ),
    Course(
        id="woncheon-stream-sindong",
        name="원천리천(신동)",
        lat=37.248469,
        lon=127.041965,  # 1127 → 127로 수정
    ),
    Course(
        id="paldalsan-hwaseong",
        name="팔달산(수원화성, 행궁동)",
        lat=37.277614,
        lon=127.010650,
    ),
    Course(
        id="suwon-stream",
        name="수원천",
        lat=37.266571,
        lon=127.015022,
    ),
    Course(
        id="gwanggyo-mountain",
        name="광교산",
        lat=37.328633,
        lon=127.038172,
    ),
    Course(
        id="suwon-worldcup",
        name="수원월드컵경기장",
        lat=37.286545,
        lon=127.036871,
    ),
    Course(
        id="dongtan-yeoul-park",
        name="동탄여울공원",
        lat=37.198689,
        lon=127.086609,
    ),
    Course(
        id="yeongheung-forest-park",
        name="영흥숲공원",
        lat=37.261067,
        lon=127.070470,
    ),
    Course(
        id="majung-park",
        name="마중공원",
        lat=37.236832,
        lon=127.020592,
    ),
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

    # ==========================
    # 1) 온도 점수/코멘트
    # ==========================
    apparent = current["apparent_temperature"]
    temp_score: int
    temp_tag: str
    temp_comment: str

    if apparent < -5:
        temp_score = 20
        temp_tag = "매우 춥음"
        temp_comment = "매우 춥습니다. 두꺼운 장갑·모자·넥워머 등 방한 장비가 필요합니다."
    elif apparent < 0:
        temp_score = 40
        temp_tag = "춥다"
        temp_comment = "상당히 쌀쌀합니다. 긴팔+긴바지, 바람막이 착용을 추천합니다."
    elif apparent < 5:
        temp_score = 60
        temp_tag = "조금 쌀쌀함"
        temp_comment = "쌀쌀하지만 러닝하기 괜찮은 온도입니다. 얇은 겹겹이 레이어링이 좋습니다."
    elif apparent < 15:
        temp_score = 95
        temp_tag = "러닝 최적"
        temp_comment = "러닝하기 아주 좋은 온도입니다. 평소보다 페이스를 조금 올려도 괜찮습니다."
    elif apparent < 20:
        temp_score = 85
        temp_tag = "적당함"
        temp_comment = "적당한 온도입니다. 평소 복장에 얇은 상·하의 정도면 충분합니다."
    elif apparent < 24:
        temp_score = 70
        temp_tag = "조금 더움"
        temp_comment = "조금 덥게 느껴질 수 있습니다. 밝은색·통풍 잘 되는 옷을 추천합니다."
    elif apparent < 28:
        temp_score = 50
        temp_tag = "더움"
        temp_comment = "덥습니다. 강도 높은 훈련은 피하고 자주 수분을 섭취하세요."
    else:
        temp_score = 30
        temp_tag = "매우 더움"
        temp_comment = "매우 덥습니다. 가능한 한 짧게, 강도 낮게 달리거나 실내 러닝을 고려하세요."

    # ==========================
    # 2) 바람 점수/코멘트
    # ==========================
    wind_speed = current["wind_speed_10m"]
    wind_dir = current["wind_direction_10m"]

    if wind_speed < 2:
        wind_score = 100
        wind_tag = "바람 거의 없음"
        wind_comment = "바람이 거의 없어 페이스 유지에 유리합니다."
    elif wind_speed < 4:
        wind_score = 80
        wind_tag = "약한 바람"
        wind_comment = "약한 바람입니다. 러닝에 큰 지장은 없습니다."
    elif wind_speed < 6:
        wind_score = 60
        wind_tag = "다소 강한 바람"
        wind_comment = "바람이 다소 있어 체감온도가 낮게 느껴질 수 있습니다."
    elif wind_speed < 8:
        wind_score = 40
        wind_tag = "강한 바람"
        wind_comment = "바람이 강한 편입니다. 맞바람 구간에서는 페이스 조절이 필요합니다."
    else:
        wind_score = 25
        wind_tag = "매우 강한 바람"
        wind_comment = "바람이 매우 강합니다. 체감온도가 내려가고 피로가 빨리 쌓일 수 있습니다."

    # ==========================
    # 3) 노면 점수/코멘트
    # ==========================
    if recent_rain == 0:
        wet_score = 100
        wet_tag = "노면 건조"
        wet_comment = "노면이 건조해서 미끄럼 위험이 적습니다."
    elif recent_rain < 0.5:
        wet_score = 80
        wet_tag = "살짝 젖음"
        wet_comment = "노면이 살짝 젖어 있습니다. 코너링 시 미끄럼에만 주의하세요."
    elif recent_rain < 2:
        wet_score = 60
        wet_tag = "젖은 노면"
        wet_comment = "노면이 젖어 있습니다. 속도를 너무 올리기보다는 안정적으로 뛰는 것을 추천합니다."
    elif recent_rain < 5:
        wet_score = 40
        wet_tag = "많이 젖은 노면"
        wet_comment = "노면이 꽤 젖어 있습니다. 배수 안 되는 구간에서는 물웅덩이를 주의하세요."
    else:
        wet_score = 25
        wet_tag = "매우 젖음"
        wet_comment = "노면이 매우 젖어 있고 물웅덩이가 많을 수 있습니다. 안정 위주의 조심 러닝을 추천합니다."

    # ==========================
    # 4) 종합 러닝 지수 & 한 줄 요약
    # ==========================
    run_score = round(temp_score * 0.5 + wind_score * 0.3 + wet_score * 0.2)

    if run_score >= 80:
        advice_short = "러닝하기 아주 좋은 컨디션입니다 😄"
    elif run_score >= 60:
        advice_short = "러닝하기 무난한 컨디션입니다 🙂"
    elif run_score >= 40:
        advice_short = "주의하면서 뛰면 괜찮은 컨디션입니다 ⚠️"
    else:
        advice_short = "러닝 강도/시간을 줄이는 것을 추천합니다 🚨"

    # 상세 조언: 온도/바람/노면 코멘트를 합치고, 기본 안전 문구 추가
    advice_detail = " ".join(
        [
            temp_comment,
            wind_comment,
            wet_comment,
            "컨디션에 따라 강도를 조절하고, 평소보다 몸 상태를 더 자주 점검해 주세요.",
        ]
    )

    # 태그 리스트 (UI에서 작은 칩 형태로 보여주기 좋음)
    tags = [temp_tag, wind_tag, wet_tag]

    return {
        "id": course.id,
        "name": course.name,
        "updated_at": current["time"],  # ISO 문자열 (Asia/Seoul)
        "temperature": current["temperature_2m"],
        "apparent_temperature": apparent,
        "wind_speed": wind_speed,
        "wind_direction": wind_dir,
        "rain_now": current["rain"],
        "recent_rain_3h": recent_rain,
        "wet_badge": wet_badge,
        "run_score": run_score,
        "temp_score": temp_score,
        "wind_score": wind_score,
        "wet_score": wet_score,
        "tags": tags,
        "advice_short": advice_short,
        "advice_detail": advice_detail,
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
