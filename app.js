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

  const wetBadge = info.wet_badge || { level: "", text_ko: "", text_en: "" };
  const wetText =
    currentLang === "ko" ? wetBadge.text_ko : wetBadge.text_en;

  const tags =
    currentLang === "ko" ? info.tags_ko || [] : info.tags_en || [];

  // ✅ 1) 노면 배지와 같은 태그 제거
  // ✅ 2) 중복 태그 제거
  const uniqueTags = [];
  for (const t of tags) {
    if (!t) continue;
    if (t === wetText) continue; // 이미 배지로 표시된 문구는 태그에서 제거
    if (uniqueTags.includes(t)) continue; // 같은 문구 중복 제거
    uniqueTags.push(t);
  }

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
      <span class="${badgeClass(wetBadge.level)}">${wetText}</span>
    </div>
    <div class="course-meta">
      <div style="margin-bottom:4px;">
        <strong>${runLabel}</strong> ${info.run_score ?? "?"}/100
      </div>
      ${
        uniqueTags.length
          ? `<div style="margin-bottom:4px;">
               ${uniqueTags
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
