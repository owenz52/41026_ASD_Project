const ragEnabled = document.getElementById("rag-enabled");
const ragCaller = document.getElementById("rag-caller");
const ragQuery = document.getElementById("rag-query");
const ragK = document.getElementById("rag-k");

const refreshBtn = document.getElementById("rag-refresh-btn");
const retrieveBtn = document.getElementById("rag-retrieve-btn");
const answerBtn = document.getElementById("rag-answer-btn");

const ragStatus = document.getElementById("rag-status");
const ragResponse = document.getElementById("rag-response");


function setStatus(message) {
    ragStatus.textContent = message;
}


function showResponse(data) {
    if (typeof data === "string") {
        ragResponse.textContent = data;
        return;
    }

    ragResponse.textContent = JSON.stringify(data, null, 2);
}


async function callRagEndpoint(endpoint, formData) {
    try {
        setStatus(`Calling ${endpoint}...`);
        ragResponse.textContent = "Loading...";

        const response = await fetch(endpoint, {
            method: "POST",
            body: formData
        });

        let data;

        try {
            data = await response.json();
        } catch {
            data = await response.text();
        }

        showResponse(data);

        if (!response.ok) {
            setStatus(`Error: HTTP ${response.status}`);
            return;
        }

        setStatus(`Success: HTTP ${response.status}`);

    } catch (error) {
        setStatus("Request failed");
        showResponse({
            status: "error",
            error: error.message
        });
    }
}


/*
 * POST /rag/refresh
 */
refreshBtn.addEventListener("click", async () => {
    if (!ragEnabled.checked) {
        setStatus("RAG is disabled");
        return;
    }

    const formData = new FormData();

    formData.append(
        "caller",
        ragCaller.value.trim() || "student"
    );

    await callRagEndpoint("/exams-api/rag/refresh", formData);
});


/*
 * POST /rag/retrieve
 */
retrieveBtn.addEventListener("click", async () => {
    if (!ragEnabled.checked) {
        setStatus("RAG is disabled");
        return;
    }

    const query = ragQuery.value.trim();
    const k = ragK.value;

    if (!query) {
        setStatus("Please enter a query");
        return;
    }

    const formData = new FormData();

    formData.append("query", query);
    formData.append("k", k);

    await callRagEndpoint("/exams-api/rag/retrieve", formData);
});


/*
 * POST /rag/answer
 */
answerBtn.addEventListener("click", async () => {
    if (!ragEnabled.checked) {
        setStatus("RAG is disabled");
        return;
    }

    const query = ragQuery.value.trim();
    const k = ragK.value;

    if (!query) {
        setStatus("Please enter a query");
        return;
    }

    const formData = new FormData();

    formData.append("query", query);
    formData.append("k", k);

    await callRagEndpoint("/exams-api/rag/answer", formData);
});
