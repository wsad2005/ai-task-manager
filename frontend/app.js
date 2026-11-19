/* AI Task Manager 前端逻辑：无框架，Fetch API + localStorage 令牌。 */
"use strict";

// ---------------------------------------------------------------- 状态
const state = {
  token: localStorage.getItem("token") || "",
  user: JSON.parse(localStorage.getItem("user") || "null"),
  view: "dashboard",
  filters: {
    status: "",
    priority: "",
    overdue: "",
    q: "",
    category: "",
    sort_by: "created_at",
    order: "desc",
  },
  skip: 0,
  limit: 10,
  total: 0,
  editingTaskId: null,
  authMode: "login",
};

const PRIORITY_LABEL = { urgent: "紧急", high: "高", medium: "中", low: "低" };
const STATUS_LABEL = { todo: "未完成", done: "已完成" };

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- API 封装
async function api(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const response = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return null;

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && state.token) logout("登录已过期，请重新登录");
    const err = data.error || {};
    const error = new Error(err.message || `请求失败（HTTP ${response.status}）`);
    error.code = err.code;
    error.detail = err.detail;
    throw error;
  }
  return data;
}

// ---------------------------------------------------------------- 小工具
function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

let toastTimer = null;
function toast(message, type = "success") {
  const el = $("toast");
  el.textContent = message;
  el.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 2600);
}

function showError(id, message) {
  const el = $(id);
  el.textContent = message;
  el.classList.remove("hidden");
}

// ---------------------------------------------------------------- 会话
function saveSession(data) {
  state.token = data.access_token;
  state.user = data.user;
  localStorage.setItem("token", state.token);
  localStorage.setItem("user", JSON.stringify(state.user));
}

function logout(message) {
  state.token = "";
  state.user = null;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  $("topbar").classList.add("hidden");
  switchView("auth");
  if (message) toast(message, "error");
}

// ---------------------------------------------------------------- 视图切换
function switchView(name) {
  state.view = name;
  for (const section of document.querySelectorAll(".view")) section.classList.add("hidden");
  $(`view-${name}`).classList.remove("hidden");
  document.querySelectorAll(".nav-btn[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  if (name === "dashboard") loadDashboard();
  if (name === "tasks") loadTasks();
}

function showApp() {
  $("topbar").classList.remove("hidden");
  $("current-user").textContent = `@${state.user.username}`;
  switchView("dashboard");
}

// ---------------------------------------------------------------- 认证
function setAuthMode(mode) {
  state.authMode = mode;
  $("tab-login").classList.toggle("active", mode === "login");
  $("tab-register").classList.toggle("active", mode === "register");
  $("auth-submit").textContent = mode === "login" ? "登录" : "注册";
  $("auth-error").classList.add("hidden");
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const username = form.username.value.trim();
  const password = form.password.value;
  const submit = $("auth-submit");
  submit.disabled = true;
  $("auth-error").classList.add("hidden");
  try {
    if (state.authMode === "register") {
      await api("/api/auth/register", { method: "POST", body: { username, password } });
      toast("注册成功，已自动登录");
    }
    const data = await api("/api/auth/login", { method: "POST", body: { username, password } });
    saveSession(data);
    form.reset();
    showApp();
  } catch (error) {
    showError("auth-error", error.message);
  } finally {
    submit.disabled = false;
  }
}

// ---------------------------------------------------------------- 仪表盘
async function loadDashboard() {
  const cards = $("stats-cards");
  cards.textContent = "加载中…";
  try {
    const stats = await api("/api/statistics");
    const rate = (stats.completion_rate * 100).toFixed(1);
    cards.innerHTML = [
      card("总任务", stats.total_tasks),
      card("已完成", stats.completed_tasks),
      card("待办", stats.pending_tasks),
      card("逾期", stats.overdue_tasks, stats.overdue_tasks > 0 ? "danger" : ""),
      card("完成率", `${rate}%`),
    ].join("");
    const priority = Object.entries(stats.by_priority)
      .map(([name, count]) => `<span class="chip">${PRIORITY_LABEL[name] || name}：${count}</span>`)
      .join("");
    const maxCount = Math.max(1, ...stats.trend.map((point) => Math.max(point.created, point.completed)));
    $("trend").innerHTML =
      `<div class="chips">${priority}</div>` +
      `<div class="trend-bars">` +
      stats.trend
        .map((point) => {
          const createdHeight = Math.round((point.created / maxCount) * 100);
          const completedHeight = Math.round((point.completed / maxCount) * 100);
          return `<div class="trend-day">
            <div class="trend-cols">
              <div class="bar created" style="height:${createdHeight}%" title="新建 ${point.created}"></div>
              <div class="bar completed" style="height:${completedHeight}%" title="完成 ${point.completed}"></div>
            </div>
            <span class="trend-date">${point.date.slice(5)}</span>
            <span class="trend-count">${point.created} / ${point.completed}</span>
          </div>`;
        })
        .join("") +
      `</div><p class="muted small">柱状图：左=新建，右=完成；下方数字为 新建/完成</p>`;
  } catch (error) {
    cards.textContent = `统计加载失败：${error.message}`;
  }
}

function card(label, value, extraClass = "") {
  return `<div class="stat-card ${extraClass}"><span class="stat-value">${esc(value)}</span><span class="stat-label">${esc(label)}</span></div>`;
}

// ---------------------------------------------------------------- 任务列表
function buildQuery() {
  const params = new URLSearchParams();
  for (const key of ["status", "priority", "category", "q", "sort_by", "order"]) {
    if (state.filters[key]) params.set(key, state.filters[key]);
  }
  if (state.filters.overdue) params.set("overdue", "true");
  params.set("skip", String(state.skip));
  params.set("limit", String(state.limit));
  return params.toString();
}

async function loadTasks() {
  const list = $("task-list");
  list.textContent = "加载中…";
  try {
    const data = await api(`/api/tasks?${buildQuery()}`);
    state.total = data.total;
    if (data.items.length === 0) {
      list.innerHTML = `<p class="empty">暂无任务。点击右上角“＋ 新建任务”开始。</p>`;
    } else {
      list.innerHTML = data.items.map(renderTask).join("");
    }
    const page = Math.floor(state.skip / state.limit) + 1;
    const totalPages = Math.max(1, Math.ceil(data.total / state.limit));
    $("page-info").textContent = `第 ${page} / ${totalPages} 页 · 共 ${data.total} 条`;
    $("prev-page").disabled = state.skip === 0;
    $("next-page").disabled = state.skip + state.limit >= data.total;
  } catch (error) {
    list.textContent = `加载失败：${error.message}`;
  }
}

function renderTask(task) {
  const overdueBadge = task.overdue ? `<span class="badge overdue">逾期</span>` : "";
  const due = task.due_date ? `<span class="meta">截止：${esc(task.due_date)}</span>` : "";
  const category = task.category ? `<span class="meta">分类：${esc(task.category)}</span>` : "";
  const tags = task.tags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join("");
  const doneButton =
    task.status === "done"
      ? `<button class="ghost" data-action="restore" data-id="${task.id}">恢复</button>`
      : `<button class="ghost" data-action="complete" data-id="${task.id}">完成</button>`;
  return `<div class="task-item ${task.status === "done" ? "done" : ""}">
    <div class="task-main">
      <span class="task-title">${esc(task.title)}</span>
      <span class="badge status-${task.status}">${STATUS_LABEL[task.status]}</span>
      <span class="badge priority-${task.priority}">${PRIORITY_LABEL[task.priority]}</span>
      ${overdueBadge}
    </div>
    ${task.description ? `<p class="task-desc">${esc(task.description)}</p>` : ""}
    <div class="task-meta">${due}${category}${tags ? `<span class="tags">${tags}</span>` : ""}</div>
    <div class="task-actions">
      ${doneButton}
      <button class="ghost" data-action="edit" data-id="${task.id}">编辑</button>
      <button class="ghost danger" data-action="delete" data-id="${task.id}">删除</button>
    </div>
  </div>`;
}

async function handleTaskListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const { action, id } = button.dataset;
  try {
    if (action === "complete") {
      await api(`/api/tasks/${id}/complete`, { method: "POST" });
      toast("任务已完成");
    } else if (action === "restore") {
      await api(`/api/tasks/${id}/restore`, { method: "POST" });
      toast("任务已恢复为未完成");
    } else if (action === "delete") {
      if (!confirm("确定删除该任务？此操作不可恢复。")) return;
      await api(`/api/tasks/${id}`, { method: "DELETE" });
      toast("任务已删除");
    } else if (action === "edit") {
      await openTaskDialog(id);
      return;
    }
    loadTasks();
    if (state.view === "dashboard") loadDashboard();
  } catch (error) {
    toast(`操作失败：${error.message}`, "error");
  }
}

// ---------------------------------------------------------------- 任务对话框
async function openTaskDialog(taskId = null) {
  state.editingTaskId = taskId;
  const form = $("task-form");
  form.reset();
  $("task-error").classList.add("hidden");
  $("task-dialog-title").textContent = taskId ? "编辑任务" : "新建任务";
  if (taskId) {
    try {
      const task = await api(`/api/tasks/${taskId}`);
      form.title.value = task.title;
      form.description.value = task.description || "";
      form.priority.value = task.priority;
      form.due_date.value = task.due_date || "";
      form.category.value = task.category || "";
      form.tags.value = (task.tags || []).join(", ");
    } catch (error) {
      toast(`加载任务失败：${error.message}`, "error");
      return;
    }
  }
  $("task-dialog").showModal();
}

async function handleTaskSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const payload = {
    title: form.title.value,
    description: form.description.value,
    priority: form.priority.value,
    due_date: form.due_date.value || null,
    category: form.category.value || null,
    tags: form.tags.value.split(",").map((tag) => tag.trim()).filter(Boolean),
  };
  $("task-save").disabled = true;
  try {
    if (state.editingTaskId) {
      await api(`/api/tasks/${state.editingTaskId}`, { method: "PATCH", body: payload });
      toast("任务已更新");
    } else {
      await api("/api/tasks", { method: "POST", body: payload });
      toast("任务已创建");
    }
    $("task-dialog").close();
    loadTasks();
    if (state.view === "dashboard") loadDashboard();
  } catch (error) {
    showError("task-error", error.message);
  } finally {
    $("task-save").disabled = false;
  }
}

// ---------------------------------------------------------------- 事件绑定
function bindEvents() {
  $("tab-login").addEventListener("click", () => setAuthMode("login"));
  $("tab-register").addEventListener("click", () => setAuthMode("register"));
  $("auth-form").addEventListener("submit", handleAuthSubmit);

  $("logout-btn").addEventListener("click", () => logout());
  document.querySelectorAll(".nav-btn[data-view]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  $("new-task-btn").addEventListener("click", () => openTaskDialog(null));
  $("task-cancel").addEventListener("click", () => $("task-dialog").close());
  $("task-form").addEventListener("submit", handleTaskSubmit);
  $("task-list").addEventListener("click", handleTaskListClick);

  $("filter-status").addEventListener("change", () => {
    state.filters.status = $("filter-status").value;
    state.skip = 0;
    loadTasks();
  });
  $("filter-priority").addEventListener("change", () => {
    state.filters.priority = $("filter-priority").value;
    state.skip = 0;
    loadTasks();
  });
  $("filter-overdue").addEventListener("change", () => {
    state.filters.overdue = $("filter-overdue").value;
    state.skip = 0;
    loadTasks();
  });
  $("filter-q").addEventListener("change", () => {
    state.filters.q = $("filter-q").value.trim();
    state.skip = 0;
    loadTasks();
  });
  $("sort-by").addEventListener("change", () => {
    state.filters.sort_by = $("sort-by").value;
    loadTasks();
  });
  $("order").addEventListener("change", () => {
    state.filters.order = $("order").value;
    loadTasks();
  });
  $("reset-filters").addEventListener("click", () => {
    state.filters = {
      status: "", priority: "", overdue: "", q: "", category: "",
      sort_by: "created_at", order: "desc",
    };
    state.skip = 0;
    $("filter-status").value = "";
    $("filter-priority").value = "";
    $("filter-overdue").value = "";
    $("filter-q").value = "";
    $("sort-by").value = "created_at";
    $("order").value = "desc";
    loadTasks();
  });
  $("prev-page").addEventListener("click", () => {
    state.skip = Math.max(0, state.skip - state.limit);
    loadTasks();
  });
  $("next-page").addEventListener("click", () => {
    if (state.skip + state.limit < state.total) {
      state.skip += state.limit;
      loadTasks();
    }
  });

  $("ai-breakdown-btn").addEventListener("click", runBreakdown);
  $("ai-breakdown-preview").addEventListener("input", updatePreviewItem);
  $("ai-confirm-btn").addEventListener("click", confirmBreakdown);
  $("ai-daily-btn").addEventListener("click", runDailyPlan);
}

// ---------------------------------------------------------------- AI 任务拆解
let previewItems = [];

async function runBreakdown() {
  const goal = $("ai-goal").value.trim();
  const errorEl = $("ai-breakdown-error");
  errorEl.classList.add("hidden");
  if (goal.length < 2) {
    showError("ai-breakdown-error", "请先输入至少 2 个字符的目标描述");
    return;
  }
  const button = $("ai-breakdown-btn");
  button.disabled = true;
  button.textContent = "生成中…";
  $("ai-breakdown-preview").innerHTML = "";
  $("ai-confirm-btn").classList.add("hidden");
  try {
    const data = await api("/api/ai/breakdown", { method: "POST", body: { goal } });
    previewItems = data.items;
    renderPreview();
    if (previewItems.length) {
      $("ai-confirm-btn").classList.remove("hidden");
      toast(`已生成 ${previewItems.length} 个子任务预览`);
    }
  } catch (error) {
    showError("ai-breakdown-error", error.message);
  } finally {
    button.disabled = false;
    button.textContent = "生成拆解预览";
  }
}

function renderPreview() {
  const container = $("ai-breakdown-preview");
  container.innerHTML = previewItems
    .map((item, index) => {
      const options = ["urgent", "high", "medium", "low"]
        .map((p) => `<option value="${p}" ${p === item.priority ? "selected" : ""}>${PRIORITY_LABEL[p]}</option>`)
        .join("");
      return `<div class="ai-item">
        <div class="ai-item-head">
          <span class="badge">#${index + 1}</span>
          <input data-index="${index}" data-field="title" value="${esc(item.title)}" maxlength="200">
        </div>
        <textarea data-index="${index}" data-field="description" rows="2" maxlength="500">${esc(item.description)}</textarea>
        <div class="ai-item-row">
          <select data-index="${index}" data-field="priority">${options}</select>
          <label class="small">几天内完成
            <input type="number" min="0" max="365" data-index="${index}" data-field="due_in_days" value="${item.due_in_days}">
          </label>
          <label class="small">预计分钟
            <input type="number" min="5" max="480" data-index="${index}" data-field="estimated_minutes" value="${item.estimated_minutes}">
          </label>
          <span class="badge">建议截止：${esc(item.suggested_due_date)}</span>
        </div>
      </div>`;
    })
    .join("");
}

function updatePreviewItem(event) {
  const target = event.target;
  const index = Number(target.dataset.index);
  const field = target.dataset.field;
  if (Number.isNaN(index) || !field || !previewItems[index]) return;

  if (field === "title") {
    previewItems[index].title = target.value;
  } else if (field === "description") {
    previewItems[index].description = target.value;
  } else if (field === "priority") {
    previewItems[index].priority = target.value;
  } else if (field === "due_in_days") {
    previewItems[index].due_in_days = Math.max(0, Number(target.value) || 0);
    previewItems[index].suggested_due_date = new Date(
      Date.now() + previewItems[index].due_in_days * 86400000
    )
      .toISOString()
      .slice(0, 10);
    target.closest(".ai-item-row").querySelector(".badge").textContent =
      `建议截止：${previewItems[index].suggested_due_date}`;
  } else if (field === "estimated_minutes") {
    previewItems[index].estimated_minutes = Number(target.value) || 60;
  }
}

async function confirmBreakdown() {
  if (!previewItems.length) return;
  const button = $("ai-confirm-btn");
  button.disabled = true;
  try {
    const items = previewItems.map((item) => ({
      title: item.title,
      description: item.description,
      priority: item.priority,
      due_date: item.suggested_due_date,
      category: "AI 拆解",
      tags: ["AI"],
    }));
    const data = await api("/api/ai/breakdown/confirm", { method: "POST", body: { items } });
    toast(`已保存 ${data.created} 个任务`);
    previewItems = [];
    $("ai-breakdown-preview").innerHTML = "";
    $("ai-confirm-btn").classList.add("hidden");
    switchView("tasks");
  } catch (error) {
    showError("ai-breakdown-error", `保存失败：${error.message}`);
  } finally {
    button.disabled = false;
  }
}

// ---------------------------------------------------------------- AI 每日计划
async function runDailyPlan() {
  $("ai-daily-error").classList.add("hidden");
  const result = $("ai-daily-result");
  result.innerHTML = `<p class="muted">生成中…</p>`;
  const button = $("ai-daily-btn");
  button.disabled = true;
  button.textContent = "生成中…";
  try {
    const plan = await api("/api/ai/daily-plan", { method: "POST" });
    if (plan.source_count === 0) {
      result.innerHTML = `<div class="plan-card"><p>${esc(plan.daily_goal)}</p></div>`;
      return;
    }
    result.innerHTML = `
      <div class="plan-card">
        <h3>${esc(plan.daily_goal)}</h3>
        <ol class="focus-list">
          ${plan.focus
            .map(
              (item) => `<li><strong>${esc(item.task_title)}</strong>
                <span class="badge">${esc(item.time_slot)}</span>
                <p class="muted small">${esc(item.reason)}</p></li>`
            )
            .join("")}
        </ol>
      </div>
      ${
        plan.overdue_reminders.length
          ? `<div class="plan-card reminders"><h3>逾期提醒</h3><ul>${plan.overdue_reminders
              .map((item) => `<li>${esc(item)}</li>`)
              .join("")}</ul></div>`
          : ""
      }
      <p class="muted small">基于 ${plan.source_count} 个真实未完成任务生成</p>`;
  } catch (error) {
    result.innerHTML = "";
    showError("ai-daily-error", error.message);
  } finally {
    button.disabled = false;
    button.textContent = "生成今日计划";
  }
}

// ---------------------------------------------------------------- 启动
bindEvents();
if (state.token && state.user) {
  showApp();
} else {
  switchView("auth");
}
