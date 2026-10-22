-- search for an online section
SELECT o.course_id, c.title, s.crn, s.section, s.campus
FROM sections s
JOIN course_offerings o ON o.offering_id = s.offering_id
JOIN courses c ON c.course_id = o.course_id
WHERE o.term = 'Fall 2026' AND c.subject_code = 'MATH' 
    AND s.campus LIKE '%Internet%' 
ORDER BY o.course_id;