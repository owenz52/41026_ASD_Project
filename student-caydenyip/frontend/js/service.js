const API_URL = "/exams-api";

function getCurrentUser() {
    try {
        const raw = localStorage.getItem("user");
        return raw ? JSON.parse(raw) : null;
    } catch (error) {
        console.error("Unable to read user:", error);
        return null;
    }
}

function getUserId(user) {
    return user?.user_id ?? user?.id ?? user?.student_id ?? null;
}

const currentUser = getCurrentUser();
const userId = getUserId(currentUser);

function checkLoggedIn() {
    if (!currentUser || userId == null) {
        window.location.href = "/login.html";
        return false;
    }

    return true;
}
