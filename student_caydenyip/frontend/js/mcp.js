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

const mcpResult =
    document.getElementById("mcp-result");


// ==================================================
// RUN MCP TOOL
// ==================================================

async function runMCPTool() {

    const tool =
        mcpToolSelect.value;


    // Reset

    mcpError.hidden = true;
    mcpError.textContent = "";

    mcpResult.textContent =
        "Running MCP tool...";

    mcpLoading.hidden = false;
    mcpRunButton.disabled = true;


    // Validate current user

    if (!userId) {

        showMCPError(
            "Unable to determine the current user's student ID."
        );

        resetMCPState();

        return;
    }


    try {

        const response = await fetch(
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
                    // the currently logged-in user
                    student_id: Number(userId)
                })
            }
        );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "MCP request failed."
            );
        }


        // Display result

        mcpResult.textContent =
            JSON.stringify(
                data,
                null,
                2
            );

    }

    catch (error) {

        console.error(error);

        showMCPError(
            error.message
        );

        mcpResult.textContent =
            "No result.";

    }

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
