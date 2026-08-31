import os
import requests

from werkzeug.security import generate_password_hash, check_password_hash


DATABASE_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://shared-user-db-container:5003"
)


def register_user(name, email, password):
    hashed_password = generate_password_hash(password)

    try:
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/users",
            json={
                "name": name,
                "email": email,
                "password": hashed_password
            },
            timeout=10
        )

        return response.json(), response.status_code

    except requests.RequestException as error:
        return {
            "error": f"Database service unavailable: {str(error)}"
        }, 503


def login_user(email, password):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/users/email/{email}",
            timeout=10
        )

        if response.status_code == 404:
            return {
                "error": "Invalid email or password"
            }, 401

        if response.status_code != 200:
            return {
                "error": "Database service error"
            }, 500

        user = response.json()

        if not check_password_hash(
            user["password"],
            password
        ):
            return {
                "error": "Invalid email or password"
            }, 401

        return {
            "message": "Login successful",
            "user": {
                "user_id": user["user_id"],
                "name": user["name"],
                "email": user["email"]
            }
        }, 200

    except requests.RequestException as error:
        return {
            "error": f"Database service unavailable: {str(error)}"
        }, 503