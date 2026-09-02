const SERVICES = [
    { key: "enrolment", label: "Enrolment", url: "http://localhost:8080" },
    { key: "assessments", label: "Assessments", url: "http://localhost:8081" },
    { key: "calendar", label: "Calendar", url: "http://localhost:8082" },
    { key: "notes", label: "Notes", url: "http://localhost:8083" },
    { key: "exams", label: "Exams", url: "http://localhost:8084" },
];







const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));






const tabFrames = {
    normal: document.getElementById("tab-frame-normal"),
    "ai-mode": document.getElementById("tab-frame-ai-mode"),
};

function activateTab(tabName) {
    tabButtons.forEach((button) => {
        button.classList.toggle(
            "is-active",
            button.dataset.tab === tabName
        );
    });

    Object.entries(tabFrames).forEach(([name, frame]) => {
        frame.classList.toggle(
            "is-active",
            name === tabName
        );
    });

    window.location.hash = tabName;
}

tabButtons.forEach((button) => {
    if (button.disabled) {
        return;
    }

    button.addEventListener("click", () => {
        activateTab(button.dataset.tab);
    });
});

const hashTab = window.location.hash.replace("#", "");

if (hashTab && tabFrames[hashTab]) {
    activateTab(hashTab);
} else {
    activateTab("normal");
}





function getUserFromUrl() {

    const params =
        new URLSearchParams(window.location.search);

    return {
        userId: params.get("user_id"),
        name: params.get("name")
    };
}


function updateIframeUrls() {

    const user = getUserFromUrl();

    if (!user.userId) {
        console.log("No user ID found");
        return;
    }

    const normalFrame =
        document.getElementById("tab-frame-normal");

    const aiFrame =
        document.getElementById("tab-frame-ai-mode");


    normalFrame.src =
        `tabs/normal.html?user_id=${encodeURIComponent(user.userId)}&name=${encodeURIComponent(user.name || "")}`;


    aiFrame.src =
        `tabs/ai-mode.html?user_id=${encodeURIComponent(user.userId)}&name=${encodeURIComponent(user.name || "")}`;
}


document.addEventListener("DOMContentLoaded", () => {

    updateIframeUrls();

});




function updateFeatureLinks() {
    const user = getUserFromUrl();
    if (user.userId == null) {
        return;
    }
    const userId = user.userId || user.id;
    const name = user.name || "";

    if (!userId) {
        return;
    }

    const serviceUrls = SERVICES.map(service => service.url);
    document.querySelectorAll("a").forEach(link => {
        const href = link.getAttribute("href");
        if (!href) {
            return;
        }
        const matchedService = serviceUrls.find(url => 
            href.startsWith(url)
        );
        if (!matchedService) {
            return;
        }
        const target = new URL(matchedService);
        target.searchParams.set("user_id", userId);
        target.searchParams.set("name", name);
        link.href = target.toString();
    });
}


document.addEventListener("DOMContentLoaded", () => {
    updateFeatureLinks();
});