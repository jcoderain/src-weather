const COURSES = [
  {
    id: "suwon-city-hall",
    name: "수원시청 주변",
    lat: 37.2636,
    lon: 127.0286,
  },
];

const statusEl = document.getElementById("status");
const coursesEl = document.getElementById("courses");

function windDirectionToText(deg) {
  if (deg === null || deg === undefined) return "-";
  const dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"];
  const idx = Math.round((deg % 360) / 45) % 8;
  return dirs[idx];
}

function buildApiUrl(lat, lon) {
  const base = "https://api.open-meteo.com/v1/forecast";
  const params = new URLSearchParams({
    latitude: lat,
    longitude: lon,
    hourly:
      "temperature_2m,apparent_temperature,precipitation,rain,wind_speed_10m,wind_direction_10m",
    current:
      "temperature_2m,apparent_temperature,precipitation,rain,wind_speed_10m,wind_direction_10m",
    timezone: "Asia/Seoul",
    models: "kma_seamless",
    past_hours: "3",
    forecast_hours: "0",
  });
  return `${base}?${params.toString()}`;
}

async function fetchCourseWeather(course) {
  const url = buildApiUrl(course.lat, course.lon);
  const resp = await fetch(url);
  if (!resp.ok) throw new Error("API error");
  const data = await resp.json();

  const current = data.current;
  const hourly = data.hourly;

  const recentRain = hourly.rain.reduce((sum, v) => sum + (v || 0), 0);

  let wetBadge = { text: "노면 건조", cls: "badge-good" };
  if (recentRain > 0 && recentRain < 1) {
    wetBadge = { text: "약간 젖음", cls: "badge-wet" };
  } else if (recentRain >= 1) {
    wetBadge = { text: "많이 젖음", cls: "badge-bad" };
  }

  return {
    course,
    currentTemp: current.temperature_2m,
    apparentTemp: current.apparent_temperature,
    windSpeed: current.wind_speed_10m,
    windDirDeg: current.wind_direction_10m,
    rainNow: current.rain,
    recentRain,
    wetBadge,
    time: current.time,
  };
}

function renderCourseCard(info) {
  const div = document.createElement("div");
  div.className = "course-card";

  const windText =
    info.windSpeed != null
      ? `${windDirectionToText(info.windDirDeg)} ${info.windSpeed.toFixed(
          1
        )} m/s`
      : "-";

  div.innerHTML = `
    <div class="course-title">
      <span>${info.course.name}</span>
      <span class="badge ${info.wetBadge.cls}">${info.wetBadge.text}</span>
    </div>
    <div class="course-meta">
      <div>현재 기온 ${info.currentTemp.toFixed(
        1
      )}°C · 체감 ${info.apparentTemp.toFixed(1)}°C</div>
      <div>바람 ${windText}</div>
      <div>현재 비 ${info.rainNow.toFixed(
        1
      )} mm · 최근 3시간 비 ${info.recentRain.toFixed(1)} mm</div>
      <div>업데이트: ${info.time}</div>
    </div>
  `;
  return div;
}

async function init() {
  try {
    statusEl.innerHTML = "<p>Open-Meteo KMA에서 데이터를 가져오는 중…</p>";

    const results = await Promise.all(
      COURSES.map((c) => fetchCourseWeather(c))
    );

    statusEl.innerHTML = "<p>지금 달리기 컨디션을 확인해보세요 🏃‍♂️</p>";

    coursesEl.innerHTML = "";
    results.forEach((info) => {
      coursesEl.appendChild(renderCourseCard(info));
    });
  } catch (err) {
    console.error(err);
    statusEl.innerHTML =
      "<p>날씨 데이터를 불러오는데 실패했습니다. 잠시 후 다시 시도해 주세요.</p>";
  }
}

init();
