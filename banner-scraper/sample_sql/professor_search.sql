-- find courses taught by dr. jacek this sem
SELECT o.course_id, c.title, s.crn, s.section, m.days, m.time, m.location
FROM professors p
JOIN meeting_instructors mi ON mi.professor_id = p.professor_id
JOIN meetings m ON m.meeting_id = mi.meeting_id
JOIN sections s ON s.section_id = m.section_id
JOIN course_offerings o ON o.offering_id = s.offering_id
JOIN courses c ON c.course_id = o.course_id
WHERE p.name LIKE '%Jacek%' AND o.term = 'Fall 2026'
ORDER BY o.course_id, s.section;