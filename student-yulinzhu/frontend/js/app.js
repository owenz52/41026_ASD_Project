const API_URL = "http://localhost:5001";
const params = new URLSearchParams(window.location.search);

const loggedInUserId = Number(params.get("user_id"));
const loggedInUserName = params.get("name");

if (!loggedInUserId) {
    alert("Please login first.");

    window.location.href =
        "http://localhost:8081/login.html";
}

async function askAI() {
    const question = document.getElementById("ai-input").value.trim();
    const responseBox = document.getElementById("ai-response");

    if (!question) {
        responseBox.innerText = "Please enter a question.";
        return;
    }
    responseBox.innerText = "Loading response...";
    try {
        const response = await fetch(`${API_URL}/ask`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ question: question })
        });
        const data = await response.json();

        if(!response.ok) {
            responseBox.innerText = data.error || "Failed to get AI response. Please try again later.";
            return;
        }
        responseBox.innerText = data.answer;
    } catch (error) {
        console.error("Error fetching AI response:", error);
        responseBox.innerText = "Failed to get AI response. Please try again later.";
    }
}

async function loadCourses() {
    try {
        const response = await fetch(`${API_URL}/courses`);

        if (!response.ok) {
            throw new Error("Failed to load courses");
        }

        const courses = await response.json();

        const courseList = document.getElementById("courses-list");
        courseList.innerHTML = "";

        courses.forEach(course => {
            const courseElement = document.createElement("div");
            courseElement.className = "course-card";

            const available = Boolean(course.availability);

            courseElement.innerHTML = `
                <div class="course-top">
                    <span class="course-code">
                        ${course.course_code}
                    </span>

                    <span class="availability ${available ? "" : "not-available"}">
                        ${available ? "Available" : "Not Available"}
                    </span>
                </div>

                <h3>${course.course_name}</h3>

                <p class="course-description">
                    ${course.description}
                </p>

                <button
                    class="enrol-button"
                    onclick="enrolCourse(${course.course_id})"
                    ${available ? "" : "disabled"}
                >
                    Enrol
                </button>
            `;

            courseList.appendChild(courseElement);
        });

    } catch (error) {
        console.error("Failed to load courses:", error);

        document.getElementById("courses-list").innerText =
            "Failed to load courses. Please try again later.";
    }
}

async function enrolCourse(courseId) {

    try {
        const checkResponse = await fetch(`${API_URL}/enrolments`);

        if (!checkResponse.ok) {
            throw new Error("Failed to check enrolments");
        }

        const enrolments = await checkResponse.json();

        const alreadyEnrolled = enrolments.some(
            enrolment =>
                Number(enrolment.student_id) === loggedInUserId &&
                Number(enrolment.course_id) === Number(courseId)
        );

        if (alreadyEnrolled) {
            alert("You are already enrolled in this course.");
            return;
        }

        const today =
            new Date().toISOString().split("T")[0];

        const response = await fetch(
            `${API_URL}/enrolments`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    student_id: loggedInUserId,
                    course_id: courseId,
                    enrolment_status: "enrolled",
                    enrolment_date: today
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            alert(
                data.error ||
                "Failed to create enrolment."
            );
            return;
        }

        alert("Enrolment created successfully.");

        loadCourses();
        loadEnrolments();

    } catch (error) {
        console.error(
            "Failed to create enrolment:",
            error
        );

        alert("Failed to create enrolment.");
    }
}

async function loadEnrolments() {
    try {
        const [enrolmentResponse, courseResponse] = await Promise.all([
            fetch(`${API_URL}/enrolments`),
            fetch(`${API_URL}/courses`)
        ]);

        if (!enrolmentResponse.ok || !courseResponse.ok) {
            throw new Error("Failed to load enrolment data");
        }

        const allEnrolments =
        await enrolmentResponse.json();

        const courses =
        await courseResponse.json();

        const enrolments = allEnrolments.filter(
            enrolment =>
                Number(enrolment.student_id) === loggedInUserId
        );

        const courseMap = {};

        courses.forEach(course => {
            courseMap[course.course_id] = course;
        });

        const enrolmentList = document.getElementById("enrolments-list");

        let html = `
            <table class="enrolment-table">
                <thead>
                    <tr>
                        <th>Enrolment ID</th>
                        <th>Student ID</th>
                        <th>Course</th>
                        <th>Status</th>
                        <th>Enrolment Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        enrolments.forEach((enrolment, index) => {
            const course = courseMap[enrolment.course_id];

            const courseDisplay = course
                ? `${course.course_code} - ${course.course_name}`
                : `Course ID ${enrolment.course_id}`;

            html += `
                <tr>
                    <td>${index+1}</td>
                    <td>${enrolment.student_id}</td>
                    <td>${courseDisplay}</td>

                    <td>
                        <span class="status-badge">
                            ${enrolment.enrolment_status}
                        </span>
                    </td>

                    <td>${enrolment.enrolment_date}</td>

                    <td class="action-buttons">
                        <button
                            class="edit-button"
                            onclick="editEnrolment(${enrolment.enrolment_id})"
                        >
                            Edit
                        </button>

                        <button
                            class="delete-button"
                            onclick="deleteEnrolment(${enrolment.enrolment_id})"
                        >
                            Withdraw
                        </button>
                    </td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        enrolmentList.innerHTML = html;

    } catch (error) {
        console.error("Failed to load enrolments:", error);

        document.getElementById("enrolments-list").innerText =
            "Failed to load enrolments. Please try again later.";
    }
}

async function editEnrolment(
    enrolmentId,
    currentCourseId,
    currentStatus,
    currentDate
) {
    const courseId = prompt(
        "Enter Course ID:",
        currentCourseId
    );

    if (!courseId) {
        return;
    }

    const status = prompt(
        "Enter enrolment status:",
        currentStatus
    );

    if (!status) {
        return;
    }

    const enrolmentDate = prompt(
        "Enter enrolment date (YYYY-MM-DD):",
        currentDate
    );

    if (!enrolmentDate) {
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/enrolments/${enrolmentId}`,
            {
                method: "PUT",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    course_id: Number(courseId),
                    enrolment_status: status,
                    enrolment_date: enrolmentDate
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            alert(
                data.error ||
                "Failed to update enrolment."
            );
            return;
        }

        alert("Enrolment updated successfully.");

        loadEnrolments();

    } catch (error) {
        console.error(
            "Failed to update enrolment:",
            error
        );

        alert("Failed to update enrolment.");
    }
}

async function deleteEnrolment(enrolmentId) {
    const confirmed = confirm(
        "Are you sure you want to delete this enrolment?"
    );

    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/enrolments/${enrolmentId}`,
            {
                method: "DELETE"
            }
        );

        const data = await response.json();

        if (!response.ok) {
            alert(
                data.error ||
                "Failed to delete enrolment."
            );
            return;
        }

        alert("Enrolment deleted successfully.");

        loadEnrolments();

    } catch (error) {
        console.error(
            "Failed to delete enrolment:",
            error
        );

        alert("Failed to delete enrolment.");
    }
}

loadCourses();
loadEnrolments();