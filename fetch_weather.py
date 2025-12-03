import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote_plus

import requests

from requests.exceptions import Timeout, ReadTimeout, RequestException, HTTPError

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

# === Provider 정의 & 상수 ===

DEFAULT_PROVIDER = os.getenv("WEATHER_PROVIDER", "open-meteo")
SUPPORTED_PROVIDERS = ("open-meteo", "kma")
KST = timezone(timedelta(hours=9))

KMA_ULTRA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_ULTRA_FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
KMA_AIR_QUALITY_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
DEFAULT_KMA_AIR_SIDO = os.getenv("KMA_AIR_SIDO_NAME", "경기도")


# === 2. 기상청(KMA) 초단기/초단기예보 호출 ===

def kst_now() -> datetime:
    return datetime.now(tz=timezone.utc).astimezone(KST)


def kma_base_datetime(now_kst: Optional[datetime] = None) -> Tuple[str, str]:
    """
    기상청 초단기 API는 발표시각 이후 약 30~40분 뒤에 최신 값을 제공합니다.
    현재 시각에서 40분을 뺀 뒤, 가까운 30분 단위로 내림하여 base_date/base_time을 계산합니다.
    """
    now = now_kst or kst_now()
    base_dt = now - timedelta(minutes=40)
    base_dt = base_dt.replace(
        minute=(base_dt.minute // 30) * 30,
        second=0,
        microsecond=0,
    )
    return base_dt.strftime("%Y%m%d"), base_dt.strftime("%H%M")


def latlon_to_kma_xy(lat: float, lon: float) -> Tuple[int, int]:
    """
    위/경도를 기상청 격자(nx, ny)로 변환합니다.
    표준 기상청 격자 변환(DFS) 공식 사용.
    """
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0       # 격자 간격(km)
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)
    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + XO + 1.5)
    y = int(ro - ra * math.cos(theta) + YO + 1.5)
    return x, y


def parse_precip_value(raw: Any) -> float:
    """
    기상청 RN1/PCP 값은 숫자 또는 '강수없음', '1mm 미만' 형태가 올 수 있으므로 보정합니다.
    """
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if not text or text == "강수없음":
        return 0.0

    cleaned = text.replace("mm", "").replace(" ", "")
    cleaned = cleaned.replace("미만", "")
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_pm_value(raw: Any) -> Optional[float]:
    """PM10/PM2.5 값 문자열에서 숫자만 추출해 float로 변환합니다."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def calc_apparent_temperature(temp_c: float, wind_speed_ms: float, humidity: float) -> float:
    """
    기상청 실황(체감온도 제공 안 함) 값을 이용해 간단히 체감온도를 계산합니다.
    - 추울 때: 캐나다 윈드칠 공식
    - 더울 때: NOAA Heat Index (섭씨 변환)
    """
    wind_kmh = wind_speed_ms * 3.6

    if temp_c <= 10 and wind_kmh > 4.8:
        v16 = math.pow(wind_kmh, 0.16)
        return 13.12 + 0.6215 * temp_c - 11.37 * v16 + 0.3965 * temp_c * v16

    if temp_c >= 27 and humidity >= 40:
        t_f = temp_c * 9 / 5 + 32
        hi_f = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * humidity
            - 0.22475541 * t_f * humidity
            - 0.00683783 * t_f * t_f
            - 0.05481717 * humidity * humidity
            + 0.00122874 * t_f * t_f * humidity
            + 0.00085282 * t_f * humidity * humidity
            - 0.00000199 * t_f * t_f * humidity * humidity
        )
        return (hi_f - 32) * 5 / 9

    return temp_c


def build_kma_url(base_url: str, service_key: str) -> str:
    """
    serviceKey는 이미 URL-encoded된 문자열을 그대로 써야 하므로,
    인코딩 여부를 감지해 중복 인코딩을 방지합니다.
    """
    if "%" in service_key:
        encoded_key = service_key
    else:
        encoded_key = quote_plus(service_key)
    return f"{base_url}?serviceKey={encoded_key}"


def fetch_kma_weather(course: Course, service_key: str) -> Optional[Dict[str, Any]]:
    """
    기상청 초단기실황 + 초단기예보를 조회해 summarize_course_weather가 기대하는
    형태(current/hourly)로 정규화합니다.
    """
    if not service_key:
        raise ValueError("KMA 서비스 키가 필요합니다. --kma-service-key 또는 KMA_SERVICE_KEY를 설정하세요.")

    base_date, base_time = kma_base_datetime()
    nx, ny = latlon_to_kma_xy(course.lat, course.lon)

    common_params = {
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
        "pageNo": 1,
        "numOfRows": 1000,
    }

    try:
        obs_url = build_kma_url(KMA_ULTRA_NCST_URL, service_key)
        obs_resp = requests.get(obs_url, params=common_params, timeout=10)
        obs_resp.raise_for_status()
        obs_items = obs_resp.json()["response"]["body"]["items"]["item"]
    except (Timeout, ReadTimeout) as e:
        print(f"[WARN] KMA timeout for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        return None
    except HTTPError as e:
        print(f"[WARN] KMA request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        if e.response is not None:
            print(f"[WARN] KMA response body: {e.response.text}")
        return None
    except RequestException as e:
        print(f"[WARN] KMA request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        return None
    except Exception as e:
        print(f"[WARN] KMA response parsing error for {course.name_ko}: {e}")
        return None

    obs_map: Dict[str, Any] = {item["category"]: item.get("obsrValue") for item in obs_items}

    try:
        temp_c = float(obs_map.get("T1H"))
    except (TypeError, ValueError):
        temp_c = None

    if temp_c is None:
        print(f"[WARN] KMA response missing temperature for {course.name_ko}, skipping.")
        return None

    wind_ms = float(obs_map.get("WSD", 0.0) or 0.0)
    wind_dir = float(obs_map.get("VEC", 0.0) or 0.0)
    humidity = float(obs_map.get("REH", 60.0) or 60.0)
    precip_mm = parse_precip_value(obs_map.get("RN1"))
    pty_val = str(obs_map.get("PTY", "0"))

    rain_mm = precip_mm if pty_val in ("1", "2", "5", "6") else 0.0
    apparent = calc_apparent_temperature(temp_c or 0.0, wind_ms, humidity)

    # 초단기예보로 앞으로 3시간 강수 예측값을 가져와 최근 강수량 근사에 사용
    forecast_params = dict(common_params)
    forecast_params["numOfRows"] = 200

    forecast_rain: Dict[str, float] = {}
    forecast_pty: Dict[str, str] = {}
    try:
        fcst_url = build_kma_url(KMA_ULTRA_FCST_URL, service_key)
        fcst_resp = requests.get(fcst_url, params=forecast_params, timeout=10)
        fcst_resp.raise_for_status()
        fcst_items = fcst_resp.json()["response"]["body"]["items"]["item"]
        for item in fcst_items:
            time_key = f"{item['fcstDate']}{item['fcstTime']}"
            if item["category"] == "RN1":
                forecast_rain[time_key] = parse_precip_value(item["fcstValue"])
            elif item["category"] == "PTY":
                forecast_pty[time_key] = str(item["fcstValue"])
    except (Timeout, ReadTimeout) as e:
        print(f"[WARN] KMA forecast timeout for {course.name_ko} ({course.lat}, {course.lon}): {e}")
    except HTTPError as e:
        print(f"[WARN] KMA forecast request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        if e.response is not None:
            print(f"[WARN] KMA forecast response body: {e.response.text}")
    except RequestException as e:
        print(f"[WARN] KMA forecast request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
    except Exception as e:
        print(f"[WARN] KMA forecast parsing error for {course.name_ko}: {e}")

    hourly_precip: List[float] = []
    hourly_rain: List[float] = []
    sorted_times = sorted(forecast_rain.keys())
    if not sorted_times:
        sorted_times = sorted(forecast_pty.keys())

    for time_key in sorted_times[:3]:
        rn1 = forecast_rain.get(time_key, 0.0)
        pty = forecast_pty.get(time_key, "0")
        hourly_precip.append(rn1)
        hourly_rain.append(rn1 if pty in ("1", "2", "5", "6") else 0.0)

    current_time = kst_now().replace(microsecond=0).isoformat()
    return {
        "current": {
            "time": current_time,
            "temperature_2m": temp_c,
            "apparent_temperature": apparent if temp_c is not None else temp_c,
            "precipitation": precip_mm,
            "rain": rain_mm,
            "wind_speed_10m": wind_ms * 3.6,  # summarize 함수가 m/s로 변환하므로 km/h 단위로 제공
            "wind_direction_10m": wind_dir,
        },
        "hourly": {
            "precipitation": hourly_precip,
            "rain": hourly_rain,
        },
    }


# === 3. Open-Meteo KMA & Air Quality 호출 ===

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

    try:
        resp = requests.get(OPEN_METEO_BASE, params=params, timeout=10)
        resp.raise_for_status()
    except (Timeout, ReadTimeout) as e:
        print(
            f"[WARN] Open-Meteo timeout for {course.name_ko} "
            f"({course.lat}, {course.lon}): {e}"
        )
        print(f"[WARN] Skipping {course.name_ko} for this run.")
        return None
    except RequestException as e:
        print(
            f"[WARN] Open-Meteo request error for {course.name_ko} "
            f"({course.lat}, {course.lon}): {e}"
        )
        print(f"[WARN] Skipping {course.name_ko} for this run.")
        return None

    return resp.json()


def fetch_air_quality_open_meteo(course: Course) -> Optional[Dict[str, Any]]:
    """Open-Meteo Air Quality API에서 PM10 / PM2.5 현재값을 가져옵니다."""
    params = {
        "latitude": course.lat,
        "longitude": course.lon,
        "current": "pm10,pm2_5",
        "timezone": "Asia/Seoul",
    }
    resp = requests.get(AIR_QUALITY_BASE, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_air_quality_kma(
    course: Course,
    service_key: str,
    sido_name: str = DEFAULT_KMA_AIR_SIDO,
) -> Optional[Dict[str, Any]]:
    """
    환경부(에어코리아) 실시간 시도별 대기오염 정보에서 PM10/PM2.5를 조회합니다.
    - lat/lon별 가장 근처 측정소를 구하는 추가 API가 있으나, 간단히 시도 단위로 조회해
      유효한 첫 측정값을 사용합니다.
    """
    if not service_key:
        raise ValueError("KMA 서비스 키가 필요합니다. --kma-service-key 또는 KMA_SERVICE_KEY를 설정하세요.")

    params = {
        "sidoName": sido_name,
        "returnType": "json",
        "pageNo": 1,
        "numOfRows": 100,
        "ver": "1.3",
    }

    url = build_kma_url(KMA_AIR_QUALITY_URL, service_key)
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except HTTPError as e:
        print(f"[WARN] KMA air quality HTTP error: {e}")
        if e.response is not None:
            print(f"[WARN] KMA air quality body: {e.response.text}")
        return None
    except RequestException as e:
        print(f"[WARN] KMA air quality request error: {e}")
        return None

    body = resp.json().get("response", {}).get("body", {})
    items = body.get("items") or []

    chosen = None
    for item in items:
        pm10 = parse_pm_value(item.get("pm10Value"))
        pm25 = parse_pm_value(item.get("pm25Value"))
        if pm10 is not None or pm25 is not None:
            chosen = {
                "time": item.get("dataTime"),
                "pm10": pm10,
                "pm2_5": pm25,
                "station": item.get("stationName"),
            }
            break

    if chosen is None:
        return None

    return {"current": chosen}


# === CLI 옵션 ===


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch running weather data from Open-Meteo or KMA.")
    parser.add_argument(
        "--provider",
        choices=list(SUPPORTED_PROVIDERS),
        default=DEFAULT_PROVIDER,
        help="날씨 데이터 소스 (open-meteo|kma). 기본값은 WEATHER_PROVIDER 환경변수 또는 open-meteo.",
    )
    parser.add_argument(
        "--kma-service-key",
        dest="kma_service_key",
        default=os.getenv("KMA_SERVICE_KEY"),
        help="기상청(data.go.kr) 서비스 키. provider=kma일 때 필수. 환경변수 KMA_SERVICE_KEY로도 지정 가능.",
    )
    parser.add_argument(
        "--air-provider",
        choices=("open-meteo", "kma"),
        default=None,
        help="대기질 데이터 소스 (open-meteo|kma). 기본값은 weather provider와 동일하게 동작.",
    )
    parser.add_argument(
        "--kma-air-sido-name",
        dest="kma_air_sido_name",
        default=DEFAULT_KMA_AIR_SIDO,
        help=f"기상청(에어코리아) 대기질 조회 시 사용할 시도 이름. 기본값: {DEFAULT_KMA_AIR_SIDO}",
    )
    return parser


# === 4. 러닝용으로 요약 + 한/영 텍스트 생성 ===


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
        temp_tag_ko = "위험한 추움"
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
        temp_tag_ko = "매우 추움"
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
        temp_tag_ko = "추움"
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
        temp_tag_en = "Warm"
        temp_comment_ko = (
            "다소 따뜻한 편입니다. 통풍 잘 되는 옷과 충분한 수분 섭취를 추천합니다."
        )
        temp_comment_en = (
            "Slightly warm. Wear breathable clothes and make sure to hydrate."
        )
    elif apparent < 26:
        temp_score = 55
        temp_tag_ko = "조금 더움"
        temp_tag_en = "Very warm"
        temp_comment_ko = (
            "조금 더운 편입니다. 강도 높은 훈련보다는 적당한 강도의 러닝이 좋습니다."
        )
        temp_comment_en = (
            "Slightly hot. Moderate intensity runs are better than hard workouts."
        )
    elif apparent < 29:
        temp_score = 40
        temp_tag_ko = "더움"
        temp_tag_en = "Hot"
        temp_comment_ko = (
            "더운 편입니다. 강도를 낮추고 자주 수분을 섭취하는 것이 좋습니다."
        )
        temp_comment_en = (
            "Warm conditions. Lower your intensity and hydrate frequently."
        )
    elif apparent < 31:
        temp_score = 25
        temp_tag_ko = "꽤 더움"
        temp_tag_en = "Quite hot"
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
        temp_tag_ko = "위험한 더움"
        temp_tag_en = "Extremely hot"
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
        "lat": course.lat,
        "lon": course.lon,
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


# === 5. JSON 파일로 저장 ===


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    provider = args.provider
    kma_service_key = args.kma_service_key
    air_provider = args.air_provider or provider
    kma_air_sido_name = args.kma_air_sido_name

    if provider == "kma" and not kma_service_key:
        print("[ERROR] provider=kma 인 경우 --kma-service-key 또는 KMA_SERVICE_KEY가 필요합니다.")
        return

    results: List[Dict[str, Any]] = []

    for course in COURSES:
        print(
            f"[INFO] Fetching weather ({provider}) for {course.name_ko} "
            f"({course.lat}, {course.lon})"
        )

        if provider == "kma":
            raw_weather = fetch_kma_weather(course, kma_service_key)
        else:
            raw_weather = fetch_open_meteo_kma(course)

        if raw_weather is None:
            # 이 코스는 이번 run에서 실패 → 전체 스크립트는 계속 진행
            print(f"[WARN] Weather fetch failed for {course.name_ko}, skipping this course.")
            continue

        raw_air: Optional[Dict[str, Any]] = None
        try:
            if air_provider == "open-meteo":
                print("    - Fetching air quality (Open-Meteo)...")
                raw_air = fetch_air_quality_open_meteo(course)
            elif air_provider == "kma":
                print("    - Fetching air quality (KMA/AirKorea)...")
                raw_air = fetch_air_quality_kma(course, kma_service_key, kma_air_sido_name)
        except Exception as e:
            print(f"[WARN] Failed to fetch air quality for {course.name_ko}: {e}")
            raw_air = None

        # KMA 대기질 실패 시 Open-Meteo로 한 번 더 시도
        if raw_air is None and air_provider == "kma":
            try:
                print("    - Air quality fallback to Open-Meteo...")
                raw_air = fetch_air_quality_open_meteo(course)
            except Exception as e:
                print(f"[WARN] Air quality fallback failed for {course.name_ko}: {e}")
        summary = summarize_course_weather(course, raw_weather, raw_air)
        results.append(summary)
        time.sleep(5)

    output = {
        "generated_at": kst_now().isoformat(),
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
