const addExamModal = document.getElementById("add-exam-modal");
const openAddExamButton = document.getElementById("open-add-exam-btn");
const closeAddExamButton = document.getElementById("close-add-exam-btn");
const addExamForm = document.getElementById("add-exam-form");
const addExamResult = document.getElementById("add-exam-result");

function openAddExamModal() {
    addExamResult.hidden = true;
    addExamResult.textContent = "";

    addExamModal.hidden = false;

    document.getElementById("add-course-id").focus();
}

function closeAddExamModal() {
    addExamModal.hidden = true;
}

openAddExamButton.addEventListener("click", openAddExamModal);
closeAddExamButton.addEventListener("click", closeAddExamModal);

addExamModal.addEventListener("click", event => {
    if (event.target === addExamModal) {
        closeAddExamModal();
    }
});

document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !addExamModal.hidden) {
        closeAddExamModal();
    }
});

addExamForm.addEventListener("submit", async event => {
    event.preventDefault();

    addExamResult.hidden = false;
    addExamResult.textContent = "Adding exam...";

    const data = {
        student_id: userId,
        course_id: document.getElementById("add-course-id").value.trim(),
        exam_name: document.getElementById("add-exam-name").value.trim(),
        exam_date: document.getElementById("add-exam-date").value,
        exam_time: document.getElementById("add-exam-time").value
    };

    try {
        const response = await fetch(`${API_URL}/exams`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });

        const result = await getResponseData(response);

        if (!response.ok) {
            addExamResult.textContent =
                result.error || "Failed to add exam.";
            return;
        }

        addExamForm.reset();
        closeAddExamModal();

        showToast(
            result.message || "Exam added successfully.",
            "success"
        );

        await refreshUserExams();

        if (currentCourseId) {
            await refreshCourseResults();
        }

    } catch (error) {
        console.error(error);
        addExamResult.textContent = "Failed to add exam.";
    }
});
