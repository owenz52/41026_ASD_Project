# Shared MCP Server

Exposes the project's data to every feature as a set of named tools, so one
feature can reach another feature's information through a single interface.

Release 1 requires this server to run locally and **not** be containerised, so
it is started directly with Python and is deliberately absent from
`docker-compose.yml`.

## Running it

```bash
pip install -r requirements.txt
python app.py
```

It listens on port 5100. Start it before the features that use it; the rest of
the application runs normally without it, reporting MCP as unavailable.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `list_calendar_events` | `student_id`, optional `start_date`, `end_date`, `subject` | A student's calendar events |
| `list_assignments` | `student_id`, optional `status` | Assignments with due dates and weightings |
| `list_exams` | optional `student_id` | Exam timetable entries |
| `list_courses` | none | The course catalogue |
| `list_enrolments` | optional `student_id` | Enrolment records |
| `search_notes` | `query` | Notes matching a phrase |
| `student_overview` | `student_id` | Events, assignments, exams and enrolments together |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and tool count |
| GET | `/tools` | The registered tools and their input schemas |
| POST | `/invoke` | `{"tool": name, "arguments": {...}}` |

## Configuration

The server reads the feature database services on the ports Docker Compose
publishes to the host. Each is overridable, which is how the tests point it at
stubs.

| Variable | Default |
|---|---|
| `MCP_PORT` | 5100 |
| `ENROLMENT_DB_URL` | http://localhost:5002 |
| `NOTEBOOK_DB_URL` | http://localhost:5004 |
| `CALENDAR_DB_URL` | http://localhost:5006 |
| `ASSESSMENT_DB_URL` | http://localhost:5008 |
| `EXAM_DB_URL` | http://localhost:5010 |
| `MCP_UPSTREAM_TIMEOUT` | 10 |

## Failure behaviour

A tool never raises out of the server. If a feature database service is
unavailable the tool returns an error with HTTP 502 and the server keeps
serving every other tool. `student_overview` goes further: it gathers each
source independently and reports which ones were unavailable, so a stopped
container reduces the overview rather than failing it.
