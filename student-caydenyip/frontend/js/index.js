/*
==================================================
SERVICES
==================================================
*/

const SERVICES = [
    {
        key: "enrolment",
        label: "Enrolment",
        url: "http://localhost:8080"
    },
    {
        key: "assessments",
        label: "Assessments",
        url: "http://localhost:8081"
    },
    {
        key: "calendar",
        label: "Calendar",
        url: "http://localhost:8082"
    },
    {
        key: "notes",
        label: "Notes",
        url: "http://localhost:8083"
    },
    {
        key: "exams",
        label: "Exams",
        url: "http://localhost:8084"
    }
];


/*
==================================================
GET LOGGED-IN USER
==================================================

The login page stores the user in:

localStorage.user

Example:

{
    "id": 5,
    "name": "John"
}

or:

{
    "user_id": 5,
    "name": "John"
}

*/

function getCurrentUser() {

    try {

        const raw =
            localStorage.getItem("user");


        if (!raw) {

            return null;

        }


        return JSON.parse(raw);

    } catch (error) {

        console.error(
            "Unable to read user from localStorage:",
            error
        );

        return null;

    }

}


/*
==================================================
GET USER ID
==================================================
*/

function getUserId(user) {

    if (!user) {

        return null;

    }


    return (
        user.user_id ??
        user.id ??
        user.student_id ??
        null
    );

}


/*
==================================================
GET USER NAME
==================================================
*/

function getUserName(user) {

    if (!user) {

        return "";

    }


    return (
        user.name ??
        user.username ??
        ""
    );

}


/*
==================================================
CHECK LOGIN
==================================================
*/

function checkLoggedIn() {

    const user =
        getCurrentUser();


    const userId =
        getUserId(user);


    if (!user || userId == null) {

        console.log(
            "No logged-in user found."
        );

        window.location.href =
            "/login.html";

        return false;

    }


    return true;

}


/*
==================================================
TAB BUTTONS
==================================================
*/

const tabButtons =
    Array.from(
        document.querySelectorAll(
            ".tab-btn"
        )
    );


/*
==================================================
TAB FRAMES
==================================================
*/

const tabFrames = {

    normal:
        document.getElementById(
            "tab-frame-normal"
        ),

    "ai-mode":
        document.getElementById(
            "tab-frame-ai-mode"
        )

};


/*
==================================================
ACTIVATE TAB
==================================================
*/

function activateTab(tabName) {

    tabButtons.forEach(
        button => {

            button.classList.toggle(

                "is-active",

                button.dataset.tab ===
                tabName

            );

        }
    );


    Object.entries(
        tabFrames
    ).forEach(
        ([name, frame]) => {

            if (!frame) {

                return;

            }


            frame.classList.toggle(

                "is-active",

                name === tabName

            );

        }
    );


    window.location.hash =
        tabName;

}


/*
==================================================
TAB BUTTON EVENTS
==================================================
*/

tabButtons.forEach(
    button => {

        if (button.disabled) {

            return;

        }


        button.addEventListener(
            "click",
            () => {

                activateTab(
                    button.dataset.tab
                );

            }
        );

    }
);


/*
==================================================
RESTORE TAB
==================================================
*/

function restoreTab() {

    const hashTab =
        window.location.hash
            .replace("#", "");


    if (
        hashTab &&
        tabFrames[hashTab]
    ) {

        activateTab(
            hashTab
        );

    } else {

        activateTab(
            "normal"
        );

    }

}


/*
==================================================
UPDATE IFRAME URLS
==================================================

IMPORTANT:

The user ID is NOT added to the iframe URL.

The iframe pages can read the same:

localStorage.user

directly.

This means:

/exams/

instead of:

/exams/?user_id=5&name=John

*/

function updateIframeUrls() {

    const user =
        getCurrentUser();


    const userId =
        getUserId(user);


    if (!user || userId == null) {

        console.log(
            "No user ID found."
        );

        return;

    }


    const normalFrame =
        document.getElementById(
            "tab-frame-normal"
        );


    const aiFrame =
        document.getElementById(
            "tab-frame-ai-mode"
        );


    /*
     * Keep iframe URLs clean.
     *
     * The iframe itself reads localStorage.user.
     */

    if (normalFrame) {

        normalFrame.src =
            "tabs/normal.html";

    }


    if (aiFrame) {

        aiFrame.src =
            "tabs/ai-mode.html";

    }

}


/*
==================================================
UPDATE SERVICE LINKS
==================================================

The old version added:

?user_id=5&name=John

to every service URL.

We no longer need to do that.

Each service can read localStorage.user
if it is served from the same origin.

*/

function updateFeatureLinks() {

    const user =
        getCurrentUser();


    const userId =
        getUserId(user);


    if (!user || userId == null) {

        return;

    }


    document.querySelectorAll(
        "a"
    ).forEach(
        link => {

            const href =
                link.getAttribute(
                    "href"
                );


            if (!href) {

                return;

            }


            /*
             * Find which service this link
             * points to.
             */

            const matchedService =
                SERVICES.find(
                    service => {

                        return href.startsWith(
                            service.url
                        );

                    }
                );


            if (!matchedService) {

                return;

            }


            /*
             * Do NOT add user_id/name
             * to the URL.
             */

            link.href =
                matchedService.url;

        }
    );

}


/*
==================================================
INITIALISE PAGE
==================================================
*/

document.addEventListener(
    "DOMContentLoaded",
    () => {

        /*
         * Check that the user is logged in.
         */

        if (!checkLoggedIn()) {

            return;

        }


        /*
         * Set up tabs.
         */

        restoreTab();


        /*
         * Set iframe URLs.
         */

        updateIframeUrls();


        /*
         * Set service links.
         */

        updateFeatureLinks();

    }
);
