# Retrieval Validation

## Retrieval metrics

### course exam retrieval
- Query: `course exams`
- Retrieval status: `success`
- Retrieval mode: `vector`
- Retrieved: 5
- Relevant: 5
- Tier 1 results: 5
- Tier 2 results: 0
- P@5: 1.000
- R@5: 1.000
- Retrieved chunks: ['db_course_exam_17', 'db_course_exam_12', 'db_course_exam_11', 'db_course_exam_16', 'db_course_exam_14']
- Relevant chunks: ['db_course_exam_17', 'db_course_exam_12', 'db_course_exam_11', 'db_course_exam_16', 'db_course_exam_14']

### student count
- Query: `student count`
- Retrieval status: `success`
- Retrieval mode: `vector`
- Retrieved: 5
- Relevant: 2
- Tier 1 results: 5
- Tier 2 results: 0
- P@5: 0.400
- R@5: 1.000
- Retrieved chunks: ['db_student_exam_4', 'db_course_exam_1', 'db_course_exam_13', 'db_course_exam_5', 'db_student_exam_join_4']
- Relevant chunks: ['db_student_exam_4', 'db_student_exam_join_4']

### student exams
- Query: `Which students have exams?`
- Retrieval status: `success`
- Retrieval mode: `vector`
- Retrieved: 5
- Relevant: 2
- Tier 1 results: 4
- Tier 2 results: 0
- P@5: 0.400
- R@5: 1.000
- Retrieved chunks: ['db_student_exam_2', 'db_course_exam_6', 'db_student_exam_join_2', 'db_course_exam_1', 'repo_index']
- Relevant chunks: ['db_student_exam_2', 'db_student_exam_join_2']

### exam schedule
- Query: `exam schedule`
- Retrieval status: `success`
- Retrieval mode: `vector`
- Retrieved: 5
- Relevant: 3
- Tier 1 results: 5
- Tier 2 results: 0
- P@5: 0.600
- R@5: 1.000
- Retrieved chunks: ['db_course_exam_count', 'db_course_exam_18', 'db_student_exam_count', 'db_course_exam_5', 'db_course_exam_8']
- Relevant chunks: ['db_course_exam_18', 'db_course_exam_5', 'db_course_exam_8']

### report retrieval
- Query: `CI report status`
- Retrieval status: `success`
- Retrieval mode: `vector`
- Retrieved: 5
- Relevant: 0
- Tier 1 results: 4
- Tier 2 results: 0
- P@5: 0.000
- R@5: 0.000
- Retrieved chunks: ['db_course_exam_8', 'db_course_exam_4', 'db_course_exam_5', 'db_course_exam_16', 'repo_index']
- Relevant chunks: []

## Answer validation

### student count
- Status: `success`
- Confidence: `High`
- Citation count: 5
- Missing expected terms: []
- Passed: `True`
- Answer: Answer:
There are 1 unique students in the retrieved evidence.

### Which students have exams?
- Status: `success`
- Confidence: `High`
- Citation count: 5
- Missing expected terms: []
- Passed: `True`
- Answer: Answer:
Student 2 -> Course 2 -> 48024 Final Exam -> 2026-11-12 13:00 -> Status: Completed

### What exams are available?
- Status: `success`
- Confidence: `High`
- Citation count: 5
- Missing expected terms: ['exam']
- Passed: `False`
- Answer: LLM unavailable: Request timed out.
