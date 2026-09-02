const API = window.ASSESS_API || "/assessments-api";

let currentUser = null;
let STUDENT_ID = null;

function readUser() {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

const STATUS_LABELS = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
};

const state = {
  assignments: [],
  filter: "",
};


function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(message, kind = "info") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `toast toast--${kind} toast--visible`;
  setTimeout(() => el.classList.remove("toast--visible"), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function daysUntil(dueDate) {
  if (!dueDate) return null;
  const due = new Date(`${dueDate}T23:59`);
  if (Number.isNaN(due.getTime())) return null;
  return Math.ceil((due - new Date()) / 86400000);
}


async function loadAssignments() {
  const list = document.getElementById("assignments-list");
  try {
    const data = await api("/assignments");
    state.assignments = Array.isArray(data) ? data : data.assignments || [];
    render();
  } catch (error) {
    list.innerHTML = `<p class="empty">Could not load assessments: ${escapeHtml(error.message)}</p>`;
  }
}

function render() {
  const list = document.getElementById("assignments-list");
  const shown = state.filter
    ? state.assignments.filter((a) => a.status === state.filter)
    : state.assignments;


  const open = state.assignments.filter((a) => a.status !== "completed");
  const done = state.assignments.filter((a) => a.status === "completed");
  const weight = open.reduce((sum, a) => sum + (Number(a.weighting) || 0), 0);

  document.getElementById("stat-total").textContent = state.assignments.length;
  document.getElementById("stat-open").textContent = open.length;
  document.getElementById("stat-done").textContent = done.length;
  document.getElementById("stat-weight").textContent = `${weight}%`;

  document.getElementById("list-heading").textContent = state.filter
    ? STATUS_LABELS[state.filter]
    : "All assessments";
  document.getElementById("list-count").textContent =
    `${shown.length} item${shown.length === 1 ? "" : "s"}`;

  if (!shown.length) {
    list.innerHTML = `<p class="empty">Nothing here.</p>`;
    return;
  }

  const sorted = [...shown].sort((a, b) =>
    String(a.due_date).localeCompare(String(b.due_date))
  );

  list.innerHTML = sorted
    .map((a) => {
      const days = daysUntil(a.due_date);
      const overdue = days !== null && days < 0 && a.status !== "completed";
      const soon = days !== null && days >= 0 && days <= 7 && a.status !== "completed";

      let due = escapeHtml(a.due_date || "");
      if (overdue) due += ` · ${Math.abs(days)}d overdue`;
      else if (soon) due += days === 0 ? " · due today" : ` · in ${days}d`;

      return `
      <article class="assignment assignment--${escapeHtml(a.status)}">
        <div class="assignment__main">
          <h3 class="assignment__title">${escapeHtml(a.title)}</h3>
          <p class="assignment__desc">${escapeHtml(a.description || "")}</p>
          <div class="assignment__meta">
            <span class="assignment__course">Course ${escapeHtml(a.course_id)}</span>
            <span class="assignment__due${overdue ? " is-overdue" : soon ? " is-soon" : ""}">${due}</span>
            ${a.weighting ? `<span class="assignment__weight">${escapeHtml(a.weighting)}%</span>` : ""}
          </div>
        </div>
        <div class="assignment__side">
          <span class="badge ${a.status === "completed" ? "badge--ok" : a.status === "in_progress" ? "badge--warn" : ""}">
            ${escapeHtml(STATUS_LABELS[a.status] || a.status)}
          </span>
          <select class="status-select" data-id="${a.assignment_id}">
            ${Object.entries(STATUS_LABELS)
              .map(([value, label]) =>
                `<option value="${value}"${value === a.status ? " selected" : ""}>${label}</option>`)
              .join("")}
          </select>
          <div class="assignment__actions">
            <button class="btn btn--small edit-btn" data-id="${a.assignment_id}">EDIT</button>
            <button class="btn btn--small btn--danger delete-btn" data-id="${a.assignment_id}">DELETE</button>
          </div>
        </div>
      </article>`;
    })
    .join("");

  list.querySelectorAll(".status-select").forEach((select) => {
    select.addEventListener("change", () =>
      changeStatus(Number(select.dataset.id), select.value)
    );
  });
  list.querySelectorAll(".edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => openForm(Number(btn.dataset.id)));
  });
  list.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", () => remove(Number(btn.dataset.id)));
  });
}

async function changeStatus(id, status) {
  try {
    await api(`/assignments/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    const target = state.assignments.find((a) => a.assignment_id === id);
    if (target) target.status = status;
    render();
    toast(`Marked ${STATUS_LABELS[status].toLowerCase()}`, "success");
  } catch (error) {
    toast(`Could not update: ${error.message}`, "error");
    loadAssignments();
  }
}

async function remove(id) {
  const target = state.assignments.find((a) => a.assignment_id === id);
  if (!window.confirm(`Delete "${target ? target.title : "this assessment"}"?`)) return;

  try {
    await api(`/assignments/${id}`, { method: "DELETE" });
    state.assignments = state.assignments.filter((a) => a.assignment_id !== id);
    render();
    toast("Assessment deleted", "success");
  } catch (error) {
    toast(`Delete failed: ${error.message}`, "error");
  }
}

function openForm(id) {
  const form = document.getElementById("assignment-form");
  const editing = id !== undefined;
  const target = editing
    ? state.assignments.find((a) => a.assignment_id === id)
    : null;

  document.getElementById("form-error").hidden = true;
  document.getElementById("form-title").textContent =
    editing ? "Edit assessment" : "New assessment";
  document.getElementById("form-submit").textContent =
    editing ? "SAVE CHANGES" : "CREATE";

  form.assignment_id.value = target ? target.assignment_id : "";
  form.title.value = target ? target.title : "";
  form.description.value = target ? target.description || "" : "";
  form.course_id.value = target ? target.course_id : "";
  form.weighting.value = target ? target.weighting ?? "" : "";
  form.due_date.value = target ? (target.due_date || "").slice(0, 10) : "";
  form.status.value = target ? target.status : "not_started";

  document.getElementById("form-modal").hidden = false;
}

async function submitForm(form) {
  const errorBox = document.getElementById("form-error");
  errorBox.hidden = true;

  const id = form.assignment_id.value;
  const payload = {
    student_id: STUDENT_ID,
    course_id: Number(form.course_id.value),
    title: form.title.value.trim(),
    description: form.description.value.trim(),
    due_date: form.due_date.value,
    weighting: form.weighting.value ? Number(form.weighting.value) : null,
    status: form.status.value,
  };

  try {
    if (id) {
      await api(`/assignments/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/assignments", { method: "POST", body: JSON.stringify(payload) });
    }
    document.getElementById("form-modal").hidden = true;
    form.reset();
    await loadAssignments();
    toast(id ? "Assessment updated" : "Assessment created", "success");
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
}

async function prioritise() {
  const output = document.getElementById("agent-output");
  const button = document.getElementById("prioritise-btn");

  button.disabled = true;
  output.textContent = "Running agent workflow...";

  try {
    const data = await api("/ai/prioritise", {
  method: "POST",
  body: JSON.stringify({
    student_id: STUDENT_ID
  })
});

    const steps = Array.isArray(data.agent_steps)
      ? data.agent_steps
      : [];

    const workflowText = steps
      .map((step) => `${step.stage}\n${step.detail}`)
      .join("\n\n");

    const recommendation =
      data.recommendation ||
      data.message ||
      "No recommendation returned.";

    output.textContent =
      `${workflowText}\n\nFINAL RECOMMENDATION\n${recommendation}`;

  } catch (error) {
    output.textContent = `Could not prioritise: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}


document.addEventListener("DOMContentLoaded", () => {
  currentUser = readUser();

  if (!currentUser) {
    window.location.href = "/login.html";
    return;
  }

  STUDENT_ID = Number(currentUser.user_id || currentUser.id);

  if (!STUDENT_ID) {
    localStorage.removeItem("user");
    window.location.href = "/login.html";
    return;
  }

  document.getElementById("new-btn").addEventListener("click", () => openForm());
  document.getElementById("form-close").addEventListener("click", () => {
    document.getElementById("form-modal").hidden = true;
  });
  document.getElementById("form-cancel").addEventListener("click", () => {
    document.getElementById("form-modal").hidden = true;
  });
  document.getElementById("assignment-form").addEventListener("submit", (e) => {
    e.preventDefault();
    submitForm(e.target);
  });

  document.getElementById("prioritise-btn").addEventListener("click", prioritise);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.getElementById("form-modal").hidden = true;
  });

  loadAssignments();
});
