const statusEl = document.getElementById("status");
const coursesEl = document.getElementById("courses");

function windDirectionToText(deg) {
  if (deg === null || deg === undefined) return "-";
  const dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"];
  const idx = Math.round((deg % 360) / 45) % 8;
  return dirs[idx];
}

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

function renderCourseCard(info) {
  const div = document.createElement("div");
  div.className = "course-card";

  const windText =
    info.wind_speed != null
      ? `${windDirectionToText(info.wind_direction)} ${info.wind_speed.toFixed(
          1
        )} m/s`
      : "-";

  const wetBadge = info.wet_badge || { text: "", level: "" };

  div.innerHTML = `
    <div class="course-title">
      <span>${info.name}</span>
      <span class="${badgeClass(wetBadge.level)}">${wetBadge.text}</span>
    </div>
    <div class="course-meta">
      <div>현재 기온 ${info.temperature.toFixed(
        1
      )}°C · 체감 ${info.apparent_temperature.toFixed(1)}°C</div>
      <div>바람 ${windText}</div>
      <div>현재 비 ${info.rain_now.toFixed(
        1
      )} mm · 최근 3시간 비 ${info.recent_rain_3h.toFixed(1)} mm</div>
      <div>${info.comment || ""}</div>
      <div>업데이트: ${info.updated_at}</div>
    </div>
  `;
  return div;
}

async function init() {
  try {
    statusEl.innerHTML = "<p>수원 러너용 날씨 데이터를 불러오는 중…</p>";

    const resp = await fetch("data/suwon_weather.json", { cache: "no-cache" });
    if (!resp.ok) throw new Error("JSON not found");

    const data = await resp.json();
    const courses = data.courses || [];

    statusEl.innerHTML = `<p>총 ${courses.length}개 코스의 컨디션을 불러왔습니다 🏃‍♂️</p>`;

    coursesEl.innerHTML = "";
    courses.forEach((info) => {
      coursesEl.appendChild(renderCourseCard(info));
    });
  } catch (err) {
    console.error(err);
    statusEl.innerHTML =
      "<p>날씨 데이터를 불러오는데 실패했습니다. 잠시 후 다시 시도해 주세요.</p>";
  }
}

init();
