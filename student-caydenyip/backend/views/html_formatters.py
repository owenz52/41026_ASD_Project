def format_exams_html(exams):
    if not exams:
        return "<p>No exams found.</p>"

    html = "<ul>"

    for exam in exams:
        html += (
            f"<li>Exam ID: {exam['exam_id']} - "
            f"Course ID: {exam['course_id']} - "
            f"Student ID: {exam['student_id']} - "
            f"Exam: {exam['exam_name']} - "
            f"Time: {exam['exam_time']}</li>"
        )

    html += "</ul>"

    return html


def format_exam_html(exam):
    return (
        f"<p>"
        f"Exam ID: {exam['exam_id']}<br>"
        f"Course ID: {exam['course_id']}<br>"
        f"Student ID: {exam['student_id']}<br>"
        f"Exam Name: {exam['exam_name']}<br>"
        f"Exam Time: {exam['exam_time']}"
        f"</p>"
    )
