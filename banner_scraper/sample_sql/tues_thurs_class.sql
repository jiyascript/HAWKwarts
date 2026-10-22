-- only tues/thurs CS classes in the morning
SELECT o.course_id, c.title, s.section, m.days, m.time, m.location
FROM meetings m
JOIN sections s ON s.section_id = m.section_id
JOIN course_offerings o ON o.offering_id = s.offering_id
JOIN courses c ON c.course_id = o.course_id
WHERE o.term = 'Fall 2026' AND c.subject_code = 'CS'
  AND m.days = 'TR' AND m.time LIKE '%AM - %'
ORDER BY o.course_id;