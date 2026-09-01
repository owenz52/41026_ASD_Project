const SERVICES = [
    { key: "enrolment", label: "Enrolment", url: "http://localhost:8080" },
    { key: "assessments", label: "Assessments", url: "http://localhost:8081" },
    { key: "calendar", label: "Calendar", url: "http://localhost:8082" },
    { key: "notes", label: "Notes", url: "http://localhost:8083" },
    { key: "exams", label: "Exams", url: "http://localhost:8084" },
];


function readUser() {
    try {
        const raw = localStorage.getItem("user");
        return raw ? JSON.parse(raw) : null;
    } catch (error) {
        // A corrupt entry should not break the page.
        return null;
    }
}

function firstName(user) {
    const name = (user && (user.name || user.email)) || "";
    return String(name).trim().split(/[\s@]+/)[0] || "";
}

function greetingFor(date) {
    const hour = date.getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
}

function renderUser() {
    const user = readUser();
    const nameEl = document.getElementById("user-name");
    const emailEl = document.getElementById("user-email");
    const button = document.getElementById("auth-action");
    const greeting = document.getElementById("greeting");

    const now = new Date();
    document.getElementById("today-line").textContent = now.toLocaleDateString(
        undefined,
        { weekday: "long", day: "numeric", month: "long", year: "numeric" }
    );

    if (user) {
        nameEl.textContent = user.name || "Student";
        emailEl.textContent = user.email || "";
        greeting.textContent = `${greetingFor(now)}, ${firstName(user)}`;

        button.textContent = "SIGN OUT";
        button.classList.remove("btn--primary");
        button.addEventListener("click", () => {
            localStorage.removeItem("user");
            window.location.reload();
        });
    } else {
        nameEl.textContent = "Not signed in";
        emailEl.textContent = "";
        greeting.textContent = "Student Portal";

        button.textContent = "SIGN IN";
        button.classList.add("btn--primary");
        button.addEventListener("click", () => {
            window.location.href = "login.html";
        });
    }
}

async function isUp(url, timeoutMs = 3000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        await fetch(url, { mode: "no-cors", signal: controller.signal });
        return true;
    } catch (error) {
        return false;
    } finally {
        clearTimeout(timer);
    }
}

function renderStatusRow(service, state) {
    const dot = state === "up" ? "dot dot--up" : state === "down" ? "dot dot--down" : "dot";
    const text = state === "up" ? "Running" : state === "down" ? "Not running" : "Checking";

    return `
      <li>
        <span class="status-name"><span class="${dot}"></span>${service.label}</span>
        <span class="status-value">${text}</span>
      </li>`;
}

async function checkServices() {
    const list = document.getElementById("status-list");
    list.innerHTML = SERVICES.map((s) => renderStatusRow(s, "checking")).join("");

    const results = await Promise.all(SERVICES.map((s) => isUp(s.url)));

    list.innerHTML = SERVICES
        .map((s, i) => renderStatusRow(s, results[i] ? "up" : "down"))
        .join("");

    SERVICES.forEach((service, i) => {
        const badge = document.querySelector(`.feature__status[data-service="${service.key}"]`);
        if (!badge) return;
        badge.textContent = results[i] ? "Running" : "Offline";
        badge.classList.add(results[i] ? "feature__status--up" : "feature__status--down");
    });

    const up = results.filter(Boolean).length;
    document.getElementById("status-summary").textContent =
        `${up} of ${SERVICES.length} running`;
}


document.addEventListener("DOMContentLoaded", () => {
    renderUser();
    checkServices();
});
