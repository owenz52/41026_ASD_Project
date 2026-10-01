const examsByCourseForm =
    document.getElementById("exams-by-course-form");

async function refreshCourseResults() {
    if (!currentCourseId) return;

    courseResult.innerHTML =
        "<div class='exam-message'>Loading...</div>";

    try {
        const response = await fetch(
            `${API_URL}/exams/by-course?course_id=${encodeURIComponent(
                currentCourseId
            )}`
        );

        const data = await getResponseData(response);

        if (!response.ok) {
            courseResult.innerHTML =
                `<div class="exam-message">${
                    data.error || "No exams found."
                }</div>`;
            return;
        }

        const allExams = Array.isArray(data) ? data : [data];

        const exams = allExams.filter(
            exam => String(exam.student_id) === String(userId)
        );

        if (!exams.length) {
            courseResult.innerHTML =
                "<div class='exam-message'>No exams found for this course.</div>";
            return;
        }

        courseResult.innerHTML =
            createExamTable(exams, false);

    } catch (error) {
        console.error(error);

        courseResult.innerHTML =
            "<div class='exam-message'>Request failed.</div>";
    }
}

examsByCourseForm.addEventListener("submit", async event => {
    event.preventDefault();

    const courseId =
        document.getElementById("course_id").value.trim();

    if (!courseId) return;

    currentCourseId = courseId;

    await refreshCourseResults();
});
