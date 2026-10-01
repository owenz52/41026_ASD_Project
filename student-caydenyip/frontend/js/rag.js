// ==================================================
// RAG
// ==================================================

const ragQuery =
    document.getElementById("rag-query");

const ragK =
    document.getElementById("rag-k");

const retrieveBtn =
    document.getElementById("rag-retrieve-btn");

const answerBtn =
    document.getElementById("rag-answer-btn");

const ragStatus =
    document.getElementById("rag-status");


// ==================================================
// RESPONSE TABLE
// ==================================================

// This is the <tbody> from the HTML table.
//
// Make sure your HTML contains:
//
// <tbody id="rag-response-table-body"></tbody>

const ragResponseTableBody =
    document.getElementById(
        "rag-response-table-body"
    );


// ==================================================
// STATUS
// ==================================================

function setStatus(message) {

    ragStatus.textContent = message;

}


// ==================================================
// FORMAT VALUE
// ==================================================

function formatValue(value) {

    // ----------------------------------------------
    // Null / undefined
    // ----------------------------------------------

    if (
        value === null ||
        value === undefined
    ) {

        return "—";
    }


    // ----------------------------------------------
    // Arrays
    // ----------------------------------------------

    if (Array.isArray(value)) {

        if (value.length === 0) {
            return "None";
        }


        // Simple array
        if (
            value.every(
                item =>
                    typeof item !== "object" ||
                    item === null
            )
        ) {

            return value.join(", ");
        }


        // Array containing objects
        return JSON.stringify(
            value,
            null,
            2
        );
    }


    // ----------------------------------------------
    // Objects
    // ----------------------------------------------

    if (typeof value === "object") {

        return JSON.stringify(
            value,
            null,
            2
        );
    }


    // ----------------------------------------------
    // Everything else
    // ----------------------------------------------

    return String(value);
}


// ==================================================
// FORMAT FIELD NAME
// ==================================================

function formatFieldName(key) {

    return key
        // camelCase -> camel Case
        .replace(
            /([a-z])([A-Z])/g,
            "$1 $2"
        )

        // snake_case -> snake case
        .replace(
            /_/g,
            " "
        )

        // kebab-case -> kebab case
        .replace(
            /-/g,
            " "
        )

        // Capitalise first letter
        .replace(
            /^./,
            letter =>
                letter.toUpperCase()
        );
}


// ==================================================
// CLEAR RESPONSE TABLE
// ==================================================

function clearResponseTable() {

    ragResponseTableBody.innerHTML = "";

}


// ==================================================
// ADD TABLE ROW
// ==================================================

function addResponseRow(
    key,
    value
) {

    const row =
        document.createElement("tr");


    const heading =
        document.createElement("th");


    const cell =
        document.createElement("td");


    heading.textContent =
        formatFieldName(key);


    cell.textContent =
        formatValue(value);


    row.appendChild(
        heading
    );


    row.appendChild(
        cell
    );


    ragResponseTableBody.appendChild(
        row
    );
}


// ==================================================
// DISPLAY RESPONSE
// ==================================================

function showResponse(data) {

    clearResponseTable();


    // =================================================
    // STRING RESPONSE
    // =================================================

    if (typeof data === "string") {

        addResponseRow(
            "Response",
            data
        );

        return;
    }


    // =================================================
    // NULL / EMPTY RESPONSE
    // =================================================

    if (
        data === null ||
        data === undefined
    ) {

        addResponseRow(
            "Response",
            "No response data"
        );

        return;
    }


    // =================================================
    // ARRAY RESPONSE
    // =================================================

    if (Array.isArray(data)) {

        data.forEach(
            (item, index) => {

                addResponseRow(
                    `Item ${index + 1}`,
                    item
                );

            }
        );


        if (data.length === 0) {

            addResponseRow(
                "Response",
                "Empty array"
            );
        }


        return;
    }


    // =================================================
    // OBJECT RESPONSE
    // =================================================

    if (typeof data === "object") {

        const keys =
            Object.keys(data);


        if (keys.length === 0) {

            addResponseRow(
                "Response",
                "Empty object"
            );

            return;
        }


        keys.forEach(
            key => {

                addResponseRow(
                    key,
                    data[key]
                );

            }
        );


        return;
    }


    // =================================================
    // OTHER
    // =================================================

    addResponseRow(
        "Response",
        data
    );

}


// ==================================================
// LOADING
// ==================================================

function showLoading() {

    clearResponseTable();


    addResponseRow(
        "Response",
        "Loading..."
    );

}


// ==================================================
// CALL RAG ENDPOINT
// ==================================================

async function callRagEndpoint(
    endpoint,
    formData
) {

    try {

        setStatus(
            `Calling ${endpoint}...`
        );


        showLoading();


        const response =
            await fetch(
                endpoint,
                {
                    method: "POST",
                    body: formData
                }
            );


        let data;


        // ------------------------------------------
        // Try JSON first
        // ------------------------------------------

        try {

            data =
                await response.json();

        }

        // ------------------------------------------
        // Fall back to text
        // ------------------------------------------

        catch {

            data =
                await response.text();

        }


        // ------------------------------------------
        // Display response
        // ------------------------------------------

        showResponse(data);


        // ------------------------------------------
        // HTTP error
        // ------------------------------------------

        if (!response.ok) {

            setStatus(
                `Error: HTTP ${response.status}`
            );

            return;
        }


        // ------------------------------------------
        // Success
        // ------------------------------------------

        setStatus(
            `Success: HTTP ${response.status}`
        );

    }

    catch (error) {

        setStatus(
            "Request failed"
        );


        showResponse({
            status: "error",
            error: error.message
        });

    }

}


// ==================================================
// GET STUDENT ID
// ==================================================

function getStudentId() {

    if (!userId) {

        setStatus(
            "Unable to determine the current user's student ID"
        );

        return null;
    }


    const studentId =
        Number(userId);


    if (
        !Number.isInteger(studentId) ||
        studentId <= 0
    ) {

        setStatus(
            "Invalid student ID"
        );

        return null;
    }


    return studentId;

}


// ==================================================
// POST /rag/retrieve
// ==================================================

retrieveBtn.addEventListener(
    "click",
    async () => {

        const studentId =
            getStudentId();


        if (!studentId) {
            return;
        }


        const query =
            ragQuery.value.trim();


        const k =
            ragK.value;


        if (!query) {

            setStatus(
                "Please enter a query"
            );

            return;
        }


        const formData =
            new FormData();


        formData.append(
            "student_id",
            studentId
        );


        formData.append(
            "query",
            query
        );


        formData.append(
            "k",
            k
        );


        await callRagEndpoint(
            "/exams-api/rag/retrieve",
            formData
        );

    }
);


// ==================================================
// POST /rag/answer
// ==================================================

answerBtn.addEventListener(
    "click",
    async () => {

        const studentId =
            getStudentId();


        if (!studentId) {
            return;
        }


        const query =
            ragQuery.value.trim();


        const k =
            ragK.value;


        if (!query) {

            setStatus(
                "Please enter a query"
            );

            return;
        }


        const formData =
            new FormData();


        formData.append(
            "student_id",
            studentId
        );


        formData.append(
            "query",
            query
        );


        formData.append(
            "k",
            k
        );


        await callRagEndpoint(
            "/exams-api/rag/answer",
            formData
        );

    }
);
