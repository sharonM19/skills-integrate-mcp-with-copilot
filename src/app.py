"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import base64
import binascii
import hashlib
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")

SESSION_COOKIE_NAME = "teacher_session"
SESSION_MAX_AGE = 8 * 60 * 60
PASSWORD_HASH_ITERATIONS = 600_000
sessions: dict[str, float] = {}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


def _decode_password_hash(password_hash: str) -> tuple[int, bytes, bytes]:
    try:
        algorithm, iteration_count, encoded_salt, encoded_digest = (
            password_hash.split("$")
        )
        iterations = int(iteration_count)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 1_000_000:
            raise ValueError
        salt = base64.b64decode(
            encoded_salt + "=" * (-len(encoded_salt) % 4),
            altchars=b"-_",
            validate=True,
        )
        digest = base64.b64decode(
            encoded_digest + "=" * (-len(encoded_digest) % 4),
            altchars=b"-_",
            validate=True,
        )
        if len(salt) < 16 or len(digest) != hashlib.sha256().digest_size:
            raise ValueError
        return iterations, salt, digest
    except (ValueError, binascii.Error) as error:
        raise HTTPException(
            status_code=503,
            detail="Teacher credentials are not configured correctly",
        ) from error


def _load_teacher_accounts() -> dict[str, tuple[int, bytes, bytes]]:
    credentials_path = Path(
        os.environ.get("TEACHER_CREDENTIALS_FILE", current_dir / "teachers.json")
    )
    try:
        credential_data = json.loads(credentials_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Teacher credentials are not configured",
        ) from error

    if (
        not isinstance(credential_data, dict)
        or not isinstance(credential_data.get("teachers"), list)
        or not credential_data["teachers"]
    ):
        raise HTTPException(
            status_code=503,
            detail="Teacher credentials are not configured correctly",
        )

    accounts = {}
    for teacher in credential_data["teachers"]:
        if (
            not isinstance(teacher, dict)
            or not isinstance(teacher.get("username"), str)
            or not teacher["username"].strip()
            or not isinstance(teacher.get("password_hash"), str)
            or teacher["username"] in accounts
        ):
            raise HTTPException(
                status_code=503,
                detail="Teacher credentials are not configured correctly",
            )
        accounts[teacher["username"]] = _decode_password_hash(
            teacher["password_hash"]
        )
    return accounts


def _password_matches(
    password: str, password_hash: tuple[int, bytes, bytes]
) -> bool:
    iterations, salt, expected_digest = password_hash
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return secrets.compare_digest(actual_digest, expected_digest)


def _require_teacher(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    expires_at = sessions.get(token) if token else None
    if expires_at is None or expires_at <= time.time():
        if token:
            sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Teacher login required")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=os.environ.get("TEACHER_COOKIE_SECURE", "").lower() == "true",
        samesite="strict",
        path="/",
    )

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/auth/login")
def login(credentials: LoginRequest, response: Response):
    accounts = _load_teacher_accounts()
    account_hash = accounts.get(credentials.username)
    dummy_hash = (
        PASSWORD_HASH_ITERATIONS,
        b"mergington-dummy-salt",
        hashlib.sha256(b"invalid-password").digest(),
    )
    password_is_valid = _password_matches(
        credentials.password, account_hash or dummy_hash
    )
    if account_hash is None or not password_is_valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = secrets.token_urlsafe(32)
    sessions[token] = time.time() + SESSION_MAX_AGE
    _set_session_cookie(response, token)
    return {"authenticated": True}


@app.get("/auth/session")
def get_auth_session(request: Request):
    try:
        _require_teacher(request)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        return {"authenticated": False}
    return {"authenticated": True}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        sessions.pop(token, None)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=os.environ.get("TEACHER_COOKIE_SECURE", "").lower() == "true",
        samesite="strict",
        path="/",
    )
    return {"authenticated": False}


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str, email: str, _: None = Depends(_require_teacher)
):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str, email: str, _: None = Depends(_require_teacher)
):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
