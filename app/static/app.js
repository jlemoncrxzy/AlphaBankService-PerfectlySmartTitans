// Минималистичный SPA: JWT в localStorage, fetch-обёртка, hash-роутинг по кнопкам.
const state = {
  token: localStorage.getItem("token") || "",
  role: localStorage.getItem("role") || "",
  pollTimer: null,
};
const $ = (id) => document.getElementById(id);

// ---------- API-обёртка ----------
async function api(path, opts = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(opts.headers || {}),
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    logout();
    throw new Error("Сессия истекла, войдите снова");
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

// ---------- Авторизация ----------
async function login(username, password) {
  const body = new URLSearchParams({ username, password });
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Неверные учётные данные");
  const data = await res.json();
  state.token = data.access_token;
  state.role = data.role;
  localStorage.setItem("token", state.token);
  localStorage.setItem("role", state.role);
}

function logout() {
  state.token = "";
  state.role = "";
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  stopPolling();
  showLogin();
}

// ---------- Роутинг ----------
function showLogin() {
  $("login-screen").classList.remove("hidden");
  $("view").classList.add("hidden");
  $("nav").classList.add("hidden");
}

function showApp() {
  $("login-screen").classList.add("hidden");
  $("nav").classList.remove("hidden");
  $("view").classList.remove("hidden");
  $("whoami").textContent = `(${state.role})`;
}

async function route(view) {
  stopPolling();
  if (view === "clients") return viewClients();
  if (view === "news") return viewNews();
  if (view === "runs") return viewRuns();
}

// ---------- Экраны ----------
let currentClientsPage = 1;
const CLIENTS_PAGE_SIZE = 20;

async function viewClients(page = 1) {
  currentClientsPage = page;
  const canRun = state.role === "admin" || state.role === "analyst";
  
  try {
    const data = await api(`/api/clients?page=${page}&size=${CLIENTS_PAGE_SIZE}`);
    
    if (!data || !data.items) {
      throw new Error("Некорректный ответ от сервера. Перезапустите uvicorn.");
    }

    const clients = data.items;
    const totalPages = Math.ceil(data.total / CLIENTS_PAGE_SIZE);

    let paginationHtml = `<div style="margin-top: 16px; display: flex; gap: 10px; align-items: center;">`;
    paginationHtml += `<button ${page === 1 ? 'disabled' : ''} id="btn-prev">← Назад</button>`;
    paginationHtml += `<span>Страница ${page} из ${totalPages || 1} (Всего: ${data.total})</span>`;
    paginationHtml += `<button ${page === totalPages || totalPages === 0 ? 'disabled' : ''} id="btn-next">Вперед →</button>`;
    paginationHtml += `</div>`;

    $("view").innerHTML = `
      <h2>Клиенты</h2>
      <table>
        <thead><tr><th>Название</th><th>Отрасль</th><th>Выручка, млрд ₽</th><th>Сотрудники</th><th></th></tr></thead>
        <tbody>
          ${clients.length ? clients.map(c => `
            <tr>
              <td><a href="#" data-client="${c.id}">${escapeHtml(c.name)}</a></td>
              <td>${escapeHtml(c.industry)}</td>
              <td>${((c.scale_revenue_rub || 0) / 1e9).toFixed(1)}</td>
              <td>${(c.scale_employees || 0).toLocaleString("ru")}</td>
              <td>${canRun ? `<button data-analyze="${c.id}">Запустить анализ</button>` : `<span class="hint">только чтение</span>`}</td>
            </tr>`).join("") : `<tr><td colspan="5" class="hint">Клиентов пока нет. Запустите ingest_csv.py</td></tr>`}
        </tbody>
      </table>
      ${paginationHtml}
      <div id="client-detail" class="card hidden" style="margin-top: 24px;"></div>
    `;

    if ($("btn-prev")) $("btn-prev").addEventListener("click", () => viewClients(page - 1));
    if ($("btn-next")) $("btn-next").addEventListener("click", () => viewClients(page + 1));

    $("view").querySelectorAll("[data-client]").forEach(el =>
      el.addEventListener("click", async (e) => {
        e.preventDefault();
        const id = Number(el.dataset.client);
        try {
          const c = await api(`/api/clients/${id}`);
          $("client-detail").classList.remove("hidden");
          $("client-detail").innerHTML = `
            <h3>${escapeHtml(c.name)}</h3>
            <p><b>Отрасль:</b> ${escapeHtml(c.industry)}<br/>
               <b>Выручка:</b> ${((c.scale_revenue_rub || 0) / 1e9).toFixed(1)} млрд ₽<br/>
               <b>Сотрудники:</b> ${(c.scale_employees || 0).toLocaleString("ru")}</p>
            <p><b>Описание:</b> ${escapeHtml(c.description || "—")}</p>
            ${c.profile ? `
              <p><b>Продукты:</b> ${(c.profile.products || []).map(escapeHtml).join(", ") || "—"}</p>
              <p><b>Регионы:</b> ${(c.profile.regions || []).map(escapeHtml).join(", ") || "—"}</p>
              <p><b>Ключевые слова:</b> ${(c.profile.keywords || []).map(escapeHtml).join(", ") || "—"}</p>
              <p><b>Контрагенты:</b></p>
              <ul style="max-height: 200px; overflow-y: auto;">
                ${(c.profile.counterparties || []).map(cp =>
                  `<li>${escapeHtml(cp.name)} — <i>${cp.role}</i>${cp.share ? " (доля " + cp.share + ")" : ""}</li>`
                ).join("") || "<li>—</li>"}
              </ul>
              <p><b>Риски (заметки):</b> ${escapeHtml(c.profile.risk_notes || "—")}</p>
            ` : ""}
          `;
          $("client-detail").scrollIntoView({ behavior: 'smooth' });
        } catch (err) {
          alert("Ошибка загрузки профиля: " + err.message);
        }
      })
    );

    $("view").querySelectorAll("[data-analyze]").forEach(el =>
      el.addEventListener("click", async () => {
        const id = Number(el.dataset.analyze);
        el.disabled = true;
        el.textContent = "Запуск…";
        try {
          const r = await api(`/api/clients/${id}/analyze`, { method: "POST" });
          await viewRun(r.run_id);
        } catch (e) {
          alert("Ошибка запуска: " + e.message);
          el.disabled = false;
          el.textContent = "Запустить анализ";
        }
      })
    );
  } catch (error) {
    $("view").innerHTML = `
      <h2>Клиенты</h2>
      <div class="card" style="border-left: 4px solid #b00020;">
        <h3 class="error">Не удалось загрузить клиентов</h3>
        <p>${escapeHtml(error.message)}</p>
        <p class="hint">Проверьте консоль разработчика (F12) и логи сервера. Убедитесь, что вы перезапустили <code>uvicorn</code> после изменения файлов.</p>
      </div>
    `;
  }
}

async function viewNews() {
  const [news, analytics] = await Promise.all([
    api("/api/news?limit=30"),
    api("/api/analytics?limit=30"),
  ]);
  $("view").innerHTML = `
    <h2>Новости</h2>
    <table>
      <thead><tr><th>Дата</th><th>Заголовок</th><th>Источник</th><th>Magnitude</th></tr></thead>
      <tbody>
        ${news.map(n => `
          <tr>
            <td>${fmtDate(n.published_at)}</td>
            <td>${escapeHtml(n.title)}<br/><span class="hint">${escapeHtml(n.body || "")}</span></td>
            <td>${escapeHtml(n.source)}</td>
            <td>${n.magnitude.toFixed(2)}</td>
          </tr>`).join("")}
      </tbody>
    </table>
    <h2 style="margin-top:24px">Аналитика Альфа-Банка</h2>
    <table>
      <thead><tr><th>Дата</th><th>Заголовок</th><th>Категория</th></tr></thead>
      <tbody>
        ${analytics.map(a => `
          <tr>
            <td>${fmtDate(a.published_at)}</td>
            <td>${escapeHtml(a.title)}<br/><span class="hint">${escapeHtml(a.body || "")}</span></td>
            <td>${escapeHtml(a.category)}</td>
          </tr>`).join("")}
      </tbody>
    </table>
  `;
}

async function viewRuns() {
  const runs = await api("/api/runs");
  $("view").innerHTML = `
    <h2>Запуски анализа</h2>
    <table>
      <thead><tr><th>ID</th><th>Клиент</th><th>Статус</th><th>Модель</th><th>Начат</th><th>Завершён</th></tr></thead>
      <tbody>
        ${runs.map(r => `
          <tr class="clickable" data-run="${r.id}">
            <td>${r.id}</td>
            <td>${r.client_id}</td>
            <td>${statusBadge(r.status)}</td>
            <td class="mono">${escapeHtml(r.model || "—")}</td>
            <td>${fmtDate(r.created_at)}</td>
            <td>${r.finished_at ? fmtDate(r.finished_at) : "—"}</td>
          </tr>`).join("") || `<tr><td colspan="6" class="hint">Запусков пока нет</td></tr>`}
      </tbody>
    </table>
    <div id="run-detail"></div>
  `;
  $("view").querySelectorAll("[data-run]").forEach(el =>
    el.addEventListener("click", () => viewRun(Number(el.dataset.run)))
  );
}

async function viewRun(runId) {
  stopPolling();
  $("view").innerHTML = `<h2>Run #${runId}</h2><div id="run-box" class="card">Загрузка…</div>`;

  async function refresh() {
    try {
      const r = await api(`/api/runs/${runId}`);
      const done = r.status === "done" || r.status === "failed";
      $("run-box").innerHTML = `
        <p><b>Статус:</b> ${statusBadge(r.status)} &nbsp;
           <b>Модель:</b> <span class="mono">${escapeHtml(r.model || "—")}</span></p>
        ${r.error ? `<p class="error">${escapeHtml(r.error)}</p>` : ""}
        ${r.summary ? `<p><b>Резюме:</b> ${escapeHtml(r.summary)}</p>` : ""}

        <h3>Шаги пайплайна</h3>
        ${r.steps.map(s => `
          <div class="step">
            <b>${s.index}. ${escapeHtml(s.name)}</b>
            — <span class="${s.status === "ok" ? "" : "error"}">${s.status}</span>
            <div class="hint">${fmtDate(s.started_at)} → ${s.finished_at ? fmtDate(s.finished_at) : "…"}</div>
            ${s.notes ? `<div class="error">${escapeHtml(s.notes)}</div>` : ""}
            <details><summary>inputs / output</summary>
              <pre>${escapeHtml(JSON.stringify({ inputs: s.inputs, output: s.output }, null, 2))}</pre>
            </details>
          </div>`).join("")}

        <h3>Инсайты (${r.insights.length})</h3>
        ${r.insights.map(i => renderInsight(i)).join("") || `<p class="hint">Пока нет</p>`}
      `;

      if (!done) {
        state.pollTimer = setTimeout(refresh, 1000);
      } else if (state.role === "admin" || state.role === "analyst") {
        const tools = await api(`/api/runs/${runId}/tools`);
        $("run-box").insertAdjacentHTML("beforeend", `
          <h3>Журнал инструментов (${tools.length})</h3>
          <table>
            <thead><tr><th>Время</th><th>Инструмент</th><th>Разрешён</th><th>Результат</th><th>Params</th></tr></thead>
            <tbody>
              ${tools.map(t => `
                <tr>
                  <td>${fmtDate(t.created_at)}</td>
                  <td class="mono">${escapeHtml(t.tool)}</td>
                  <td>${t.allowed ? "✅" : `<span class="error">❌ ${escapeHtml(t.reason)}</span>`}</td>
                  <td>${escapeHtml(t.result_summary || "")}</td>
                  <td><pre class="mono">${escapeHtml(JSON.stringify(t.params))}</pre></td>
                </tr>`).join("")}
            </tbody>
          </table>
        `);
      }
    } catch (e) {
      $("run-box").innerHTML = `<p class="error">Ошибка: ${escapeHtml(e.message)}</p>`;
    }
  }
  await refresh();
}

function renderInsight(i) {
  const p = i.impact || {};
  const kind = p.kind || "neutral";
  return `
    <div class="card">
      <div><span class="badge ${kind}">${kind}</span>
           &nbsp;<b>${escapeHtml(p.headline || i.title)}</b></div>
      <div class="hint">Источник: ${escapeHtml(i.source_type)} #${i.source_id} ·
           relevance ${i.relevance_score.toFixed(2)} · confidence ${p.confidence ?? "—"} ·
           попыток ${i.attempts}</div>
      <p><b>Механизм влияния:</b> ${escapeHtml(p.mechanism || "—")}</p>
      ${p.affected_business_lines?.length ? `<p><b>Затронутые линии:</b> ${p.affected_business_lines.map(escapeHtml).join(", ")}</p>` : ""}
      ${p.recommended_actions?.length ? `<p><b>Рекомендации:</b></p><ul>${p.recommended_actions.map(a => `<li>${escapeHtml(a)}</li>`).join("")}</ul>` : ""}
      ${p.caveats?.length ? `<p class="hint"><b>Оговорки:</b> ${p.caveats.map(escapeHtml).join("; ")}</p>` : ""}
      <details><summary>Источники (${i.sources.length})</summary>
        <pre>${escapeHtml(JSON.stringify(i.sources, null, 2))}</pre>
      </details>
    </div>`;
}

// ---------- Утилиты ----------
function statusBadge(s) {
  const map = { pending: "#999", running: "#0a84ff", done: "#0a7c2f", failed: "#b00020" };
  return `<span class="badge" style="background:${map[s] || "#666"}">${s}</span>`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { hour12: false });
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function stopPolling() {
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
}

// ---------- Инициализация ----------
$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await login(fd.get("username"), fd.get("password"));
    $("login-error").textContent = "";
    showApp();
    route("clients");
  } catch (err) {
    $("login-error").textContent = err.message;
  }
});

$("logout").addEventListener("click", logout);

document.querySelectorAll("#nav button[data-view]").forEach(btn =>
  btn.addEventListener("click", () => route(btn.dataset.view))
);

(async () => {
  if (state.token) {
    try {
      await api("/api/auth/me");
      showApp();
      route("clients");
      return;
    } catch (_) {}
  }
  showLogin();
})();