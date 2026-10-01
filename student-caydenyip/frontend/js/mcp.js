// ==================================================
// MCP TESTER
// ==================================================

const mcpToolSelect =
    document.getElementById("mcp-tool");

const mcpRunButton =
    document.getElementById("mcp-run-button");

const mcpLoading =
    document.getElementById("mcp-loading");

const mcpError =
    document.getElementById("mcp-error");

const mcpResultTableBody =
    document.getElementById(
        "mcp-result-table-body"
    );


// ==================================================
// FORMAT FIELD NAME
// ==================================================

function formatMCPFieldName(key) {

    return key

        // camelCase
        .replace(
            /([a-z])([A-Z])/g,
            "$1 $2"
        )

        // snake_case
        .replace(
            /_/g,
            " "
        )

        // kebab-case
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
// FORMAT VALUE
// ==================================================

function formatMCPValue(value) {

    // Null / undefined

    if (
        value === null ||
        value === undefined
    ) {

        return "—";
    }


    // Arrays

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


        // Array of objects

        return JSON.stringify(
            value,
            null,
            2
        );
    }


    // Objects

    if (
        typeof value === "object"
    ) {

        return JSON.stringify(
            value,
            null,
            2
        );
    }


    // String / number / boolean

    return String(value);
}


// ==================================================
// CLEAR RESULT
// ==================================================

function clearMCPResult() {

    mcpResultTableBody.innerHTML = "";

}


// ==================================================
// ADD RESULT ROW
// ==================================================

function addMCPResultRow(
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
        formatMCPFieldName(key);


    cell.textContent =
        formatMCPValue(value);


    row.appendChild(
        heading
    );


    row.appendChild(
        cell
    );


    mcpResultTableBody.appendChild(
        row
    );

}


// ==================================================
// DISPLAY RESULT
// ==================================================

function showMCPResult(data) {

    clearMCPResult();


    // =================================================
    // STRING
    // =================================================

    if (
        typeof data === "string"
    ) {

        addMCPResultRow(
            "Response",
            data
        );

        return;
    }


    // =================================================
    // NULL / UNDEFINED
    // =================================================

    if (
        data === null ||
        data === undefined
    ) {

        addMCPResultRow(
            "Response",
            "No response data"
        );

        return;
    }


    // =================================================
    // ARRAY
    // =================================================

    if (Array.isArray(data)) {

        if (data.length === 0) {

            addMCPResultRow(
                "Response",
                "Empty array"
            );

            return;
        }


        data.forEach(
            (item, index) => {

                addMCPResultRow(
                    `Item ${index + 1}`,
                    item
                );

            }
        );

        return;
    }


    // =================================================
    // OBJECT
    // =================================================

    if (
        typeof data === "object"
    ) {

        const keys =
            Object.keys(data);


        if (keys.length === 0) {

            addMCPResultRow(
                "Response",
                "Empty object"
            );

            return;
        }


        keys.forEach(
            key => {

                addMCPResultRow(
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

    addMCPResultRow(
        "Response",
        data
    );

}


// ==================================================
// SHOW LOADING
// ==================================================

function showMCPLoading() {

    clearMCPResult();


    addMCPResultRow(
        "Response",
        "Running MCP tool..."
    );

}


// ==================================================
// RUN MCP TOOL
// ==================================================

async function runMCPTool() {

    const tool =
        mcpToolSelect.value;


    // =================================================
    // RESET
    // =================================================

    mcpError.hidden = true;

    mcpError.textContent = "";


    showMCPLoading();


    mcpLoading.hidden = false;

    mcpRunButton.disabled = true;


    // =================================================
    // VALIDATE CURRENT USER
    // =================================================

    if (!userId) {

        showMCPError(
            "Unable to determine the current user's student ID."
        );

        resetMCPState();

        return;
    }


    // =================================================
    // CALL MCP ENDPOINT
    // =================================================

    try {

        const response =
            await fetch(
                "/exams-api/mcp/test",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        tool: tool,

                        // Automatically use
                        // currently logged-in user
                        student_id:
                            Number(userId)

                    })
                }
            );


        let data;


        // =================================================
        // TRY JSON
        // =================================================

        try {

            data =
                await response.json();

        }

        // =================================================
        // FALLBACK TO TEXT
        // =================================================

        catch {

            data =
                await response.text();

        }


        // =================================================
        // HTTP ERROR
        // =================================================

        if (!response.ok) {

            const errorMessage =
                typeof data === "object"
                    ? (
                        data.error ||
                        "MCP request failed."
                    )
                    : data;


            throw new Error(
                errorMessage
            );
        }


        // =================================================
        // DISPLAY RESULT
        // =================================================

        showMCPResult(data);

    }


    // =================================================
    // ERROR
    // =================================================

    catch (error) {

        console.error(error);


        showMCPError(
            error.message
        );


        clearMCPResult();


        addMCPResultRow(
            "Status",
            "Error"
        );


        addMCPResultRow(
            "Message",
            error.message
        );

    }


    // =================================================
    // RESET
    // =================================================

    finally {

        resetMCPState();

    }

}


// ==================================================
// ERROR
// ==================================================

function showMCPError(message) {

    mcpError.textContent =
        message;

    mcpError.hidden = false;

}


// ==================================================
// RESET
// ==================================================

function resetMCPState() {

    mcpLoading.hidden = true;

    mcpRunButton.disabled = false;

}


// ==================================================
// BUTTON
// ==================================================

if (mcpRunButton) {

    mcpRunButton.addEventListener(
        "click",
        runMCPTool
    );

}
