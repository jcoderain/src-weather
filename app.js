let currentLang = "ko";
let LAST_DATA = null;

const statusEl = document.getElementById("status");
const coursesEl = document.getElementById("courses");
const appTitleEl = document.getElementById("app-title");
const appSubtitleEl = document.getElementById("app-subtitle");
const courseListTitleEl = document.getElementById("course-list-title");
const courseListUpdatedEl = document.getElementById("course-list-updated"); // ✅ 추가


// 절대 경로 + 캐시 방지
const JSON_URL =
  "https://jcoderain.github.io/src-weather/data/src_weather.json";

// ✅ wind_speed 값의 단위 설정
// true  => src_weather.json 의 wind_speed 가 m/s 라고 가정
// false => src_weather.json 의 wind_speed 가 km/h 라고 가정 (자동으로 m/s 로 환산해서 표시)
const WIND_SOURCE_IS_MS = true;

const uiText = {
  appTitle: {
    ko: "SRC 날씨 정보",
    en: "SRC Weather Information",
  },
  appSubtitle: {
    ko: "SRC 러너들을 위한 현재 코스 상황",
    en: "Current course conditions for SRC runners",
  },
  courseListTitle: {
    ko: "코스별 현재 상황",
    en: "Current conditions by course",
  },
  statusLoading: {
    ko: "SRC 러너용 날씨 데이터를 불러오는 중…",
    en: "Loading weather data for SRC runners…",
  },
  statusLoaded: (count) => ({
    ko: `SRC의 주요 ${count}개 코스의 날씨를 불러왔습니다. 화이팅! 🏃‍♂️`,
    en: `Loaded conditions for SRC major ${count} courses. Fighting! 🏃‍♂️`,
  }),
  fail: {
    ko: "코스 데이터를 불러오는데 실패했습니다. 잠시 후 다시 시도해 주세요.",
    en: "Failed to load course data. Please try again later.",
  },
  airQualityLabel: {
    ko: "공기질",
    en: "Air quality",
  },
  gpxLabel: {
    ko: "GPX 파일 열기",
    en: "Open GPX file",
  },
};

function applyLanguage() {
  appTitleEl.textContent = uiText.appTitle[currentLang];
  appSubtitleEl.textContent = uiText.appSubtitle[currentLang];
  courseListTitleEl.textContent = uiText.courseListTitle[currentLang];

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    const lang = btn.dataset.lang;
    if (lang === currentLang) btn.classList.add("active");
    else btn.classList.remove("active");
  });

  // ✅ 언어 바꿀 때 status 문구도 다시 렌더
  renderStatus();
  renderUpdatedAt(); // ✅ 언어 바뀔 때도 같이 갱신
}

// "2025-11-26T21:00" 같은 문자열을 한/영으로 포맷
function formatUpdatedAtLocalized(isoLikeStr) {
  if (!isoLikeStr) return "";

  const [datePart, timePart] = isoLikeStr.split("T");
  if (!datePart || !timePart) return "";

  const [y, m, d] = datePart.split("-");
  const [hh, mm] = timePart.split(":");

  const pad2 = (v) => String(v).padStart(2, "0");  // ✅ 여기서 pad2 정의

  if (currentLang === "ko") {
    // 시/분 모두 2자리로 (21시 00분)
    return `${y}년 ${Number(m)}월 ${Number(d)}일 ${pad2(hh)}시 ${pad2(mm)}분에 업데이트됨`;
  } else {
    // 2025-11-26 21:00 (KST)
    return `Updated at ${y}-${pad2(m)}-${pad2(d)} ${pad2(hh)}:${pad2(mm)} (KST)`;
  }
}


// 공통 updated_at (첫 코스 기준) 가져오기
function getCommonUpdatedAt() {
  if (!LAST_DATA) return null;
  const courses = LAST_DATA.courses || [];
  if (!courses.length) return null;
  return courses[0].updated_at || null;
}

// 실제로 DOM에 렌더
function renderUpdatedAt() {
  if (!courseListUpdatedEl) return;
  const iso = getCommonUpdatedAt();
  if (!iso) {
    courseListUpdatedEl.textContent = "";
    return;
  }
  courseListUpdatedEl.textContent = formatUpdatedAtLocalized(iso);
}

// ✅ 풍향(deg)을 한/영 텍스트로 변환
function windDirectionToText(deg) {
  if (deg === null || deg === undefined) return "-";
  const dirsKo = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"];
  const dirsEn = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const idx = Math.round((deg % 360) / 45) % 8;
  return currentLang === "ko" ? dirsKo[idx] : dirsEn[idx];
}

// ✅ 풍속 포맷팅 (단위 변환 포함)
function formatWindText(speed, deg) {
  if (speed == null) return "-";

  let valueMs;
  if (WIND_SOURCE_IS_MS) {
    valueMs = speed;
  } else {
    // JSON 이 km/h 라면 m/s 로 변환
    valueMs = speed / 3.6;
  }

  const dirText = windDirectionToText(deg);
  const unitLabel = "m/s"; // 화면에는 m/s 기준으로 표시

  return `${dirText} ${valueMs.toFixed(1)} ${unitLabel}`;
}

// (지금은 안 쓰이지만 놔둬도 상관 없음)
function badgeClass(level) {
  switch (level) {
    case "good":
      return "badge badge-good";
    case "wet":
      return "badge badge-wet";
    case "bad":
      return "badge badge-bad";
    default:
      return "badge";
  }
}

// ✅ run_score 색상 클래스 결정
function runScoreClass(score) {
  if (score == null) return "run-score run-score-unknown";
  if (score >= 80) return "run-score run-score-great"; // 매우 좋음
  if (score >= 60) return "run-score run-score-good"; // 괜찮음
  if (score >= 40) return "run-score run-score-caution"; // 주의
  return "run-score run-score-bad"; // 비추천
}

// ✅ 미세먼지/초미세먼지 등급 분류
function classifyPm10(value) {
  if (value == null) return null;
  if (value <= 30) return { level: "good", ko: "좋음", en: "Good" };
  if (value <= 80) return { level: "moderate", ko: "보통", en: "Moderate" };
  if (value <= 150) return { level: "bad", ko: "나쁨", en: "Bad" };
  return { level: "very-bad", ko: "매우 나쁨", en: "Very bad" };
}

function classifyPm25(value) {
  if (value == null) return null;
  if (value <= 15) return { level: "good", ko: "좋음", en: "Good" };
  if (value <= 35) return { level: "moderate", ko: "보통", en: "Moderate" };
  if (value <= 75) return { level: "bad", ko: "나쁨", en: "Bad" };
  return { level: "very-bad", ko: "매우 나쁨", en: "Very bad" };
}

function buildNaverMapLink(lat, lon) {
  if (lat == null || lon == null) return null;
  // v5 지도에서 중심을 주어진 좌표로 맞추는 URL
  return `https://map.naver.com/v5/?c=${lon},${lat},16,0,0,0,dh`;
}

// ✅ 공기질 한 줄 HTML 생성
function buildAirQualityHtml(info) {
  const pm10 = info.pm10;
  const pm25 = info.pm25;

  if (pm10 == null && pm25 == null) {
    return "";
  }

  const pm10Info = classifyPm10(pm10);
  const pm25Info = classifyPm25(pm25);

  const label = uiText.airQualityLabel[currentLang];
  const unit = "㎍/m³";

  const pm10Text =
    pm10 != null && pm10Info
      ? `PM10 ${pm10.toFixed(0)} ${unit} (${
          currentLang === "ko" ? pm10Info.ko : pm10Info.en
        })`
      : "";

  const pm25Text =
    pm25 != null && pm25Info
      ? `PM2.5 ${pm25.toFixed(0)} ${unit} (${
          currentLang === "ko" ? pm25Info.ko : pm25Info.en
        })`
      : "";

  const parts = [pm10Text, pm25Text].filter((x) => x);

  if (!parts.length) return "";

  return `<div>${label} · ${parts.join(" · ")}</div>`;
}

function renderCourseCard(info) {
  const div = document.createElement("div");
  div.className = "course-card";

  // 이름 한/영
  const displayName =
    currentLang === "ko"
      ? info.name_ko || info.name
      : info.name_en || info.name;

  const windText = formatWindText(info.wind_speed, info.wind_direction);

  // 태그는 원래대로(온도/바람/노면 모두) 사용
  const tags =
    currentLang === "ko" ? info.tags_ko || [] : info.tags_en || [];

  const adviceShort =
    currentLang === "ko" ? info.advice_short_ko : info.advice_short_en;
  const adviceDetail =
    currentLang === "ko" ? info.advice_detail_ko : info.advice_detail_en;

  const lat = info.lat ?? info.latitude;
  const lon = info.lon ?? info.longitude;
  const locationLink = buildNaverMapLink(lat, lon);

  const windTag =
    currentLang === "ko"
      ? (info.tags_ko && info.tags_ko[1]) || null
      : (info.tags_en && info.tags_en[1]) || null;
  const airTag =
    currentLang === "ko"
      ? info.tags_ko && info.tags_ko.length > 3
        ? info.tags_ko[3]
        : null
      : info.tags_en && info.tags_en.length > 3
        ? info.tags_en[3]
        : null;

  const runLabel = currentLang === "ko" ? "러닝 지수" : "Run index";
  const tempLabel = currentLang === "ko" ? "현재 기온" : "Air temp";
  const feelsLabel = currentLang === "ko" ? "체감" : "Feels like";
  const windLabel = currentLang === "ko" ? "바람" : "Wind";
  const rainNowLabel = currentLang === "ko" ? "현재 비" : "Rain now";
  const rain3hLabel =
    currentLang === "ko" ? "최근 3시간 비" : "Rain (last 3h)";
  const gpxLabel = uiText.gpxLabel[currentLang];

  const airQualityHtml = buildAirQualityHtml(info);

  div.innerHTML = `
    <div class="course-title">
      <span>${displayName}</span>
      <!-- ✅ 여기 원래 노면 건조가 있던 자리에 run_score 하이라이트 -->
      <span class="${runScoreClass(info.run_score)}">${info.run_score ?? "?"}</span>
    </div>
    <div class="course-meta">
      <div class="run-index-row" style="margin-bottom:4px;">
        <strong>${runLabel}</strong> ${info.run_score ?? "?"}/100
      </div>
      ${
        tags.length
          ? `<div style="margin-bottom:4px;">
               ${tags
                 .map(
                   (t) =>
                     `<span class="badge" style="margin-right:4px;">${t}</span>`
                 )
                 .join("")}
             </div>`
          : ""
      }
      <div>
        ${tempLabel} ${info.temperature.toFixed(
    1
  )}°C · ${feelsLabel} ${info.apparent_temperature.toFixed(1)}°C
      </div>
      <div>
        ${windLabel} ${windText}
      </div>
      <div>
        ${rainNowLabel} ${info.rain_now.toFixed(
    1
  )} mm · ${rain3hLabel} ${info.recent_rain_3h.toFixed(1)} mm
      </div>
      ${
        airQualityHtml
          ? `<div style="margin-top:4px;">${airQualityHtml}</div>`
          : ""
      }
      <div class="location-row">
        ${
          lat != null && lon != null
            ? `<div>${currentLang === "ko" ? "위치" : "Location"} ${lat.toFixed(5)}, ${lon.toFixed(5)}</div>
               ${
                 locationLink
                   ? `<a class="location-link" href="${locationLink}" target="_blank" rel="noopener">
                        ${currentLang === "ko" ? "네이버맵에서 보기" : "Open in Naver Map"}
                      </a>`
                   : ""
               }`
            : `<div>${currentLang === "ko" ? "위치 정보 없음" : "No location info"}</div>`
        }
      </div>
      <div class="score-rows">
        <div class="score-row">
          <span class="score-label">${currentLang === "ko" ? "바람 점수" : "Wind score"}</span>
          <span>${info.wind_score ?? "?"}/100 ${windTag ? `· ${windTag}` : ""}</span>
        </div>
        <div class="score-row">
          <span class="score-label">${currentLang === "ko" ? "공기질" : "Air quality"}</span>
          <span>${info.air_score ?? "?"}/100 ${airTag ? `· ${airTag}` : ""}</span>
        </div>
      </div>
      ${
        adviceShort || adviceDetail
          ? `<div class="advice-box">
               ${adviceShort ? `<div class="advice-short">${adviceShort}</div>` : ""}
               ${adviceDetail ? `<div class="advice-detail">${adviceDetail}</div>` : ""}
             </div>`
          : ""
      }
      ${
        info.gpx
          ? `<div class="course-actions" style="margin-top:6px;">
               <a class="gpx-link" href="${info.gpx}" target="_blank" rel="noopener">
                 ${gpxLabel}
               </a>
             </div>`
          : ""
      }
    </div>
  `;
  return div;
}

function renderAllCourses() {
  if (!LAST_DATA) return;
  const courses = LAST_DATA.courses || [];
  coursesEl.innerHTML = "";
  courses.forEach((info) => {
    coursesEl.appendChild(renderCourseCard(info));
  });
}

function renderStatus() {
  // 아직 데이터가 없으면 "로딩 중" 문구
  if (!LAST_DATA) {
    statusEl.innerHTML = `<p>${uiText.statusLoading[currentLang]}</p>`;
    return;
  }

  // 데이터가 있으면 코스 개수 기준 문구
  const courses = LAST_DATA.courses || [];
  const text = uiText.statusLoaded(courses.length)[currentLang];
  statusEl.innerHTML = `<p>${text}</p>`;
}

async function init() {
  try {
    applyLanguage();
    renderStatus(); // ✅ 처음에도 함수로 렌더

    const resp = await fetch(`${JSON_URL}?t=${Date.now()}`, {
      cache: "no-store",
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }

    const data = await resp.json();
    LAST_DATA = data;

    renderStatus(); // ✅ 데이터 받은 뒤에도 다시 호출
    renderUpdatedAt();   // ✅ 데이터 로딩 후 갱신
    renderAllCourses();
  } catch (err) {
    console.error("[weather-init-error]", err);
    statusEl.innerHTML = `<p>${uiText.fail[currentLang]}</p>`;
  }
}

// 언어 버튼 이벤트
document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const lang = btn.dataset.lang;
    if (!lang || lang === currentLang) return;
    currentLang = lang;
    applyLanguage();
    renderAllCourses();
  });
});

init();
