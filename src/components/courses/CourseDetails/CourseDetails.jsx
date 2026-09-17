import "./CourseDetails.css";

import Badge from "../../ui/Badge/Badge";
import Button from "../../ui/Button/Button";

function CourseDetails({
    courseCode,
    courseName,
    credits,
    description,
    prerequisites = [],
    interests = [],
    onAddCourse,
    className = "",
}) {
    return (
        <div className={`course-details ${className}`}>

            <div className="course-details__header">
                <div>
                    <h2 className="course-details__code">
                        {courseCode}
                    </h2>

                    <p className="course-details__name">
                        {courseName}
                    </p>
                </div>

                {credits && (
                    <Badge text={`${credits} Credits`} />
                )}
            </div>

            {description && (
                <div className="course-details__section">
                    <h3>Description</h3>

                    <p>{description}</p>
                </div>
            )}

            {prerequisites.length > 0 && (
                <div className="course-details__section">
                    <h3>Prerequisites</h3>

                    <div className="course-details__items">
                        {prerequisites.map((prerequisite) => (
                            <Badge
                                key={prerequisite}
                                text={prerequisite}
                            />
                        ))}
                    </div>
                </div>
            )}

            {interests.length > 0 && (
                <div className="course-details__section">
                    <h3>Related Interests</h3>

                    <div className="course-details__items">
                        {interests.map((interest) => (
                            <Badge
                                key={interest}
                                text={interest}
                                variant="info"
                            />
                        ))}
                    </div>
                </div>
            )}

            {onAddCourse && (
                <div className="course-details__actions">
                    <Button onClick={onAddCourse}>
                        Add Course
                    </Button>
                </div>
            )}

        </div>
    );
}

export default CourseDetails;