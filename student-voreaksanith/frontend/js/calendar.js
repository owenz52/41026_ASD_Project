const API_BASE = window.CALENDAR_API || "/calendar-api";

// The login page lives on the portal, not in this container. Redirecting to a
// bare "/login.html" here hits nginx's try_files, which serves index.html and
// runs this guard again — an endless reload for anyone not signed in.
const LOGIN_URL = window.PORTAL_LOGIN_URL || "http://localhost:8000/login.html";

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

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const state = {
  cursor: new Date(2026, 8, 1), // September 2026, matching the seed data
  events: [],

  selectedId: null,
};

/* ---------------------------------------------------------------- helpers */

const pad = (n) => String(n).padStart(2, "0");
const isoDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const timeOf = (s) => (s || "").slice(11, 16);

function escapeHtml(value) {
  // Event titles are user input and get injected as HTML below, so they must
  // be escaped to avoid an XSS hole.
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(message, kind = "info") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = message;
  el.className = `toast toast--${kind} toast--visible`;
  setTimeout(() => el.classList.remove("toast--visible"), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

/* ------------------------------------------------------------------ load */

async function loadEvents() {
  const year = state.cursor.getFullYear();
  const month = state.cursor.getMonth();
  const start = isoDate(new Date(year, month, 1));
  const end = isoDate(new Date(year, month + 1, 0));

  try {
    const data = await api(
      `/events?student_id=${STUDENT_ID}&start_date=${start}&end_date=${end}`
    );
    state.events = data.events || [];
  } catch (error) {
    state.events = [];
    toast(`Could not load events: ${error.message}`, "error");
  }
  render();
}

/* ---------------------------------------------------------------- render */

function render() {
  document.getElementById("month-label").textContent =
    `${MONTHS[state.cursor.getMonth()]} ${state.cursor.getFullYear()}`;

  const grid = document.getElementById("calendar-grid");
  grid.innerHTML = "";

  const year = state.cursor.getFullYear();
  const month = state.cursor.getMonth();
  const first = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Monday-first offset: JS getDay() is Sunday-first.
  const offset = (first.getDay() + 6) % 7;

  for (let i = 0; i < offset; i += 1) {
    const filler = document.createElement("div");
    filler.className = "day day--empty";
    grid.appendChild(filler);
  }

  const todayIso = isoDate(new Date());

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(year, month, day);
    const dateIso = isoDate(date);

    const cell = document.createElement("div");
    cell.className = "day";
    cell.dataset.date = dateIso;
    if (dateIso === todayIso) cell.classList.add("day--today");

    cell.innerHTML = `<div class="day__number">${day}</div>`;

    state.events
      .filter((e) => e.start_time.startsWith(dateIso))
      .sort((a, b) => a.start_time.localeCompare(b.start_time))
      .forEach((event) => cell.appendChild(renderEvent(event)));

    // Drop target wiring for drag-to-reschedule.
    cell.addEventListener("dragover", (e) => {
      e.preventDefault();
      cell.classList.add("day--drop");
    });
    cell.addEventListener("dragleave", () => cell.classList.remove("day--drop"));
    cell.addEventListener("drop", (e) => {
      e.preventDefault();
      cell.classList.remove("day--drop");
      const eventId = e.dataTransfer.getData("text/plain");
      if (eventId) moveEvent(Number(eventId), dateIso);
    });

    grid.appendChild(cell);
  }
}

function renderEvent(event) {
  const el = document.createElement("div");
  el.className = `event event--${event.event_type}`;
  el.draggable = true;
  el.dataset.eventId = event.event_id;
  el.style.borderLeftColor = event.color;

  const label = event.subject ? `${escapeHtml(event.subject)} · ` : "";
  el.innerHTML = `
    <span class="event__title">${escapeHtml(event.title)}</span>
    <span class="event__meta">${label}${timeOf(event.start_time)}</span>
    <button class="event__delete" title="Delete event" aria-label="Delete event">×</button>
  `;

  el.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", String(event.event_id));
    e.dataTransfer.effectAllowed = "move";
    el.classList.add("event--dragging");
  });
  el.addEventListener("dragend", () => el.classList.remove("event--dragging"));

  el.querySelector(".event__delete").addEventListener("click", (e) => {
    e.stopPropagation();
    deleteEvent(event.event_id, event.title);
  });

  return el;
}

/* --------------------------------------------------------------- actions */

async function moveEvent(eventId, newDate) {
  const event = state.events.find((e) => e.event_id === eventId);
  if (!event) return;
  if (event.start_time.startsWith(newDate)) return; // dropped on its own day

  const previous = event.start_time;

  // Optimistic update so the drag feels immediate, reverted if the API rejects.
  event.start_time = `${newDate} ${timeOf(previous)}`;
  render();

  try {
    const updated = await api(`/events/${eventId}/move`, {
      method: "PATCH",
      body: JSON.stringify({ new_date: newDate }),
    });

    Object.assign(event, updated);
    render();

    if (updated.conflicts && updated.conflicts.length) {
      const names = updated.conflicts.map((c) => c.title).join(", ");
      toast(`Moved — note it now overlaps: ${names}`, "warn");
    } else {
      toast(`"${event.title}" moved to ${newDate}`, "success");
    }
  } catch (error) {
    event.start_time = previous;
    render();
    toast(`Move failed: ${error.message}`, "error");
  }
}

async function deleteEvent(eventId, title) {
  if (!window.confirm(`Delete "${title}"?`)) return;

  try {
    await api(`/events/${eventId}`, { method: "DELETE" });
    state.events = state.events.filter((e) => e.event_id !== eventId);
    render();
    toast(`"${title}" deleted`, "success");
  } catch (error) {
    toast(`Delete failed: ${error.message}`, "error");
  }
}

async function addEvent(form) {
  const payload = {
    student_id: STUDENT_ID,
    title: form.title.value.trim(),
    event_type: form.event_type.value,
    start_time: form.start_time.value.replace("T", " "),
    end_time: form.end_time.value.replace("T", " "),
    location: form.location.value.trim(),
  };

  if (form.subject.value.trim()) {
    payload.subject = form.subject.value.trim();
  }

  try {
    const created = await api("/events", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    closeModal();
    form.reset();

    // Jump to the created event's month so it is actually visible.
    const [y, m] = created.start_time.split("-");
    state.cursor = new Date(Number(y), Number(m) - 1, 1);
    await loadEvents();

    toast(created.warning || `"${created.title}" added`, created.warning ? "warn" : "success");
  } catch (error) {
    const box = document.getElementById("form-error");
    box.textContent = error.message;
    box.hidden = false;
  }
}

/* ---------------------------------------------------------- study agent */

let pendingSuggestions = [];

function formatSlot(isoLike) {
  const [datePart, timePart] = isoLike.split(" ");
  const d = new Date(`${datePart}T${timePart}`);
  return d.toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short",
  }) + `, ${timePart}`;
}

function renderSuggestions(suggestions, trace) {
  const list = document.getElementById("agent-suggestions");
  list.innerHTML = suggestions
    .map(
      (s) => `
      <div class="suggestion">
        <span class="suggestion__when">${escapeHtml(formatSlot(s.start_time))}</span>
        <span class="suggestion__what">${escapeHtml(s.title)}</span>
        <span class="suggestion__why">${escapeHtml(s.reason)}</span>
      </div>`
    )
    .join("");

  document.getElementById("agent-apply").hidden = suggestions.length === 0;
  document.getElementById("agent-dismiss").hidden = suggestions.length === 0;

  const traceWrap = document.getElementById("agent-trace-wrap");
  if (trace) {
    document.getElementById("agent-trace").textContent = JSON.stringify(trace, null, 2);
    traceWrap.hidden = false;
  }
}

function clearSuggestions() {
  pendingSuggestions = [];
  document.getElementById("agent-suggestions").innerHTML = "";
  document.getElementById("agent-apply").hidden = true;
  document.getElementById("agent-dismiss").hidden = true;
  document.getElementById("agent-trace-wrap").hidden = true;
}

async function requestSuggestions() {
  const panel = document.querySelector(".agent");
  const button = document.getElementById("agent-suggest");
  const text = document.getElementById("agent-text");

  panel.classList.add("is-busy");
  button.disabled = true;
  text.textContent = "Looking at your deadlines and free time...";

  try {
    const data = await api("/ai/suggest-schedule", {
      method: "POST",
      body: JSON.stringify({ student_id: STUDENT_ID }),
    });

    pendingSuggestions = data.suggestions || [];

    if (!pendingSuggestions.length) {
      const why = data.trace?.adapt?.reasoning || "Nothing to schedule right now.";
      text.textContent = why;
      clearSuggestions();
      document.getElementById("agent-trace-wrap").hidden = false;
      document.getElementById("agent-trace").textContent =
        JSON.stringify(data.trace, null, 2);
      return;
    }

    const usedFallback = (data.trace?.adapt?.action || "").startsWith("fallback");
    text.textContent = usedFallback
      ? `${pendingSuggestions.length} session(s) suggested. The AI model was unavailable, so these were picked from your free time directly.`
      : `${pendingSuggestions.length} session(s) suggested. Review before adding.`;

    const apply = document.getElementById("agent-apply");
    apply.dataset.mode = "sessions";
    apply.textContent = "ADD THESE TO MY CALENDAR";
    renderSuggestions(pendingSuggestions, data.trace);
  } catch (error) {
    text.textContent = `Could not get suggestions: ${error.message}`;
    toast(`Agent failed: ${error.message}`, "error");
  } finally {
    panel.classList.remove("is-busy");
    button.disabled = false;
  }
}

async function applySuggestions() {
  if (!pendingSuggestions.length) return;

  const button = document.getElementById("agent-apply");
  button.disabled = true;

  try {
    const result = await api("/ai/apply-suggestions", {
      method: "POST",
      body: JSON.stringify({
        student_id: STUDENT_ID,
        suggestions: pendingSuggestions,
      }),
    });

    // Jump to the month the sessions landed in, so they are visible.
    const first = pendingSuggestions[0].start_time;
    const [y, m] = first.split("-");
    state.cursor = new Date(Number(y), Number(m) - 1, 1);

    clearSuggestions();
    document.getElementById("agent-text").textContent =
      `Added ${result.created_count} session(s) to your calendar.`;
    await loadEvents();

    if (result.failed_count) {
      toast(`${result.failed_count} session(s) could not be added`, "warn");
    } else {
      toast(`${result.created_count} revision session(s) added`, "success");
    }
  } catch (error) {
    toast(`Could not add sessions: ${error.message}`, "error");
  } finally {
    button.disabled = false;
  }
}

/* ------------------------------------------------- deadlines + briefing */

let pendingDeadlines = [];

async function findDeadlines() {
  const button = document.getElementById("agent-import");
  const text = document.getElementById("agent-text");

  button.disabled = true;
  text.textContent = "Checking your assessments and exams...";

  try {
    const data = await api("/ai/find-deadlines", {
      method: "POST",
      body: JSON.stringify({ student_id: STUDENT_ID }),
    });

    pendingDeadlines = data.missing || [];

    // Say plainly when a source could not be reached, rather than implying
    // the student has nothing due.
    const down = Object.entries(data.sources || {})
      .filter(([, s]) => !s.available)
      .map(([name]) => name);

    if (!pendingDeadlines.length) {
      text.textContent = down.length
        ? `No new deadlines found, but the ${down.join(" and ")} service could not be reached.`
        : `Nothing new — all ${data.already_in_calendar} deadline(s) are already on your calendar.`;
      document.getElementById("agent-suggestions").innerHTML = "";
      document.getElementById("agent-apply").hidden = true;
      return;
    }

    text.textContent =
      `${pendingDeadlines.length} deadline(s) not on your calendar yet.` +
      (down.length ? ` (${down.join(" and ")} unavailable)` : "");

    document.getElementById("agent-suggestions").innerHTML = pendingDeadlines
      .map((d) => `
        <div class="suggestion">
          <span class="suggestion__when">${escapeHtml(d.start_time.slice(0, 16))}</span>
          <span class="suggestion__what">${escapeHtml(d.title)}</span>
          <span class="suggestion__why">${
            d.weighting ? `Worth ${Math.round(d.weighting)}% · ` : ""
          }${escapeHtml(d.source)} · due in ${d.days_until_due} day(s)</span>
        </div>`)
      .join("");

    const apply = document.getElementById("agent-apply");
    apply.hidden = false;
    apply.textContent = "ADD THESE TO MY CALENDAR";
    apply.dataset.mode = "deadlines";
    document.getElementById("agent-dismiss").hidden = false;
  } catch (error) {
    text.textContent = `Could not check deadlines: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

async function importDeadlines() {
  if (!pendingDeadlines.length) return;
  const button = document.getElementById("agent-apply");
  button.disabled = true;

  try {
    const result = await api("/ai/import-deadlines", {
      method: "POST",
      body: JSON.stringify({ student_id: STUDENT_ID, items: pendingDeadlines }),
    });

    const first = pendingDeadlines[0].start_time;
    const [y, m] = first.split("-");
    state.cursor = new Date(Number(y), Number(m) - 1, 1);

    pendingDeadlines = [];
    clearSuggestions();
    document.getElementById("agent-text").textContent =
      `Added ${result.created_count} deadline(s) to your calendar.`;
    await loadEvents();
    toast(`${result.created_count} deadline(s) imported`, "success");
  } catch (error) {
    toast(`Import failed: ${error.message}`, "error");
  } finally {
    button.disabled = false;
  }
}

async function getBriefing() {
  const button = document.getElementById("brief-btn");
  const text = document.getElementById("brief-text");
  const facts = document.getElementById("brief-facts");

  button.disabled = true;
  text.textContent = "Pulling together today...";
  facts.innerHTML = "";
  document.getElementById("brief-note")?.remove();

  try {
    const data = await api("/ai/briefing", {
      method: "POST",
      body: JSON.stringify({ student_id: STUDENT_ID }),
    });

    text.textContent = data.summary || "Nothing to report.";

    const f = data.facts || {};

    // Rendered with the same .suggestion cards the study agent uses, so both
    // panels read as one feature rather than two different designs.
    const card = (when, what, why) => `
      <div class="suggestion">
        <span class="suggestion__when">${escapeHtml(when)}</span>
        <span class="suggestion__what">${escapeHtml(what)}</span>
        ${why ? `<span class="suggestion__why">${escapeHtml(why)}</span>` : ""}
      </div>`;

    const cards = [];

    (f.events_today || []).forEach((e) => {
      cards.push(card(e.time, e.title,
        [e.type, e.location].filter(Boolean).join(" · ")));
    });

    if (!(f.events_today || []).length) {
      cards.push(card("Today", "Nothing scheduled", "No classes or events in your calendar"));
    }

    (f.due_this_week || []).slice(0, 3).forEach((d) => {
      const days = d.days_until_due;
      cards.push(card(
        `Due ${String(d.due).slice(0, 10)}`,
        d.title,
        [
          days === 0 ? "due today" : `in ${days} day(s)`,
          d.weighting ? `worth ${Math.round(d.weighting)}%` : "",
        ].filter(Boolean).join(" · ")
      ));
    });

    if (f.next_exam) {
      cards.push(card(
        `Exam ${String(f.next_exam.when).slice(0, 10)}`,
        f.next_exam.title,
        `in ${f.next_exam.days_until} day(s)`
      ));
    }

    if (f.top_priorities && f.top_priorities.length) {
      const top = f.top_priorities[0];
      cards.push(`
        <div class="suggestion suggestion--top">
          <span class="suggestion__when">Start with</span>
          <span class="suggestion__what">${escapeHtml(top.title)}</span>
          <span class="suggestion__why">due ${escapeHtml(String(top.due).slice(0, 10))}${
            top.weighting ? ` · worth ${Math.round(top.weighting)}%` : ""
          }</span>
        </div>`);
    }

    facts.innerHTML = cards.join("");

    if (!data.trace?.llm_invoked) {
      facts.insertAdjacentHTML("afterend",
        `<p class="agent__note" id="brief-note">Summary written without the AI model, which was unavailable. The details above are still accurate.</p>`);
    }

  } catch (error) {
    text.textContent = `Could not build a briefing: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

/* ---------------------------------------------------------------- modal */

function openModal() {
  document.getElementById("form-error").hidden = true;
  document.getElementById("event-modal").hidden = false;
  document.getElementById("event-title").focus();
}

function closeModal() {
  document.getElementById("event-modal").hidden = true;
}

/* ------------------------------------------------------------------ init */

document.addEventListener("DOMContentLoaded", () => {
  currentUser = readUser();

  if (!currentUser) {
    window.location.href = LOGIN_URL;
    return;
  }

  STUDENT_ID = Number(currentUser.user_id || currentUser.id);

  if (!STUDENT_ID) {
    localStorage.removeItem("user");
    window.location.href = LOGIN_URL;
    return;
  }

  document.getElementById("prev-month").addEventListener("click", () => {
    state.cursor.setMonth(state.cursor.getMonth() - 1);
    loadEvents();
  });
  document.getElementById("next-month").addEventListener("click", () => {
    state.cursor.setMonth(state.cursor.getMonth() + 1);
    loadEvents();
  });

  document.getElementById("add-event-btn").addEventListener("click", openModal);

  document.getElementById("agent-suggest").addEventListener("click", requestSuggestions);
  document.getElementById("agent-apply").addEventListener("click", (e) => {
    if (e.currentTarget.dataset.mode === "deadlines") importDeadlines();
    else applySuggestions();
  });
  document.getElementById("agent-import").addEventListener("click", findDeadlines);
  document.getElementById("brief-btn").addEventListener("click", getBriefing);
  document.getElementById("agent-dismiss").addEventListener("click", () => {
    clearSuggestions();
    document.getElementById("agent-text").textContent =
      "Suggestions dismissed. Nothing was added to your calendar.";
  });
  document.getElementById("cancel-event").addEventListener("click", closeModal);

  document.getElementById("event-form").addEventListener("submit", (e) => {
    e.preventDefault();
    addEvent(e.target);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  loadEvents();
});
