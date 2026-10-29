import "./CourseCard.css";

import Card from "../../ui/Card/Card";
import Badge from "../../ui/Badge/Badge";
import Button from "../../ui/Button/Button";

function CourseCard({
    courseCode,
    courseName,
    credits,
    description,
    interests = [],
    onViewDetails,
    className = "",
}) {
    return (
        <Card className={`course-card ${className}`}>

            <div className="course-card__header">
                <div>
                    <h3 className="course-card__code">
                        {courseCode}
                    </h3>

                    <p className="course-card__name">
                        {courseName}
                    </p>
                </div>

                {credits && (
                    <Badge text={`${credits} Credits`} />
                )}
            </div>

            {interests.length > 0 && (
                <div className="course-card__interests">
                    {interests.map((interest) => (
                        <Badge
                            key={interest}
                            text={interest}
                            variant="info"
                        />
                    ))}
                </div>
            )}

            {description && (
                <p className="course-card__description">
                    {description}
                </p>
            )}

            {onViewDetails && (
                <div className="course-card__actions">
                    <Button
                        variant="secondary"
                        onClick={onViewDetails}
                    >
                        View Details
                    </Button>
                </div>
            )}

        </Card>
    );
}

export default CourseCard;