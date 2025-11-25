import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import requests


# === 1. 러닝 코스 정의 ===


@dataclass
class Course:
    id: str
    name_ko: str
    name_en: str
    lat: float
    lon: float


COURSES: List[Course] = [
    Course(
        id="seoho-park",
        name_ko="서호공원",
        name_en="Seoho Park",
        lat=37.280325,
        lon=126.990396,
    ),
    Course(
        id="youth-center",
        name_ko="청소년문화센터",
        name_en="Youth Culture Center",
        lat=37.274248,
        lon=127.034519,
    ),
    Course(
        id="gwanggyo-lake-park",
        name_ko="광교호수공원",
        name_en="Gwanggyo Lake Park",
        lat=37.283439,
        lon=127.065989,
    ),
    Course(
        id="skku",
        name_ko="성균관대학교",
        name_en="Sungkyunkwan Univ. (Suwon)",
        lat=37.293788,
        lon=126.974365,
    ),
    Course(
        id="woncheon-stream-sindong",
        name_ko="원천리천(신동)",
        name_en="Woncheon Stream (Sindong)",
        lat=37.248469,
        lon=127.041965,
    ),
    Course(
        id="paldalsan-hwaseong",
        name_ko="팔달산(수원화성, 행궁동)",
        name_en="Paldalsan Fortress Area",
        lat=37.277614,
        lon=127.010650,
    ),
    Course(
        id="suwon-stream",
        name_ko="수원천",
        name_en="Suwoncheon Stream",
        lat=37.266571,
        lon=127.015022,
    ),
    Course(
        id="gwanggyo-mountain",
        name_ko="광교산",
        name_en="Gwanggyo Mountain",
        lat=37.328633,
        lon=127.038172,
    ),
    Course(
        id="suwon-worldcup",
        name_ko="수원월드컵경기장",
        name_en="Suwon World Cup Stadium",
        lat=37.286545,
        lon=127.036871,
    ),
    Course(
        id="dongtan-yeoul-park",
        name_ko="동탄여울공원",
        name_en="Dongtan Yeoul Park",
        lat=37.198689,
        lon=127.086609,
    ),
    Course(
        id="yeongheung-forest-park",
        name_ko="영흥숲공원",
        name_en="Yeongheung Forest Park",
        lat=37.261067,
        lon=127.070470,
    ),
    Course(
        id="majung-park",
        name_ko="마중공원",
        name_en="Majung Park",
        lat=37.236832,
        lon=127.020592,
    ),
]


# === 2. Open-Meteo KMA 호출 ===

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"


def fetch_open_meteo_kma(course: Course) -> Dict[str, Any]:
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


# === 3. 러닝용으로 요약 + 한/영 텍스트 생성 ===


def summarize_course_weather(course: Course, raw: Dict[str, Any]) -> Dict[str, Any]:
    current = raw["current"]
    hourly = raw["hourly"]

    # 최근 3시간 비 합계
    recent_rain = float(sum(hourly.get("rain", []) or []))

    # --- 노면 상태 배지 (한/영) ---
    if recent_rain == 0:
        wet_badge = {
            "level": "good",
            "text_ko": "노면 건조",
            "text_en": "Dry surface",
        }
        wet_tag_ko = "노면 건조"
        wet_tag_en = "Dry surface"
        wet_comment_ko = "노면이 건조해서 미끄럼 위험이 적습니다."
        wet_comment_en = "Dry surface, low risk of slipping."
    elif recent_rain < 0.5:
        wet_badge = {
            "level": "wet",
            "text_ko": "살짝 젖음",
            "text_en": "Slightly wet",
        }
        wet_tag_ko = "살짝 젖음"
        wet_tag_en = "Slightly wet"
        wet_comment_ko = "노면이 살짝 젖어 있습니다. 코너링 시 미끄럼에만 주의하세요."
        wet_comment_en = "Surface is slightly wet. Be careful when cornering."
    elif recent_rain < 2:
        wet_badge = {
            "level": "wet",
            "text_ko": "젖은 노면",
            "text_en": "Wet surface",
        }
        wet_tag_ko = "젖은 노면"
        wet_tag_en = "Wet surface"
        wet_comment_ko = "노면이 젖어 있습니다. 속도를 너무 올리기보다는 안정적으로 뛰는 것을 추천합니다."
        wet_comment_en = "Surface is wet. Better to run safely rather than pushing the pace."
    elif recent_rain < 5:
        wet_badge = {
            "level": "bad",
            "text_ko": "많이 젖음",
            "text_en": "Very wet",
        }
        wet_tag_ko = "많이 젖음"
        wet_tag_en = "Very wet"
        wet_comment_ko = "노면이 꽤 젖어 있습니다. 물웅덩이와 미끄러운 구간을 조심하세요."
        wet_comment_en = "Surface is very wet. Watch out for puddles and slippery spots."
    else:
        wet_badge = {
            "level": "bad",
            "text_ko": "매우 젖음",
            "text_en": "Extremely wet",
        }
        wet_tag_ko = "매우 젖음"
        wet_tag_en = "Extremely wet"
        wet_comment_ko = "노면이 매우 젖어 있고 물웅덩이가 많을 수 있습니다. 안정 위주의 조심 러닝을 추천합니다."
        wet_comment_en = "Surface is extremely wet with many puddles. Run conservatively for safety."

    # --- 온도 점수/코멘트 (한/영) ---
    apparent = float(current["apparent_temperature"])

    if apparent < -5:
        temp_score = 20
        temp_tag_ko = "매우 춥음"
        temp_tag_en = "Very cold"
        temp_comment_ko = "매우 춥습니다. 두꺼운 장갑·모자·넥워머 등 방한 장비가 필요합니다."
        temp_comment_en = "Very cold. Wear warm gear such as thick gloves, hat, and neck warmer."
    elif apparent < 0:
        temp_score = 40
        temp_tag_ko = "춥다"
        temp_tag_en = "Cold"
        temp_comment_ko = "상당히 쌀쌀합니다. 긴팔+긴바지, 바람막이 착용을 추천합니다."
        temp_comment_en = "Quite chilly. Long sleeves, tights, and a light windbreaker are recommended."
    elif apparent < 5:
        temp_score = 60
        temp_tag_ko = "조금 쌀쌀함"
        temp_tag_en = "A bit chilly"
        temp_comment_ko = "쌀쌀하지만 러닝하기 괜찮은 온도입니다. 얇은 겹겹이 레이어링이 좋습니다."
        temp_comment_en = "A bit chilly but fine for running. Light layering works well."
    elif apparent < 15:
        temp_score = 95
        temp_tag_ko = "러닝 최적"
        temp_tag_en = "Optimal"
        temp_comment_ko = "러닝하기 아주 좋은 온도입니다. 평소보다 페이스를 조금 올려도 괜찮습니다."
        temp_comment_en = "Perfect temperature for running. You can slightly increase your usual pace."
    elif apparent < 20:
        temp_score = 85
        temp_tag_ko = "적당함"
        temp_tag_en = "Comfortable"
        temp_comment_ko = "적당한 온도입니다. 평소 복장에 얇은 상·하의 정도면 충분합니다."
        temp_comment_en = "Comfortable temperature. Usual outfit with light layers is enough."
    elif apparent < 24:
        temp_score = 70
        temp_tag_ko = "조금 더움"
        temp_tag_en = "Slightly warm"
        temp_comment_ko = "조금 덥게 느껴질 수 있습니다. 밝은색·통풍 잘 되는 옷을 추천합니다."
        temp_comment_en = "Might feel slightly warm. Wear light, breathable, bright-colored clothes."
    elif apparent < 28:
        temp_score = 50
        temp_tag_ko = "더움"
        temp_tag_en = "Warm"
        temp_comment_ko = "덥습니다. 강도 높은 훈련은 피하고 자주 수분을 섭취하세요."
        temp_comment_en = "Warm. Avoid high-intensity workouts and hydrate frequently."
    else:
        temp_score = 30
        temp_tag_ko = "매우 더움"
        temp_tag_en = "Very hot"
        temp_comment_ko = "매우 덥습니다. 가능한 한 짧게, 강도 낮게 달리거나 실내 러닝을 고려하세요."
        temp_comment_en = "Very hot. Consider shorter, easier runs or indoor running."

    # --- 바람 점수/코멘트 (한/영) ---
    wind_speed = float(current["wind_speed_10m"])
    wind_dir = float(current["wind_direction_10m"])

    if wind_speed < 2:
        wind_score = 100
        wind_tag_ko = "바람 거의 없음"
        wind_tag_en = "Calm"
        wind_comment_ko = "바람이 거의 없어 페이스 유지에 유리합니다."
        wind_comment_en = "Almost no wind, good for maintaining pace."
    elif wind_speed < 4:
        wind_score = 80
        wind_tag_ko = "약한 바람"
        wind_tag_en = "Light breeze"
        wind_comment_ko = "약한 바람입니다. 러닝에 큰 지장은 없습니다."
        wind_comment_en = "Light breeze, little impact on running."
    elif wind_speed < 6:
        wind_score = 60
        wind_tag_ko = "다소 강한 바람"
        wind_tag_en = "Moderate wind"
        wind_comment_ko = "바람이 다소 있어 체감온도가 낮게 느껴질 수 있습니다."
        wind_comment_en = "Moderate wind. It may feel cooler than the actual temperature."
    elif wind_speed < 8:
        wind_score = 40
        wind_tag_ko = "강한 바람"
        wind_tag_en = "Strong wind"
        wind_comment_ko = "바람이 강한 편입니다. 맞바람 구간에서는 페이스 조절이 필요합니다."
        wind_comment_en = "Strong wind. Adjust your pace in headwind sections."
    else:
        wind_score = 25
        wind_tag_ko = "매우 강한 바람"
        wind_tag_en = "Very strong wind"
        wind_comment_ko = "바람이 매우 강합니다. 체감온도가 크게 내려가고 피로가 빨리 쌓일 수 있습니다."
        wind_comment_en = "Very strong wind. It feels much colder and fatigue may build up faster."

    # --- 종합 러닝 지수 ---
    run_score = round(
        temp_score * 0.5 + wind_score * 0.3 + (100 if recent_rain == 0 else 70) * 0.2
    )
    run_score = max(0, min(100, run_score))

    if run_score >= 80:
        advice_short_ko = "러닝하기 아주 좋은 컨디션입니다 😄"
        advice_short_en = "Great conditions for running 😄"
    elif run_score >= 60:
        advice_short_ko = "러닝하기 무난한 컨디션입니다 🙂"
        advice_short_en = "Decent conditions for running 🙂"
    elif run_score >= 40:
        advice_short_ko = "주의하면서 뛰면 괜찮은 컨디션입니다 ⚠️"
        advice_short_en = "Okay to run with some caution ⚠️"
    else:
        advice_short_ko = "러닝 강도/시간을 줄이는 것을 추천합니다 🚨"
        advice_short_en = "Consider reducing intensity or duration 🚨"

    advice_detail_ko = " ".join(
        [
            temp_comment_ko,
            wind_comment_ko,
            wet_comment_ko,
            "컨디션에 따라 강도를 조절하고, 평소보다 몸 상태를 더 자주 점검해 주세요.",
        ]
    )
    advice_detail_en = " ".join(
        [
            temp_comment_en,
            wind_comment_en,
            wet_comment_en,
            "Adjust intensity based on how you feel and check your condition more often than usual.",
        ]
    )

    return {
        "id": course.id,
        "name_ko": course.name_ko,
        "name_en": course.name_en,
        "name": course.name_ko,
        "updated_at": current["time"],
        "temperature": float(current["temperature_2m"]),
        "apparent_temperature": apparent,
        "wind_speed": wind_speed,
        "wind_direction": wind_dir,
        "rain_now": float(current["rain"]),
        "recent_rain_3h": recent_rain,
        "wet_badge": wet_badge,
        "run_score": run_score,
        "temp_score": temp_score,
        "wind_score": wind_score,
        "wet_score": None,
        # ✅ 태그에는 온도 + 바람만 넣고, 노면은 위 배지에서만 표현
        "tags_ko": [temp_tag_ko, wind_tag_ko],
        "tags_en": [temp_tag_en, wind_tag_en],
        "advice_short_ko": advice_short_ko,
        "advice_short_en": advice_short_en,
        "advice_detail_ko": advice_detail_ko,
        "advice_detail_en": advice_detail_en,
    }



# === 4. JSON 파일로 저장 ===


def main() -> None:
    results: List[Dict[str, Any]] = []

    for course in COURSES:
        print(f"[INFO] Fetching weather for {course.name_ko} ({course.lat}, {course.lon})")
        raw = fetch_open_meteo_kma(course)
        summary = summarize_course_weather(course, raw)
        results.append(summary)

    output = {
        "generated_at": datetime.now().isoformat(),
        "courses": results,
    }

    out_path = Path("data") / "suwon_weather.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[INFO] Saved {out_path} ({len(results)} courses)")


if __name__ == "__main__":
    main()
