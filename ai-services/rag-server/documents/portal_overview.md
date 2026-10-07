# ASD Student Portal

The ASD Student Portal is a student dashboard for viewing and organising subjects. Each feature is a microservice with its own frontend, backend and database, and each has an AI capability that uses a local Ollama model.

The portal contains five features: Course Enrolment, Calendar, Notebook, Assessment Tracker and Exam. Registration and login are shared across the portal, so a student signs in once and that identity is used by every feature.

The Calendar feature shows classes, deadlines and exams in a month view. Events can be added, edited, deleted, and dragged to another day to reschedule them. When an event is dragged, its time of day and duration are preserved.

The Calendar can import deadlines automatically. It reads outstanding assignments from the Assessment Tracker service and upcoming exams from the Exam service, identifies items that are not yet in the calendar, and offers them for confirmation before anything is added.

The Calendar study agent suggests revision sessions in free time before a deadline. Free time slots are computed by the application rather than by the language model, and the model only chooses between the slots it is given.

The Assessment Tracker records assignments with a due date, a weighting and a status of not started, in progress or completed. The weighting is the percentage of the subject mark that the assignment is worth.

The Exam feature holds the exam timetable, including the date and time of each exam.

The Notebook feature holds notebooks and notes for each subject, and supports searching across every note.

To run the application, Docker and Ollama with the qwen2.5:0.5b model are required. The application is started with docker compose up and the portal is reached on port 8000.
