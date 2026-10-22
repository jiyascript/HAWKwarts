-- learn more about CS 450
SELECT c.course_id, c.title, o.course_description, o.learning_objectives
FROM course_offerings o
JOIN courses c ON c.course_id = o.course_id
WHERE o.course_id = 'CS 450' AND o.term = 'Fall 2026';