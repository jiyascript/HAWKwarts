import "./CourseList.css";

import CourseCard from "../CourseCard/CourseCard";

function CourseList({
    courses = [],
    onViewDetails,
    className = "",
}) {
    if (courses.length === 0) {
        return (
            <p className="course-list__empty">
                No courses found.
            </p>
        );
    }

    return (
        <div className={`course-list ${className}`}>

            {courses.map((course) => (
                <CourseCard
                    key={course.id}
                    courseCode={course.courseCode}
                    courseName={course.courseName}
                    credits={course.credits}
                    description={course.description}
                    interests={course.interests}
                    onViewDetails={() => onViewDetails?.(course)}
                />
            ))}

        </div>
    );
}

export default CourseList;