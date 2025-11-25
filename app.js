let currentLang = "ko";
let LAST_DATA = null;

const statusEl = document.getElementById("status");
const coursesEl = document.getElementById("courses");
const appTitleEl = document.getElementById("app-title");
const appSubtitleEl = document.getElementById("app-subtitle");
const courseListTitleEl = document.getElementById("course-list-title");

// 절대 경로 + 캐시 방지
const JSON_URL =
  "https://jcoderain.github.io/src-weather/data/src_weather.json";


const uiText = {
  appTitle: {
    ko: "SRC 날씨",
    en: "SRC Weather",
  },
  appSubtitle: {
    ko: "SRC 러너들을 위한 현재 컨디션",
    en: "Current conditions for SRC runners",
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
    ko: `총 ${count}개 코스의 날씨을 불러왔습니다. 화이팅! 🏃‍♂️`,
    en: `Loaded weather for ${count} courses. Fighting! 🏃‍♂️`,
  }),
  fail: {
    ko: "날씨 데이터를 불러오는데 실패했습니다. 잠시 후 다시 시도해 주세요.",
    en: "Failed to load weather data. Please try again later.",
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
}


function windDirectionToText(deg) {
  if (deg === null || deg === undefined) return "-";
  const dirsKo = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"];
  const dirsEn = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const idx = Math.round((deg % 360) / 45) % 8;
  return currentLang === "ko" ? dirsKo[idx] : dirsEn[idx];
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

function renderCourseCard(info) {
  const div = document.createElement("div");
  div.className = "course-card";

  // 이름 한/영
  const displayName =
    currentLang === "ko"
      ? info.name_ko || info.name
      : info.name_en || info.name;

  const windText =
    info.wind_speed != null
      ? `${windDirectionToText(info.wind_direction)} ${info.wind_speed.toFixed(
          1
        )} m/s`
      : "-";

  // 태그는 원래대로(온도/바람/노면 모두) 사용
  const tags =
    currentLang === "ko" ? info.tags_ko || [] : info.tags_en || [];

  const runLabel = currentLang === "ko" ? "러닝 지수" : "Run index";
  const tempLabel = currentLang === "ko" ? "현재 기온" : "Air temp";
  const feelsLabel = currentLang === "ko" ? "체감" : "Feels like";
  const windLabel = currentLang === "ko" ? "바람" : "Wind";
  const rainNowLabel = currentLang === "ko" ? "현재 비" : "Rain now";
  const rain3hLabel =
    currentLang === "ko" ? "최근 3시간 비" : "Rain (last 3h)";
  const updatedLabel = currentLang === "ko" ? "업데이트" : "Updated";

  div.innerHTML = `
    <div class="course-title">
      <span>${displayName}</span>
      <!-- ✅ 여기 원래 노면 건조가 있던 자리에 run_score 하이라이트 -->
      <span class="${runScoreClass(info.run_score)}">${info.run_score ?? "?"}</span>
    </div>
    <div class="course-meta">
      <div style="margin-bottom:4px;">
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
      <div style="margin-top:4px; font-size:0.78rem; color:#9ca3af;">
        ${updatedLabel}: ${info.updated_at}
      </div>
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

    renderStatus();   // ✅ 데이터 받은 뒤에도 다시 호출
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
