const API_URL = "http://localhost:5004";
const registerForm =
    document.getElementById("register-form");

if (registerForm) {

    registerForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            const name =
                document.getElementById("name")
                    .value
                    .trim();

            const email =
                document.getElementById("email")
                    .value
                    .trim();

            const password =
                document.getElementById("password")
                    .value;

            const message =
                document.getElementById("message");


            message.textContent = "Creating account...";


            try {

                const response = await fetch(
                    `${API_URL}/register`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type": "application/json"
                        },

                        body: JSON.stringify({
                            name: name,
                            email: email,
                            password: password
                        })
                    }
                );
                const data =
                    await response.json();

                if (!response.ok) {
                    message.textContent =
                        data.error ||
                        "Registration failed.";

                    return;
                }

                message.textContent =
                    "Account created successfully. Redirecting to login...";
                setTimeout(
                    function () {

                        window.location.href =
                            "login.html";

                    },
                    1000
                );
            } catch (error) {
                console.error(
                    "Registration error:",
                    error
                );
                message.textContent =
                    "Unable to connect to the server.";
            }
        }
    );
}

const loginForm =
    document.getElementById("login-form");

if (loginForm) {

    loginForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            const email =
                document.getElementById("email")
                    .value
                    .trim();

            const password =
                document.getElementById("password")
                    .value;

            const message =
                document.getElementById("message");
            message.textContent = "Signing in...";

            try {

                const response = await fetch(
                    `${API_URL}/login`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type": "application/json"
                        },

                        body: JSON.stringify({
                            email: email,
                            password: password
                        })
                    }
                );

                const data =
                    await response.json();
                if (!response.ok) {

                    message.textContent =
                        data.error ||
                        "Login failed.";

                    return;
                }

                localStorage.setItem(
                    "user",
                    JSON.stringify(data.user)
                );


                message.textContent =
                    "Login successful.";
                window.location.href =
                    "index.html";

            } catch (error) {

                console.error(
                    "Login error:",
                    error
                );

                message.textContent =
                    "Unable to connect to the server.";
            }
        }
    );
}