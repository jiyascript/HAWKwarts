"""
HAWKwarts academic credit policy configuration.

These are initial planning defaults.
University policies and individual student restrictions
must be verified before registration.
"""

CREDIT_POLICIES = {
    "undergraduate": {
        "full_time": {
            "minimum": 12,
            "maximum": 18,
        },
        "part_time": {
            "minimum": 1,
            "maximum": 11,
        },
    },
    "graduate": {
        "full_time": {
            "minimum": 9,
            "maximum": 15,
        },
        "part_time": {
            "minimum": 1,
            "maximum": 8,
        },
    },
}


def get_credit_policy(academic_level, enrollment_status):
    """
    Return the credit range for a student's
    academic level and enrollment status.
    """

    if academic_level not in CREDIT_POLICIES:
        raise ValueError(
            f"Unsupported academic level: {academic_level}"
        )

    policies = CREDIT_POLICIES[academic_level]

    if enrollment_status not in policies:
        raise ValueError(
            f"Unsupported enrollment status: {enrollment_status}"
        )

    return policies[enrollment_status].copy()
