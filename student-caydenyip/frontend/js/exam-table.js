function sortExams(exams) {
    return exams.sort((a, b) => {
        const dateA = new Date(
            `${a.exam_date}T${a.exam_time || "00:00"}`
        );

        const dateB = new Date(
            `${b.exam_date}T${b.exam_time || "00:00"}`
        );

        return dateA - dateB;
    });
}

function createExamTable(exams, showActions = true) {
    sortExams(exams);

    return `
        <div class="exam-table-scroll">
            <table class="exam-table">
                <thead>
                    <tr>
                        <th>Course ID</th>
                        <th>Exam Name</th>
                        <th>Exam Date</th>
                        <th>Exam Time</th>
                        <th>Status</th>
                        ${showActions ? "<th>Actions</th>" : ""}
                    </tr>
                </thead>

                <tbody>
                    ${exams.map(exam => {
                        const completed = exam.status === "Completed";

                        return `
                            <tr>
                                <td>${exam.course_id}</td>
                                <td>${exam.exam_name}</td>
                                <td>${exam.exam_date}</td>
                                <td>${exam.exam_time || ""}</td>

                                <td>
                                    <button
                                        type="button"
                                        class="status-btn ${
                                            completed
                                                ? "status-completed"
                                                : "status-uncompleted"
                                        }"
                                        onclick="toggleStatus(
                                            ${exam.exam_id},
                                            '${exam.status}'
                                        )"
                                    >
                                        ${exam.status}
                                    </button>
                                </td>

                                ${
                                    showActions
                                        ? `
                                            <td>
                                                <button
                                                    type="button"
                                                    class="delete-btn"
                                                    onclick="deleteExam(${exam.exam_id})"
                                                >
                                                    Delete
                                                </button>
                                            </td>
                                        `
                                        : ""
                                }
                            </tr>
                        `;
                    }).join("")}
                </tbody>
            </table>
        </div>
    `;
}
