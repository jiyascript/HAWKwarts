-- find cs courses in catalog but not offered this semester
SELECT c.course_id, c.title
FROM course_offerings o
JOIN courses c ON c.course_id = o.course_id
LEFT JOIN sections s ON s.offering_id = o.offering_id
WHERE o.term = 'Fall 2026' AND c.subject_code = 'ECON' AND s.section_id IS NULL
ORDER BY c.course_id;