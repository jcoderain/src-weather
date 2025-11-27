import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

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


# === 2. Open-Meteo KMA & Air Quality 호출 ===

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_BASE = "https://air-quality-api.open-meteo.com/v1/air-quality"


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
        # wind_speed_unit 기본값은 km/h 이므로 아래에서 m/s로 변환
    }

    resp = requests.get(OPEN_METEO_BASE, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_air_quality(course: Course) -> Optional[Dict[str, Any]]:
    """Open-Meteo Air Quality API에서 PM10 / PM2.5 현재값을 가져옵니다."""
    params = {
        "latitude": course.lat,
        "longitude": course.lon,
        "current": "pm10,pm2_5",
        "timezone": "Asia/Seoul",
    }
    resp = requests.get(AIR_QUALITY_BASE, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# === 3. 러닝용으로 요약 + 한/영 텍스트 생성 ===


def summarize_course_weather(
    course: Course,
    raw_weather: Dict[str, Any],
    raw_air: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = raw_weather["current"]
    hourly = raw_weather["hourly"]

    # -----------------------------
    # 1) 강수/노면 상태 (비 + 눈)
    # -----------------------------
    current_rain = float(current.get("rain", 0.0))              # mm/h
    current_precip = float(current.get("precipitation", 0.0))   # mm/h (비+눈)
    current_snow = max(current_precip - current_rain, 0.0)      # 눈/진눈깨비 추정

    recent_rain_list = hourly.get("rain", []) or []
    recent_precip_list = hourly.get("precipitation", []) or []
    recent_rain = float(sum(recent_rain_list))                  # 최근 3시간 비
    recent_precip = float(sum(recent_precip_list))              # 최근 3시간 비+눈
    recent_snow = max(recent_precip - recent_rain, 0.0)         # 최근 3시간 눈

    # surface_score: 0~100
    # wet_badge: { level: good/wet/bad, text_ko/text_en }
    # wet_tag_*: 태그용, wet_comment_*: 설명문용
    if recent_precip == 0 and current_precip == 0:
        surface_score = 100
        wet_badge = {
            "level": "good",
            "text_ko": "노면 건조",
            "text_en": "Dry surface",
        }
        wet_tag_ko = "노면 건조"
        wet_tag_en = "Dry surface"
        wet_comment_ko = "노면이 건조해서 미끄럼 위험이 적습니다."
        wet_comment_en = "Surface is dry with low risk of slipping."
    else:
        # 눈 많은 날 / 조금 쌓인 날 / 비 위주인 날 구분
        heavy_snow = (recent_snow >= 6.0) or (current_snow >= 4.0)
        light_snow = (recent_snow >= 1.0) or (current_snow >= 0.5)

        if heavy_snow:
            surface_score = 0
            wet_badge = {
                "level": "bad",
                "text_ko": "눈 많이 쌓임",
                "text_en": "Heavy snow/ice",
            }
            wet_tag_ko = "눈 많이 쌓임"
            wet_tag_en = "Heavy snow"
            wet_comment_ko = (
                "눈이 많이 쌓이거나 얼음 구간이 많아 매우 미끄럽습니다. "
                "실외 러닝보다는 실내 러닝이나 휴식을 권장합니다."
            )
            wet_comment_en = (
                "There is heavy snow or many icy sections, making it very slippery. "
                "Indoor running or rest is recommended instead of outdoor running."
            )
        elif light_snow:
            surface_score = 40
            wet_badge = {
                "level": "bad",
                "text_ko": "눈 조금 쌓임",
                "text_en": "Some snow on surface",
            }
            wet_tag_ko = "눈 조금 쌓임"
            wet_tag_en = "Some snow"
            wet_comment_ko = (
                "노면에 눈이 조금 쌓이거나 녹은 물이 있어 미끄러울 수 있습니다. "
                "가능하면 트레일 러닝화나 접지 좋은 러닝화를 착용해 주세요."
            )
            wet_comment_en = (
                "Some snow or meltwater on the surface may cause slipperiness. "
                "Trail running shoes or shoes with good grip are recommended."
            )
        else:
            # 비 위주로 판단
            if recent_precip < 2.0 and current_precip < 1.0:
                surface_score = 80
                wet_badge = {
                    "level": "wet",
                    "text_ko": "살짝 젖음",
                    "text_en": "Slightly wet",
                }
                wet_tag_ko = "살짝 젖음"
                wet_tag_en = "Slightly wet"
                wet_comment_ko = (
                    "노면이 살짝 젖어 있습니다. 코너링이나 브레이킹 시에만 "
                    "미끄럼에 주의하면 러닝에 큰 지장은 없습니다."
                )
                wet_comment_en = (
                    "The surface is slightly wet. As long as you are careful "
                    "when cornering or braking, running should be fine."
                )
            elif recent_rain < 10.0 or current_rain < 4.0:
                surface_score = 50
                wet_badge = {
                    "level": "wet",
                    "text_ko": "젖은 노면",
                    "text_en": "Wet surface",
                }
                wet_tag_ko = "젖은 노면"
                wet_tag_en = "Wet surface"
                wet_comment_ko = (
                    "노면이 젖어 있어 미끄러운 구간이 있을 수 있습니다. "
                    "페이스를 약간 낮추고, 특히 내리막·코너 구간에서 발 조심해 주세요."
                )
                wet_comment_en = (
                    "The surface is wet, and some sections may be slippery. "
                    "Slightly lower your pace and take extra care on downhills and corners."
                )
            elif recent_rain < 20.0 or current_rain < 8.0:
                surface_score = 20
                wet_badge = {
                    "level": "bad",
                    "text_ko": "많이 젖음",
                    "text_en": "Very wet",
                }
                wet_tag_ko = "많이 젖음"
                wet_tag_en = "Very wet"
                wet_comment_ko = (
                    "비가 많이 내려 노면이 꽤 젖어 있고 물웅덩이가 많을 수 있습니다. "
                    "발이 쉽게 젖고 미끄러울 수 있으니 강도 높은 훈련은 피하는 것이 좋습니다."
                )
                wet_comment_en = (
                    "It has rained a lot, so the surface is very wet with many puddles. "
                    "Your feet may get soaked and it can be slippery, so avoid high-intensity workouts."
                )
            else:
                surface_score = 0
                wet_badge = {
                    "level": "bad",
                    "text_ko": "매우 젖음",
                    "text_en": "Extremely wet",
                }
                wet_tag_ko = "매우 젖음"
                wet_tag_en = "Extremely wet"
                wet_comment_ko = (
                    "폭우 수준의 비가 내리고 있어 노면 상태가 매우 좋지 않습니다. "
                    "실외 러닝보다는 실내 러닝이나 휴식을 권장합니다."
                )
                wet_comment_en = (
                    "Rain is at a heavy or torrential level, making the surface very poor. "
                    "Indoor running or rest is recommended instead of outdoor running."
                )

    # -----------------------------
    # 2) 온도 점수 (체감온도, 한국 기준)
    # -----------------------------
    apparent = float(current["apparent_temperature"])

    if apparent <= -15:
        temp_score = 5
        temp_tag_ko = "매우 춥음"
        temp_tag_en = "Very cold"
        temp_comment_ko = (
            "매우 춥습니다. 노출 부위를 최소화하고 두꺼운 장갑, 모자, 넥워머 등 "
            "충분한 방한 장비가 필요합니다."
        )
        temp_comment_en = (
            "It is extremely cold. Minimize exposed skin and wear warm gear such as gloves, hat, and neck warmer."
        )
    elif apparent < -10:
        temp_score = 15
        temp_tag_ko = "매우 춥음"
        temp_tag_en = "Very cold"
        temp_comment_ko = (
            "상당히 강한 한기입니다. 장시간 야외 러닝은 추천하지 않으며, "
            "짧고 가벼운 러닝 위주로 가져가는 편이 안전합니다."
        )
        temp_comment_en = (
            "Very cold. Long outdoor runs are not recommended; stick to shorter, lighter runs if you go out."
        )
    elif apparent < -5:
        temp_score = 30
        temp_tag_ko = "춥다"
        temp_tag_en = "Cold"
        temp_comment_ko = (
            "꽤 춥습니다. 긴팔+긴바지에 방풍 자켓을 더해 주는 것이 좋습니다."
        )
        temp_comment_en = (
            "It is quite cold. Long sleeves, tights, and a windproof jacket are recommended."
        )
    elif apparent < 0:
        temp_score = 45
        temp_tag_ko = "쌀쌀함"
        temp_tag_en = "Chilly"
        temp_comment_ko = (
            "쌀쌀한 편입니다. 긴팔, 긴바지 또는 얇은 레이어링을 추천합니다."
        )
        temp_comment_en = (
            "Chilly conditions. Long sleeves and tights or light layering are recommended."
        )
    elif apparent < 5:
        temp_score = 60
        temp_tag_ko = "조금 쌀쌀함"
        temp_tag_en = "A bit chilly"
        temp_comment_ko = (
            "조금 쌀쌀하지만 러닝하기 좋은 편입니다. 가벼운 레이어링이 잘 어울립니다."
        )
        temp_comment_en = (
            "A bit chilly but good for running. Light layering works well."
        )
    elif apparent < 12:
        temp_score = 100
        temp_tag_ko = "러닝 최적"
        temp_tag_en = "Optimal"
        temp_comment_ko = (
            "러닝하기 최적의 온도입니다. 평소보다 페이스를 조금 올려도 부담이 적습니다."
        )
        temp_comment_en = (
            "Perfect temperature for running. You can slightly increase your usual pace."
        )
    elif apparent < 18:
        temp_score = 90
        temp_tag_ko = "적당함"
        temp_tag_en = "Comfortable"
        temp_comment_ko = (
            "적당한 온도입니다. 평소 복장으로 무리 없이 러닝하기 좋습니다."
        )
        temp_comment_en = (
            "Comfortable temperature. Your usual outfit should be fine for running."
        )
    elif apparent < 22:
        temp_score = 75
        temp_tag_ko = "다소 따뜻함"
        temp_tag_en = "Slightly warm"
        temp_comment_ko = (
            "다소 따뜻한 편입니다. 통풍 잘 되는 옷과 충분한 수분 섭취를 추천합니다."
        )
        temp_comment_en = (
            "Slightly warm. Wear breathable clothes and make sure to hydrate."
        )
    elif apparent < 26:
        temp_score = 55
        temp_tag_ko = "조금 더움"
        temp_tag_en = "Slightly hot"
        temp_comment_ko = (
            "조금 더운 편입니다. 강도 높은 훈련보다는 적당한 강도의 러닝이 좋습니다."
        )
        temp_comment_en = (
            "Slightly hot. Moderate intensity runs are better than hard workouts."
        )
    elif apparent < 29:
        temp_score = 40
        temp_tag_ko = "더움"
        temp_tag_en = "Warm"
        temp_comment_ko = (
            "더운 편입니다. 강도를 낮추고 자주 수분을 섭취하는 것이 좋습니다."
        )
        temp_comment_en = (
            "Warm conditions. Lower your intensity and hydrate frequently."
        )
    elif apparent < 31:
        temp_score = 25
        temp_tag_ko = "덥다"
        temp_tag_en = "Hot"
        temp_comment_ko = (
            "상당히 덥습니다. 장거리나 고강도 러닝은 피하고, 그늘 위주 코스를 추천합니다."
        )
        temp_comment_en = (
            "It is quite hot. Avoid long or high-intensity runs and seek shaded routes."
        )
    elif apparent < 33:
        temp_score = 10
        temp_tag_ko = "매우 더움"
        temp_tag_en = "Very hot"
        temp_comment_ko = (
            "매우 덥습니다. 짧고 가벼운 러닝이 아니면 실외 러닝을 피하는 편이 안전합니다."
        )
        temp_comment_en = (
            "Very hot. Unless it is a short and easy run, it is safer to avoid outdoor running."
        )
    else:
        temp_score = 0
        temp_tag_ko = "매우 더움"
        temp_tag_en = "Very hot"
        temp_comment_ko = (
            "위험할 정도로 덥습니다. 실외 러닝은 권장하지 않으며, 실내 운동이나 휴식을 추천합니다."
        )
        temp_comment_en = (
            "Dangerously hot. Outdoor running is not recommended; consider indoor exercise or rest."
        )

    # -----------------------------
    # 3) 바람 점수 (m/s 기준)
    # -----------------------------
    raw_wind_speed_kmh = float(current["wind_speed_10m"])
    wind_speed = raw_wind_speed_kmh / 3.6  # km/h → m/s
    wind_dir = float(current["wind_direction_10m"])

    if wind_speed < 2.0:
        wind_score = 100
        wind_tag_ko = "바람 거의 없음"
        wind_tag_en = "Calm"
        wind_comment_ko = "바람이 거의 없어 페이스 유지에 유리합니다."
        wind_comment_en = "Almost no wind, good for maintaining your pace."
    elif wind_speed < 4.0:
        wind_score = 80
        wind_tag_ko = "약한 바람"
        wind_tag_en = "Light breeze"
        wind_comment_ko = "약한 바람으로 러닝에 큰 지장은 없습니다."
        wind_comment_en = "Light breeze with little impact on running."
    elif wind_speed < 6.0:
        wind_score = 60
        wind_tag_ko = "다소 강한 바람"
        wind_tag_en = "Moderate wind"
        wind_comment_ko = (
            "바람이 다소 있어 체감온도가 조금 낮게 느껴질 수 있습니다."
        )
        wind_comment_en = (
            "Moderate wind. It may feel a bit cooler than the actual temperature."
        )
    elif wind_speed < 8.0:
        wind_score = 40
        wind_tag_ko = "강한 바람"
        wind_tag_en = "Strong wind"
        wind_comment_ko = (
            "바람이 강한 편입니다. 맞바람 구간에서는 페이스를 낮추는 것이 좋습니다."
        )
        wind_comment_en = (
            "Strong wind. Lower your pace in headwind sections."
        )
    else:
        wind_score = 25
        wind_tag_ko = "매우 강한 바람"
        wind_tag_en = "Very strong wind"
        wind_comment_ko = (
            "바람이 매우 강합니다. 체감온도가 크게 내려가고 피로가 빨리 쌓일 수 있습니다."
        )
        wind_comment_en = (
            "Very strong wind. It feels much colder and fatigue may build up faster."
        )

    # -----------------------------
    # 4) 공기질 (PM10 / PM2.5) + 패널티 팩터
    # -----------------------------
    pm10 = None
    pm25 = None
    air_score = 90  # 기본값: "거의 문제 없음" 정도
    air_tag_ko = None
    air_tag_en = None
    air_comment_ko = ""
    air_comment_en = ""

    if raw_air is not None and "current" in raw_air:
        current_air = raw_air["current"]
        if current_air.get("pm10") is not None:
            pm10 = float(current_air["pm10"])
        if current_air.get("pm2_5") is not None:
            pm25 = float(current_air["pm2_5"])

    pm_for_score = pm25 if pm25 is not None else pm10

    if pm_for_score is not None:
        # PM2.5 우선 기준
        if pm25 is not None:
            v = pm25
            if v <= 15:
                air_score = 100
                air_tag_ko = "공기질 좋음"
                air_tag_en = "Good air"
                air_comment_ko = "공기질이 좋아 러닝에 거의 지장이 없습니다."
                air_comment_en = "Air quality is good with little impact on running."
            elif v <= 35:
                air_score = 80
                air_tag_ko = "공기질 보통"
                air_tag_en = "Moderate air"
                air_comment_ko = (
                    "공기질이 보통 수준입니다. 미세먼지에 민감하다면 마스크를 고려해도 좋습니다."
                )
                air_comment_en = (
                    "Air quality is moderate. Consider a mask if you are sensitive to fine dust."
                )
            elif v <= 75:
                air_score = 55
                air_tag_ko = "공기질 나쁨"
                air_tag_en = "Bad air"
                air_comment_ko = (
                    "공기질이 좋지 않습니다. 호흡기·심혈관 질환이 있다면 강한 야외 러닝은 피하는 것이 좋습니다."
                )
                air_comment_en = (
                    "Air quality is poor. If you have respiratory or heart issues, avoid intense outdoor running."
                )
            else:
                air_score = 30
                air_tag_ko = "공기질 매우 나쁨"
                air_tag_en = "Very bad air"
                air_comment_ko = (
                    "공기질이 매우 나쁩니다. 가능하면 실외 러닝 대신 실내 운동이나 휴식을 권장합니다."
                )
                air_comment_en = (
                    "Air quality is very poor. Indoor exercise or rest is recommended instead of outdoor running."
                )
        # PM10만 있을 때
        else:
            v = pm10
            if v <= 30:
                air_score = 100
                air_tag_ko = "공기질 좋음"
                air_tag_en = "Good air"
                air_comment_ko = "공기질이 좋아 러닝에 거의 지장이 없습니다."
                air_comment_en = "Air quality is good with little impact on running."
            elif v <= 80:
                air_score = 80
                air_tag_ko = "공기질 보통"
                air_tag_en = "Moderate air"
                air_comment_ko = (
                    "공기질이 보통 수준입니다. 미세먼지에 민감하다면 마스크를 고려해도 좋습니다."
                )
                air_comment_en = (
                    "Air quality is moderate. Consider a mask if you are sensitive to fine dust."
                )
            elif v <= 150:
                air_score = 55
                air_tag_ko = "공기질 나쁨"
                air_tag_en = "Bad air"
                air_comment_ko = (
                    "공기질이 좋지 않습니다. 장시간·고강도 야외 러닝은 피하는 것이 좋습니다."
                )
                air_comment_en = (
                    "Air quality is poor. Avoid long or intense outdoor runs."
                )
            else:
                air_score = 30
                air_tag_ko = "공기질 매우 나쁨"
                air_tag_en = "Very bad air"
                air_comment_ko = (
                    "공기질이 매우 나쁩니다. 가능하면 실외 러닝 대신 실내 운동이나 휴식을 권장합니다."
                )
                air_comment_en = (
                    "Air quality is very poor. Indoor exercise or rest is recommended instead of outdoor running."
                )

    # 공기질 수준에 따른 패널티 팩터
    if air_score >= 90:
        factor_air = 1.0     # 좋음: 영향 없음
    elif air_score >= 70:
        factor_air = 0.98    # 보통: 거의 영향 없음
    elif air_score >= 50:
        factor_air = 0.8     # 나쁨: 20% 정도 점수 감소
    else:
        factor_air = 0.6     # 매우 나쁨: 40% 정도 점수 감소

    # -----------------------------
    # 5) 종합 러닝 인덱스
    #    기본: 온도 60% + 바람 20% + 노면 20%
    #    공기질은 패널티(factor_air)로만 반영
    # -----------------------------
    base_score = (
        temp_score * 0.60 +
        wind_score * 0.20 +
        surface_score * 0.20
    )

    run_score = base_score * factor_air

    # 극단적인 온도/노면에서 안전 상한
    if surface_score == 0 or apparent <= -15 or apparent >= 33:
        run_score = min(run_score, 20)

    run_score = int(round(max(0, min(100, run_score))))

    # -----------------------------
    # 6) 종합 코멘트 및 태그 구성
    # -----------------------------
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
        advice_short_ko = "러닝 강도/시간을 줄이거나 실외 러닝을 피하는 것이 좋습니다 🚨"
        advice_short_en = "Consider reducing intensity/duration or avoiding outdoor running 🚨"

    detail_parts_ko = [temp_comment_ko, wind_comment_ko, wet_comment_ko]
    detail_parts_en = [temp_comment_en, wind_comment_en, wet_comment_en]

    if air_comment_ko:
        detail_parts_ko.append(air_comment_ko)
    if air_comment_en:
        detail_parts_en.append(air_comment_en)

    detail_parts_ko.append(
        "컨디션에 따라 강도를 조절하고, 평소보다 몸 상태를 더 자주 점검해 주세요."
    )
    detail_parts_en.append(
        "Adjust intensity based on how you feel and check your condition more often than usual."
    )

    advice_detail_ko = " ".join(detail_parts_ko)
    advice_detail_en = " ".join(detail_parts_en)

    # 태그: 온도/바람/노면 + (공기질 있으면) 공기질
    tags_ko = [temp_tag_ko, wind_tag_ko, wet_tag_ko]
    tags_en = [temp_tag_en, wind_tag_en, wet_tag_en]
    if air_tag_ko and air_tag_en:
        tags_ko.append(air_tag_ko)
        tags_en.append(air_tag_en)

    # -----------------------------
    # 7) GPX 파일 경로 (있을 때만)
    # -----------------------------
    gpx_rel_path: Optional[str] = None
    gpx_path = Path("gpx") / f"{course.id}.gpx"
    if gpx_path.exists():
        gpx_rel_path = f"gpx/{course.id}.gpx"

    # -----------------------------
    # 8) 최종 Dict 리턴 (JSON으로 직렬화될 내용)
    # -----------------------------
    return {
        "id": course.id,
        "name_ko": course.name_ko,
        "name_en": course.name_en,
        "name": course.name_ko,
        "updated_at": current["time"],
        "temperature": float(current["temperature_2m"]),
        "apparent_temperature": apparent,
        "wind_speed": wind_speed,          # m/s
        "wind_direction": wind_dir,
        "rain_now": current_rain,
        "recent_rain_3h": recent_rain,
        "wet_badge": wet_badge,
        "run_score": run_score,
        "temp_score": temp_score,
        "wind_score": wind_score,
        "wet_score": surface_score,        # 노면 점수 그대로 넣어둠
        "surface_score": surface_score,
        "air_score": air_score,
        "tags_ko": tags_ko,
        "tags_en": tags_en,
        "advice_short_ko": advice_short_ko,
        "advice_short_en": advice_short_en,
        "advice_detail_ko": advice_detail_ko,
        "advice_detail_en": advice_detail_en,
        "pm10": pm10,
        "pm25": pm25,
        "gpx": gpx_rel_path,
    }


# === 4. JSON 파일로 저장 ===


def main() -> None:
    results: List[Dict[str, Any]] = []

    for course in COURSES:
        print(f"[INFO] Fetching weather for {course.name_ko} ({course.lat}, {course.lon})")
        raw_weather = fetch_open_meteo_kma(course)

        raw_air: Optional[Dict[str, Any]] = None
        try:
            print("    - Fetching air quality (PM10/PM2.5)...")
            raw_air = fetch_air_quality(course)
        except Exception as e:
            print(f"[WARN] Failed to fetch air quality for {course.name_ko}: {e}")
            raw_air = None

        summary = summarize_course_weather(course, raw_weather, raw_air)
        results.append(summary)

    output = {
        "generated_at": datetime.now().isoformat(),
        "courses": results,
    }

    out_path = Path("data") / "src_weather.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[INFO] Saved {out_path} ({len(results)} courses)")


if __name__ == "__main__":
    main()
