# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- View activity rosters without signing in
- Sign up and unregister students as an authenticated teacher

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   cd src
   uvicorn app:app --reload
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## Teacher accounts

Create `src/teachers.json` with the teacher usernames and PBKDF2-SHA256 password
hashes. The file is ignored by Git; do not commit teacher credentials. The
application returns an error from the login endpoint until this file is
configured.

Generate a password hash with Python:

```sh
python - <<'PY'
import base64
import getpass
import hashlib
import secrets

password = getpass.getpass("Teacher password: ").encode("utf-8")
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", password, salt, 600_000)
encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
print(f"pbkdf2_sha256$600000${encode(salt)}${encode(digest)}")
PY
```

Put the generated value into the file in this format:

```json
{
  "teachers": [
    {
      "username": "teacher1",
      "password_hash": "pbkdf2_sha256$600000$REPLACE_WITH_GENERATED_SALT$REPLACE_WITH_GENERATED_DIGEST"
    }
  ]
}
```

For a different credentials-file location, set `TEACHER_CREDENTIALS_FILE`.
Teacher sessions are held in memory and expire after eight hours. For an
HTTPS deployment, set `TEACHER_COOKIE_SECURE=true` so the session cookie is
only sent over HTTPS.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                     | Log in a teacher and create a session                               |
| GET    | `/auth/session`                                                   | Check whether the browser has an active teacher session             |
| POST   | `/auth/logout`                                                    | End the current teacher session                                     |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Sign up a student (teacher session required)                        |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher session required)                  |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
