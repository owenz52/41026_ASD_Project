const toast = document.getElementById("toast");

let toastTimer;

function showToast(message, type = "success") {
    toast.textContent = message;

    toast.className =
        `toast toast--visible toast--${type}`;

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        toast.className = "toast";
    }, 2500);
}

async function toggleStatus(examId, currentStatus) {
    const newStatus =
        currentStatus === "Completed"
            ? "Uncompleted"
            : "Completed";

    try {
        const response = await fetch(
            `${API_URL}/exams/${examId}`,
            {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    status: newStatus
                })
            }
        );

        const data = await getResponseData(response);

        if (!response.ok) {
            showToast(
                data.error || "Failed to update exam.",
                "error"
            );
            return;
        }

        await refreshUserExams();

        if (currentCourseId) {
            await refreshCourseResults();
        }

        showToast(
            `Exam marked ${newStatus.toLowerCase()}.`
        );

    } catch (error) {
        console.error(error);
        showToast("Request failed.", "error");
    }
}

async function deleteExam(examId) {
    if (!confirm("Are you sure you want to delete this exam?")) {
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/exams/${examId}`,
            {
                method: "DELETE"
            }
        );

        const data = await getResponseData(response);

        if (!response.ok) {
            showToast(
                data.error || "Failed to delete exam.",
                "error"
            );
            return;
        }

        showToast("Exam deleted successfully.");

        await refreshUserExams();

        if (currentCourseId) {
            await refreshCourseResults();
        }

    } catch (error) {
        console.error(error);
        showToast("Request failed.", "error");
    }
}
