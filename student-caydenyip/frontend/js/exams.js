const examsResult = document.getElementById("exams-result");
const courseResult = document.getElementById("course-result");

let currentCourseId = null;

async function getResponseData(response) {
    const text = await response.text();

    try {
        return text ? JSON.parse(text) : {};
    } catch {
        return { message: text };
    }
}

function getUserExamsUrl() {
    return `${API_URL}/exams?student_id=${encodeURIComponent(userId)}`;
}

async function refreshUserExams() {
    examsResult.innerHTML = "<div class='exam-message'>Loading exams...</div>";

    try {
        const response = await fetch(getUserExamsUrl());
        const data = await getResponseData(response);

        if (!response.ok) {
            examsResult.innerHTML =
                `<div class="exam-message">${data.error || "Failed to load exams."}</div>`;
            return;
        }

        const exams = Array.isArray(data) ? data : [data];

        if (!exams.length) {
            examsResult.innerHTML =
                "<div class='exam-message'>No exams found.</div>";
            return;
        }

        examsResult.innerHTML = createExamTable(exams, true);

    } catch (error) {
        console.error(error);
        examsResult.innerHTML =
            "<div class='exam-message'>Request failed.</div>";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (!checkLoggedIn()) return;

    refreshUserExams();
});
