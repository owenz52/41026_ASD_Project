const resetExamsButton =
    document.getElementById("reset-exams-btn");

resetExamsButton.addEventListener("click", async () => {
    if (!confirm(
        "This will remove all your existing exams and replace them with fresh exams. Continue?"
    )) {
        return;
    }

    resetExamsButton.disabled = true;
    resetExamsButton.textContent = "Resetting...";

    try {
        const response = await fetch(
            `${API_URL}/exams/reset?student_id=${encodeURIComponent(
                userId
            )}`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            }
        );

        const data = await getResponseData(response);

        if (!response.ok) {
            showToast(
                data.error || "Failed to reset exams.",
                "error"
            );
            return;
        }

        showToast(
            data.message || "Exams reset successfully."
        );

        await refreshUserExams();

        if (currentCourseId) {
            await refreshCourseResults();
        }

    } catch (error) {
        console.error(error);
        showToast("Failed to reset exams.", "error");

    } finally {
        resetExamsButton.disabled = false;
        resetExamsButton.textContent = "Reset My Exams";
    }
});
