const state = {
  metadata: null,
  session: null,
  activeSince: new Map(),
  activeIndex: 0,
  elapsedTimer: null,
};

const el = {
  dashboardView: document.querySelector("#dashboardView"),
  practiceView: document.querySelector("#practiceView"),
  sectionType: document.querySelector("#sectionType"),
  sectionCount: document.querySelector("#sectionCount"),
  mockTemplate: document.querySelector("#mockTemplate"),
  favoriteCount: document.querySelector("#favoriteCount"),
  mistakeCount: document.querySelector("#mistakeCount"),
  startSection: document.querySelector("#startSection"),
  startMock: document.querySelector("#startMock"),
  startFavorites: document.querySelector("#startFavorites"),
  startMistakes: document.querySelector("#startMistakes"),
  refreshStats: document.querySelector("#refreshStats"),
  statsSummary: document.querySelector("#statsSummary"),
  typeStats: document.querySelector("#typeStats"),
  recentSessions: document.querySelector("#recentSessions"),
  sessionTitle: document.querySelector("#sessionTitle"),
  sessionMeta: document.querySelector("#sessionMeta"),
  backDashboard: document.querySelector("#backDashboard"),
  sessionTimer: document.querySelector("#sessionTimer"),
  finishSession: document.querySelector("#finishSession"),
  aiAnalysis: document.querySelector("#aiAnalysis"),
  analysisBox: document.querySelector("#analysisBox"),
  questionNav: document.querySelector("#questionNav"),
  prevQuestion: document.querySelector("#prevQuestion"),
  nextQuestion: document.querySelector("#nextQuestion"),
  questionCounter: document.querySelector("#questionCounter"),
  cards: document.querySelector("#cards"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message || payload.error || response.statusText);
  }
  return payload;
}

async function init() {
  state.metadata = await api("/api/metadata");
  renderMetadata();
  await refreshStats();
  await refreshRecent();
}

function renderMetadata() {
  el.sectionType.innerHTML = state.metadata.question_types
    .map((type) => `<option value="${escapeAttr(type)}">${escapeHtml(type)} (${state.metadata.counts[type] || 0})</option>`)
    .join("");
  el.mockTemplate.innerHTML = Object.entries(state.metadata.templates)
    .map(([id, tpl]) => `<option value="${escapeAttr(id)}">${escapeHtml(tpl.label)} · ${tpl.total}题</option>`)
    .join("");
}

async function refreshStats() {
  const stats = await api("/api/stats?days=30");
  const total = stats.total || 0;
  const correct = stats.by_type.reduce((sum, row) => sum + row.correct, 0);
  const accuracy = total ? Math.round((correct / total) * 100) : 0;
  const avgDuration = average(stats.by_type.map((row) => row.avg_duration).filter(Boolean));
  const strongest = topType(stats.by_type, "accuracy");
  const mostPracticed = topType(stats.by_type, "total");
  el.statsSummary.innerHTML = [
    metric("近30天", `${total}题`),
    metric("正确率", `${accuracy}%`),
    metric("平均耗时", `${avgDuration.toFixed(1)}s`),
    metric("最高版块", strongest ? `${strongest.label} ${Math.round(strongest.accuracy * 100)}%` : "-"),
    metric("练得最多", mostPracticed ? `${mostPracticed.label} ${mostPracticed.total}题` : "-"),
    metric("重点/错题", `${state.metadata.favorite_count || 0}/${state.metadata.mistake_count || 0}`),
  ].join("");
  el.typeStats.innerHTML = renderTypeAnalytics(stats);
}

async function refreshRecent() {
  const payload = await api("/api/sessions");
  el.recentSessions.innerHTML = payload.sessions
    .slice(0, 8)
    .map((session) => {
      const rate = session.total_count ? Math.round((session.correct_count / session.total_count) * 100) : 0;
      return `<div class="session-row" data-session-id="${escapeAttr(session.id)}"><span>${escapeHtml(session.title)}</span><span>${rate}%</span></div>`;
    })
    .join("") || `<div class="mini-row"><span>暂无会话</span><span></span></div>`;
  document.querySelectorAll("[data-session-id]").forEach((node) => {
    node.addEventListener("click", () => loadSession(node.dataset.sessionId));
  });
}

async function startSection() {
  const payload = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      mode: "section",
      question_type: el.sectionType.value,
      count: Number(el.sectionCount.value || 10),
    }),
  });
  state.activeIndex = 0;
  state.activeSince = new Map();
  setSession(payload);
  await refreshRecent();
}

async function startMock() {
  const payload = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      mode: "mock",
      template: el.mockTemplate.value,
    }),
  });
  state.activeIndex = 0;
  state.activeSince = new Map();
  setSession(payload);
  await refreshRecent();
}

async function startFavorites() {
  const payload = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      mode: "favorites",
      count: Number(el.favoriteCount.value || 20),
    }),
  });
  state.activeIndex = 0;
  state.activeSince = new Map();
  setSession(payload);
  await refreshRecent();
}

async function startMistakes() {
  const payload = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      mode: "mistakes",
      count: Number(el.mistakeCount.value || 20),
    }),
  });
  state.activeIndex = 0;
  state.activeSince = new Map();
  setSession(payload);
  await refreshRecent();
}

async function loadSession(sessionId) {
  state.activeIndex = 0;
  state.activeSince = new Map();
  setSession(await api(`/api/sessions/${sessionId}`));
}

function setSession(payload) {
  state.session = payload;
  state.activeIndex = Math.min(state.activeIndex, Math.max(0, flattenItems(payload.cards).length - 1));
  showPractice();
  renderSession();
}

function renderSession() {
  const payload = state.session;
  const session = payload.session;
  const finished = session.status === "finished";
  el.sessionTitle.textContent = session.title;
  const answered = payload.progress.answered;
  const total = payload.progress.total;
  const rate = answered ? Math.round((payload.progress.correct / answered) * 100) : 0;
  el.sessionMeta.textContent = `${finished ? "已交卷" : "作答中"} · ${answered}/${total}`;
  el.sessionTimer.textContent = `⏱ ${formatSessionElapsed(session)}`;
  el.finishSession.disabled = finished || total === 0 || answered < total;
  el.aiAnalysis.disabled = !finished || answered === 0;
  el.finishSession.textContent = finished ? `正确 ${payload.progress.correct} · ${rate}%` : "交卷";
  if (session.ai_summary) {
    el.analysisBox.textContent = session.ai_summary;
    el.analysisBox.classList.remove("hidden");
  } else {
    el.analysisBox.classList.add("hidden");
  }
  el.cards.classList.remove("empty-state");
  const slides = flattenItems(payload.cards);
  el.questionNav.classList.toggle("hidden", slides.length === 0);
  renderQuestionNav(slides);
  el.cards.innerHTML = `<div class="slide-track" style="transform: translateX(-${state.activeIndex * 100}%);">${slides
    .map(renderSlide)
    .join("")}</div>`;
  bindCardActions();
  startElapsedTimer();
}

function flattenItems(cards) {
  const slides = [];
  cards.forEach((card) => {
    card.items.forEach((item) => {
      slides.push({
        card,
        item,
      });
    });
  });
  return slides;
}

function renderQuestionNav(slides) {
  el.questionCounter.textContent = slides.length ? `${state.activeIndex + 1} / ${slides.length}` : "0 / 0";
  el.prevQuestion.disabled = state.activeIndex <= 0;
  el.nextQuestion.disabled = state.activeIndex >= slides.length - 1;
}

function renderSlide(slide) {
  const card = slide.card;
  const item = slide.item;
  const isMaterial = Boolean(card.material);
  return `
    <div class="question-slide">
      <article class="question-card">
        <div class="card-header">
          <div>
            <h3>第 ${escapeHtml(item.position)} 题</h3>
            <div class="badge-row">
              <span class="badge">${escapeHtml(item.question_type || "未分类")}</span>
              <span class="badge">原题 #${escapeHtml(item.number)}</span>
              ${isMaterial ? `<span class="badge">材料题组</span>` : ""}
            </div>
          </div>
          <div class="card-actions">
            <button data-favorite-toggle>${item.favorite ? "已重点" : "标重点"}</button>
            <span class="badge">${escapeHtml(item.source)}</span>
          </div>
        </div>
        <div class="card-scroll">
          ${card.material ? `<div class="material markdown">${renderMarkdown(card.material)}</div>` : ""}
          ${renderItem(item)}
        </div>
      </article>
    </div>
  `;
}

function renderItem(item) {
  if (!item.selected_answer && !state.activeSince.has(item.id)) {
    state.activeSince.set(item.id, Date.now());
  }
  const reveal = state.session?.session.status === "finished";
  const options = Object.entries(item.options || {})
    .map(([key, value]) => renderOption(item, key, value, reveal))
    .join("");
  return `
    <section class="question-item" data-item-id="${escapeAttr(item.id)}">
      <div class="question-body">
        <div class="badge-row">
          <span class="badge">原题 ${escapeHtml(item.source)} #${escapeHtml(item.number)}</span>
        </div>
        <div class="stem markdown">${renderMarkdown(item.stem)}</div>
        <div class="options">${options}</div>
        ${reveal ? renderAnswerPanel(item) : ""}
        ${reveal ? renderReviewPanel(item) : ""}
      </div>
    </section>
  `;
}

function renderOption(item, key, value, reveal) {
  const selected = item.selected_answer === key;
  const correct = reveal && item.answer === key;
  const wrong = reveal && selected && item.answer !== key;
  const classes = ["option", selected ? "selected" : "", correct ? "correct" : "", wrong ? "wrong" : ""].filter(Boolean).join(" ");
  return `<button class="${classes}" data-answer="${escapeAttr(key)}" ${reveal || item.selected_answer ? "disabled" : ""}><strong>${escapeHtml(key)}.</strong> ${renderMarkdown(value)}</button>`;
}

function renderAnswerPanel(item) {
  const statusClass = item.is_correct ? "good" : "bad";
  const statusText = item.is_correct ? "正确" : "错误";
  const knowledge = item.knowledge_points.map((point) => `<span class="badge">${escapeHtml(point)}</span>`).join("");
  const related = item.related_questions
    .map((q) => `<span class="badge">${escapeHtml(q.question_type || "未分类")} #${escapeHtml(q.number)}</span>`)
    .join("");
  const attempts = item.recent_attempts
    .map((attempt) => miniRow(formatDateTime(attempt.attempted_at), `${attempt.selected_answer || "-"} · ${attempt.is_correct ? "对" : "错"} · ${attempt.duration_seconds || 0}s`))
    .join("");
  return `
    <div class="answer-panel">
      <div class="answer-status ${statusClass}">${statusText} · 答案 ${escapeHtml(item.answer || "")} · ${item.duration_seconds || 0}s</div>
      <div class="badge-row">${knowledge}</div>
      <div class="markdown">${renderMarkdown(item.explanation || "")}</div>
      <div class="related-list">${related}</div>
      <div class="mini-table">${attempts}</div>
    </div>
  `;
}

function renderReviewPanel(item) {
  return `
    <div class="review-panel">
      <div class="review-grid">
        <label>错因
          <textarea data-review-field="mistake_reason">${escapeHtml(item.mistake_reason || "")}</textarea>
        </label>
        <label>复盘
          <textarea data-review-field="review_note">${escapeHtml(item.review_note || "")}</textarea>
        </label>
        <label>信心
          <input data-review-field="confidence" type="number" min="1" max="5" value="${escapeAttr(item.confidence || 3)}" />
        </label>
      </div>
      <div class="actions">
        <button data-review-save>保存复盘</button>
      </div>
    </div>
  `;
}

function bindCardActions() {
  document.querySelectorAll(".question-item").forEach((node) => {
    const itemId = node.dataset.itemId;
    node.querySelectorAll("[data-answer]").forEach((button) => {
      button.addEventListener("click", () => submitAnswer(itemId, button.dataset.answer));
    });
    const save = node.querySelector("[data-review-save]");
    if (save) {
      save.addEventListener("click", () => saveReview(itemId, node));
    }
    const favorite = node.closest(".question-card").querySelector("[data-favorite-toggle]");
    if (favorite) {
      favorite.addEventListener("click", () => toggleFavorite(itemId, favorite.textContent !== "已重点"));
    }
  });
}

async function submitAnswer(itemId, answer) {
  const started = state.activeSince.get(itemId) || Date.now();
  const duration = Math.max(1, Math.round((Date.now() - started) / 1000));
  const currentIndex = state.activeIndex;
  await api(`/api/sessions/${state.session.session.id}/items/${itemId}/answer`, {
    method: "POST",
    body: JSON.stringify({ selected_answer: answer, duration_seconds: duration }),
  });
  const payload = await api(`/api/sessions/${state.session.session.id}`);
  const total = flattenItems(payload.cards).length;
  if (currentIndex < total - 1) {
    state.activeIndex = currentIndex + 1;
  }
  setSession(payload);
  await refreshStats();
}

async function saveReview(itemId, node) {
  const body = {};
  node.querySelectorAll("[data-review-field]").forEach((field) => {
    body[field.dataset.reviewField] = field.value;
  });
  await api(`/api/sessions/${state.session.session.id}/items/${itemId}/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  setSession(await api(`/api/sessions/${state.session.session.id}`));
}

async function toggleFavorite(itemId, favorite) {
  await api(`/api/sessions/${state.session.session.id}/items/${itemId}/review`, {
    method: "POST",
    body: JSON.stringify({ favorite }),
  });
  state.metadata = await api("/api/metadata");
  setSession(await api(`/api/sessions/${state.session.session.id}`));
  await refreshStats();
}

function goQuestion(delta) {
  if (!state.session) return;
  const total = flattenItems(state.session.cards).length;
  state.activeIndex = Math.max(0, Math.min(total - 1, state.activeIndex + delta));
  renderSession();
}

function backDashboard() {
  document.body.classList.remove("practice-mode");
  el.practiceView.classList.add("hidden");
  el.dashboardView.classList.remove("hidden");
  state.session = null;
  state.activeSince = new Map();
  state.activeIndex = 0;
  stopElapsedTimer();
  el.sessionTitle.textContent = "请选择练习";
  el.sessionMeta.textContent = "SQLite 记录作答，Obsidian 承载复盘沉淀";
  el.sessionTimer.textContent = "⏱ 0:00";
  el.finishSession.disabled = true;
  el.finishSession.textContent = "交卷";
  el.aiAnalysis.disabled = true;
  el.analysisBox.classList.add("hidden");
  el.cards.className = "cards empty-state";
  el.cards.textContent = "暂无练习会话";
  el.questionNav.classList.add("hidden");
}

async function finishSession() {
  setSession(await api(`/api/sessions/${state.session.session.id}/finish`, { method: "POST", body: "{}" }));
  await refreshStats();
  await refreshRecent();
}

async function runAiAnalysis() {
  el.analysisBox.textContent = "分析中...";
  el.analysisBox.classList.remove("hidden");
  const result = await api(`/api/sessions/${state.session.session.id}/ai-analysis`, { method: "POST", body: "{}" });
  if (result.status === "missing_api_key") {
    el.analysisBox.textContent = "未设置 DEEPSEEK_API_KEY。";
    return;
  }
  el.analysisBox.textContent = result.summary || "AI 未返回总结。";
  setSession(await api(`/api/sessions/${state.session.session.id}`));
}

function metric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function showPractice() {
  document.body.classList.add("practice-mode");
  el.dashboardView.classList.add("hidden");
  el.practiceView.classList.remove("hidden");
}

function renderTypeAnalytics(stats) {
  const rows = stats.by_type.slice().sort((a, b) => b.total - a.total);
  if (!rows.length) {
    return `<div class="empty-chart">暂无分版块练习数据</div>`;
  }
  const maxTotal = Math.max(...rows.map((row) => row.total), 1);
  const maxDuration = Math.max(...rows.map((row) => Number(row.total_duration || 0)), 1);
  const typeCards = rows
    .map((row) => {
      const accuracy = Math.round(row.accuracy * 100);
      const volume = Math.round((row.total / maxTotal) * 100);
      const totalDuration = Number(row.total_duration || 0);
      const durationShare = Math.round((totalDuration / maxDuration) * 100);
      return `
        <div class="type-card">
          <div class="type-card-head">
            <strong>${escapeHtml(row.label)}</strong>
            <span>${row.correct}/${row.total}</span>
          </div>
          <div class="gauge" style="--value: ${accuracy}">
            <span>${accuracy}%</span>
          </div>
          <div class="bar-metric">
            <span>题量</span>
            <div><i style="width: ${volume}%"></i></div>
            <b>${row.total}</b>
          </div>
          <div class="bar-metric">
            <span>均时</span>
            <div><i style="width: ${Math.min(100, Math.round((row.avg_duration / 120) * 100))}%"></i></div>
            <b>${Number(row.avg_duration || 0).toFixed(1)}s</b>
          </div>
          <div class="bar-metric">
            <span>总时</span>
            <div><i style="width: ${Math.max(4, durationShare)}%"></i></div>
            <b>${formatCompactDuration(totalDuration)}</b>
          </div>
        </div>
      `;
    })
    .join("");
  return `
    <div class="trend-card">
      <div>
        <strong>近30天练习趋势</strong>
        <span>${stats.total || 0}题</span>
      </div>
      ${renderDateTrend(stats.by_date)}
    </div>
    <div class="type-card-grid">${typeCards}</div>
  `;
}

function renderDateTrend(rows) {
  const sorted = rows.slice().sort((a, b) => a.label.localeCompare(b.label)).slice(-14);
  if (!sorted.length) {
    return `<div class="trend-bars empty-chart">暂无趋势数据</div>`;
  }
  const maxTotal = Math.max(...sorted.map((row) => row.total), 1);
  return `
    <div class="trend-bars">
      ${sorted
        .map((row) => {
          const height = Math.max(8, Math.round((row.total / maxTotal) * 100));
          const accuracy = Math.round(row.accuracy * 100);
          return `<span title="${escapeAttr(row.label)} · ${row.total}题 · ${accuracy}%" style="height: ${height}%"></span>`;
        })
        .join("")}
    </div>
  `;
}

function topType(rows, key) {
  const filtered = rows.filter((row) => row.total > 0);
  if (!filtered.length) return null;
  return filtered.slice().sort((a, b) => b[key] - a[key])[0];
}

function miniRow(label, value) {
  return `<div class="mini-row"><span>${escapeHtml(label)}</span><span>${escapeHtml(value)}</span></div>`;
}

function renderMarkdown(value) {
  const text = String(value || "");
  const tokens = [];
  let html = text.replace(/!\[[^\]]*\]\(([^)]+)\)/g, (_, url) => {
    const token = `@@IMG${tokens.length}@@`;
    tokens.push(`<img src="${escapeAttr(url)}" alt="" loading="lazy" />`);
    return token;
  });
  html = escapeHtml(html)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br />");
  tokens.forEach((token, index) => {
    html = html.replace(escapeHtml(`@@IMG${index}@@`), token);
  });
  return `<p>${html}</p>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function formatDateTime(value) {
  if (!value) return "";
  return value.replace("T", " ").slice(0, 16);
}

function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds || 0));
  const minutes = Math.floor(value / 60);
  const rest = value % 60;
  if (minutes < 60) {
    return `${minutes}:${String(rest).padStart(2, "0")}`;
  }
  const hours = Math.floor(minutes / 60);
  return `${hours}:${String(minutes % 60).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatCompactDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds || 0)));
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h${rest}m` : `${hours}h`;
}

function formatSessionElapsed(session) {
  if (!session) return "0:00";
  if (session.duration_seconds != null) {
    return formatDuration(session.duration_seconds);
  }
  const started = Date.parse(session.started_at);
  if (Number.isNaN(started)) return "0:00";
  return formatDuration(Math.round((Date.now() - started) / 1000));
}

function startElapsedTimer() {
  stopElapsedTimer();
  if (!state.session || state.session.session.status === "finished") return;
  state.elapsedTimer = window.setInterval(() => {
    if (!state.session || state.session.session.status === "finished") {
      stopElapsedTimer();
      return;
    }
    el.sessionMeta.textContent = `作答中 · ${state.session.progress.answered}/${state.session.progress.total}`;
    el.sessionTimer.textContent = `⏱ ${formatSessionElapsed(state.session.session)}`;
  }, 1000);
}

function stopElapsedTimer() {
  if (state.elapsedTimer) {
    window.clearInterval(state.elapsedTimer);
    state.elapsedTimer = null;
  }
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

el.startSection.addEventListener("click", startSection);
el.startMock.addEventListener("click", startMock);
el.startFavorites.addEventListener("click", startFavorites);
el.startMistakes.addEventListener("click", startMistakes);
el.refreshStats.addEventListener("click", async () => {
  state.metadata = await api("/api/metadata");
  await refreshStats();
  await refreshRecent();
});
el.finishSession.addEventListener("click", finishSession);
el.aiAnalysis.addEventListener("click", runAiAnalysis);
el.prevQuestion.addEventListener("click", () => goQuestion(-1));
el.nextQuestion.addEventListener("click", () => goQuestion(1));
el.backDashboard.addEventListener("click", backDashboard);

init().catch((error) => {
  el.cards.classList.add("empty-state");
  el.cards.textContent = error.message;
});
