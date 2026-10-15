-- details about phys123
SELECT s.crn, s.section, m.days, m.time, m.location,
    GROUP_CONCAT(p.name, ', ') AS instructors,
    s.remaining AS seats_left, s.waitlist_remaining AS waitlist_left
FROM course_offerings o
JOIN sections s ON s.offering_id = o.offering_id
JOIN meetings m ON m.section_id = s.section_id
LEFT JOIN meeting_instructors mi ON mi.meeting_id = m.meeting_id
LEFT JOIN professors p ON p.professor_id = mi.professor_id
WHERE o.course_id = 'FDSN 201' AND o.term = 'Fall 2026'
GROUP BY m.meeting_id
ORDER BY s.section;