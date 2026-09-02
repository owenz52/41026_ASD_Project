const API_URL = window.NOTEBOOK_API || "/notes-api";

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

const state = {
  selectedNotebookId: null,
  selectedNotebookTitle: "",
  notebooks: [],
  notes: [],
};

/* ---------------------------------------------------------------- helpers */

function escapeHtml(value) {
  // Titles and note content are user input and get injected as HTML below,
  // so they must be escaped to avoid an XSS hole.
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
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

const $ = (id) => document.getElementById(id);

function openModal(id) { $(id).hidden = false; }
function closeModal(id) { $(id).hidden = true; }

function showError(id, message) {
  const el = $(id);
  el.textContent = message;
  el.hidden = false;
}

function clearError(id) { $(id).hidden = true; }

/* ----------------------------------------------------------- confirmation */

let confirmAction = null;

function askConfirm(title, text, onConfirm) {
  $("confirm-title").textContent = title;
  $("confirm-text").textContent = text;
  confirmAction = onConfirm;
  openModal("confirm-modal");
}

/* ------------------------------------------------------------- notebooks */

async function loadNotebooks() {
  const list = $("notebooks-list");

  try {
    const notebooks = await api("/notebooks");
    state.notebooks = notebooks.filter(
      (notebook) => Number(notebook.student_id) === STUDENT_ID
    );
  } catch (error) {
    console.error("Failed to load notebooks:", error);
    list.className = "empty";
    list.textContent = "Failed to load notebooks. Please try again later.";
    return;
  }

  if (state.notebooks.length === 0) {
    list.className = "empty";
    list.textContent = "No notebooks yet. Create one to get started.";
    return;
  }

  list.className = "cards";
  list.innerHTML = state.notebooks.map((notebook) => `
    <article class="notebook${notebook.notebook_id === state.selectedNotebookId ? " notebook--active" : ""}">
      <div class="notebook__course">COURSE ${escapeHtml(notebook.course_id)}</div>
      <h3 class="notebook__title">${escapeHtml(notebook.notebook_title)}</h3>
      <div class="notebook__date">Created ${escapeHtml(notebook.created_date)}</div>
      <div class="notebook__actions">
        <button class="btn btn--small btn--primary" data-action="open-notebook" data-id="${notebook.notebook_id}">OPEN</button>
        <button class="btn btn--small" data-action="edit-notebook" data-id="${notebook.notebook_id}">EDIT</button>
        <button class="btn btn--small btn--danger" data-action="delete-notebook" data-id="${notebook.notebook_id}">DELETE</button>
      </div>
    </article>
  `).join("");
}

function openNotebookForm(notebook) {
  const form = $("notebook-form");
  form.reset();
  clearError("notebook-error");

  form.dataset.mode = notebook ? "edit" : "create";
  form.dataset.id = notebook ? notebook.notebook_id : "";
  $("notebook-modal-title").textContent = notebook ? "Edit notebook" : "Add notebook";

  const studentField = form.elements.student_id.closest(".field");
  studentField.hidden = true;
  form.elements.student_id.required = false;

  if (notebook) {
    form.elements.notebook_title.value = notebook.notebook_title;
    form.elements.course_id.value = notebook.course_id;
  }

  openModal("notebook-modal");
}

async function submitNotebook(event) {
  event.preventDefault();
  const form = event.target;
  clearError("notebook-error");

  const title = form.elements.notebook_title.value.trim();
  const courseId = Number(form.elements.course_id.value);

  if (!title) {
    showError("notebook-error", "Title is required.");
    return;
  }

  try {
    if (form.dataset.mode === "edit") {
      await api(`/notebooks/${form.dataset.id}`, {
        method: "PUT",
        body: JSON.stringify({ notebook_title: title, course_id: courseId }),
      });
      toast("Notebook updated.", "success");

      if (Number(form.dataset.id) === state.selectedNotebookId) {
        state.selectedNotebookTitle = title;
        renderSelectedNotebook();
        loadNotes();
      }
    } else {
      await api("/notebooks", {
        method: "POST",
        body: JSON.stringify({
          student_id: STUDENT_ID,
          course_id: courseId,
          notebook_title: title,
        }),
      });
      toast("Notebook created.", "success");
    }

    closeModal("notebook-modal");
    loadNotebooks();
  } catch (error) {
    showError("notebook-error", error.message);
  }
}

async function editNotebook(notebookId) {
  try {
    const notebook = await api(`/notebooks/${notebookId}`);
    openNotebookForm(notebook);
  } catch (error) {
    toast(error.message, "error");
  }
}

function deleteNotebook(notebookId) {
  const notebook = state.notebooks.find((n) => n.notebook_id === notebookId);

  askConfirm(
    "Delete notebook",
    `Deleting "${notebook ? notebook.notebook_title : notebookId}" will also delete all of its notes. This cannot be undone.`,
    async () => {
      try {
        await api(`/notebooks/${notebookId}`, { method: "DELETE" });
        toast("Notebook deleted.", "success");

        if (notebookId === state.selectedNotebookId) {
          state.selectedNotebookId = null;
          state.selectedNotebookTitle = "";
          renderSelectedNotebook();
        }
        loadNotebooks();
        loadNotes();
      } catch (error) {
        toast(error.message, "error");
      }
    }
  );
}

function openNotebook(notebookId) {
  const notebook = state.notebooks.find((n) => n.notebook_id === notebookId);
  state.selectedNotebookId = notebookId;
  state.selectedNotebookTitle = notebook ? notebook.notebook_title : "";
  renderSelectedNotebook();
  loadNotebooks();
  loadNotes();
}

function renderSelectedNotebook() {
  $("selected-notebook").textContent = state.selectedNotebookId
    ? `OPEN: ${state.selectedNotebookTitle.toUpperCase()}`
    : "NO NOTEBOOK OPEN";
}

/* ----------------------------------------------------------------- notes */

async function loadNotes() {
  const list = $("notes-list");

  if (state.selectedNotebookId === null) {
    list.className = "empty";
    list.textContent = "Open a notebook to see its notes.";
    return;
  }

  try {
    state.notes = await api(`/notebooks/${state.selectedNotebookId}/notes`);
  } catch (error) {
    console.error("Failed to load notes:", error);
    list.className = "empty";
    list.textContent = "Failed to load notes. Please try again later.";
    return;
  }

  if (state.notes.length === 0) {
    list.className = "empty";
    list.textContent = "This notebook has no notes yet.";
    return;
  }

  list.className = "table-wrap";
  list.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th class="table__id">ID</th>
          <th>Title</th>
          <th>Updated</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${state.notes.map((note) => `
          <tr>
            <td class="table__id">${escapeHtml(note.note_id)}</td>
            <td class="table__title">${escapeHtml(note.note_title)}</td>
            <td class="table__meta">${escapeHtml(note.updated_date)}</td>
            <td>
              <div class="table__actions">
                <button class="btn btn--small" data-action="summarise-note" data-id="${note.note_id}">SUMMARISE</button>
                <button class="btn btn--small" data-action="recommend-note" data-id="${note.note_id}">RECOMMEND</button>
                <button class="btn btn--small" data-action="edit-note" data-id="${note.note_id}">EDIT</button>
                <button class="btn btn--small btn--danger" data-action="delete-note" data-id="${note.note_id}">DELETE</button>
              </div>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function openNoteForm(note) {
  const form = $("note-form");
  form.reset();
  clearError("note-error");

  form.dataset.mode = note ? "edit" : "create";
  form.dataset.id = note ? note.note_id : "";
  $("note-modal-title").textContent = note ? "Edit note" : "Add note";

  if (note) {
    form.elements.note_title.value = note.note_title;
    form.elements.note_content.value = note.note_content;
  }

  openModal("note-modal");
}

function newNote() {
  if (state.selectedNotebookId === null) {
    toast("Open a notebook first.", "warn");
    return;
  }
  openNoteForm(null);
}

async function submitNote(event) {
  event.preventDefault();
  const form = event.target;
  clearError("note-error");

  const title = form.elements.note_title.value.trim();
  const content = form.elements.note_content.value.trim();

  if (!title || !content) {
    showError("note-error", "Title and content are both required.");
    return;
  }

  try {
    if (form.dataset.mode === "edit") {
      await api(`/notes/${form.dataset.id}`, {
        method: "PUT",
        body: JSON.stringify({ note_title: title, note_content: content }),
      });
      toast("Note updated.", "success");
    } else {
      await api("/notes", {
        method: "POST",
        body: JSON.stringify({
          notebook_id: state.selectedNotebookId,
          note_title: title,
          note_content: content,
        }),
      });
      toast("Note created.", "success");
    }

    closeModal("note-modal");
    loadNotes();
  } catch (error) {
    showError("note-error", error.message);
  }
}

async function editNote(noteId) {
  try {
    const note = await api(`/notes/${noteId}`);
    openNoteForm(note);
  } catch (error) {
    toast(error.message, "error");
  }
}

function deleteNote(noteId) {
  const note = state.notes.find((n) => n.note_id === noteId);

  askConfirm(
    "Delete note",
    `Delete "${note ? note.note_title : noteId}"? This cannot be undone.`,
    async () => {
      try {
        await api(`/notes/${noteId}`, { method: "DELETE" });
        toast("Note deleted.", "success");
        loadNotes();
      } catch (error) {
        toast(error.message, "error");
      }
    }
  );
}

/* ------------------------------------------------------------ ai actions */

async function runAi(path, noteId, busyText, heading, field) {
  const note = state.notes.find((n) => n.note_id === noteId);
  const title = note ? note.note_title : `note ${noteId}`;
  const agent = $("agent");
  const box = $("ai-response");

  agent.classList.add("is-busy");
  box.textContent = `${busyText} "${title}"...`;

  try {
    const data = await api(path, {
      method: "POST",
      body: JSON.stringify({ note_id: noteId }),
    });
    box.textContent = `${heading} "${title}":\n\n${data[field]}`;
  } catch (error) {
    console.error(`${path} failed:`, error);
    box.textContent = error.message;
    toast(error.message, "error");
  } finally {
    agent.classList.remove("is-busy");
  }
}

const summariseNote = (noteId) =>
  runAi("/ai/summarise", noteId, "Summarising", "Summary of", "summary");

const recommendNotes = (noteId) =>
  runAi("/ai/recommend", noteId, "Finding recommendations for", "Recommendations based on", "recommendations");

/* ---------------------------------------------------------------- search */

async function searchNotes() {
  const keyword = $("search-input").value.trim();
  const box = $("search-results");

  if (!keyword) {
    toast("Enter a keyword to search.", "warn");
    return;
  }

  try {
    const results = await api(`/notes/search?q=${encodeURIComponent(keyword)}`);

    if (results.length === 0) {
      box.innerHTML = `<div class="result"><div class="result__preview">No notes matched "${escapeHtml(keyword)}".</div></div>`;
      return;
    }

    box.innerHTML = results.map((note) => `
      <div class="result">
        <div class="result__title">${escapeHtml(note.note_title)}</div>
        <div class="result__preview">${escapeHtml(note.note_content.slice(0, 180))}${note.note_content.length > 180 ? "…" : ""}</div>
        <div class="result__meta">Notebook ${escapeHtml(note.notebook_id)}</div>
      </div>
    `).join("");
  } catch (error) {
    console.error("Failed to search notes:", error);
    box.innerHTML = `<div class="result"><div class="result__preview">${escapeHtml(error.message)}</div></div>`;
  }
}

/* ------------------------------------------------------------------ wire */

const ACTIONS = {
  "open-notebook": openNotebook,
  "edit-notebook": editNotebook,
  "delete-notebook": deleteNotebook,
  "edit-note": editNote,
  "delete-note": deleteNote,
  "summarise-note": summariseNote,
  "recommend-note": recommendNotes,
};

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-action]");
  if (trigger) {
    const handler = ACTIONS[trigger.dataset.action];
    if (handler) handler(Number(trigger.dataset.id));
    return;
  }

  const closer = event.target.closest("[data-close]");
  if (closer) closeModal(closer.dataset.close);

  // Clicking the dimmed backdrop closes the dialog.
  if (event.target.classList.contains("modal")) event.target.hidden = true;
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll(".modal").forEach((m) => { m.hidden = true; });
  }
});

$("new-notebook-btn").addEventListener("click", () => openNotebookForm(null));
$("new-note-btn").addEventListener("click", newNote);
$("notebook-form").addEventListener("submit", submitNotebook);
$("note-form").addEventListener("submit", submitNote);
$("search-btn").addEventListener("click", searchNotes);
$("search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchNotes();
});

$("confirm-ok").addEventListener("click", () => {
  closeModal("confirm-modal");
  if (confirmAction) confirmAction();
  confirmAction = null;
});

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

  renderSelectedNotebook();
  loadNotebooks();
  loadNotes();
});