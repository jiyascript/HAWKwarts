-- prerequisites for cs 550
SELECT c.course_id, o.levels, o.prerequisites, o.general_requirements,
    o.restrictions, o.mutual_exclusions
FROM course_offerings o
JOIN courses c ON c.course_id = o.course_id
WHERE o.course_id = 'CS 550' AND o.term = 'Fall 2026';