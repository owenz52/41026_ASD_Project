const askWithContextForm =
    document.getElementById("ask-with-context-form");

const contextResult =
    document.getElementById("context-result");

askWithContextForm.addEventListener("submit", async event => {
    event.preventDefault();

    const question =
        document.getElementById("context-question")
            .value
            .trim();

    if (!question) {
        contextResult.innerHTML =
            "<p>Please enter a question.</p>";
        return;
    }

    contextResult.innerHTML =
        "<p>Thinking...</p>";

    const formData = new URLSearchParams();

    formData.append("question", question);
    formData.append("student_id", userId);

    try {
        const response = await fetch(
            `${API_URL}/ask-with-context`,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/x-www-form-urlencoded"
                },
                body: formData.toString()
            }
        );

        const body = await response.text();

        if (!response.ok) {
            contextResult.innerHTML =
                `<p>Request failed.</p><pre>${body}</pre>`;
            return;
        }

        contextResult.innerHTML = body;

    } catch (error) {
        console.error(error);

        contextResult.innerHTML =
            `<p>Request failed.</p><pre>${error}</pre>`;
    }
});
