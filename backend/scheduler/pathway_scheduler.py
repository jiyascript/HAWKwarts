def prepare_pathway_options(
    unsatisfied_pathways,
    completed_codes,
    in_progress_codes
):
    """
    Prepare unfinished pathways for scheduling.

    If a pathway has already been started, require
    the remaining courses in its recommended sequence.

    If no pathway has been started, preserve the
    alternative options for later Z3 selection.
    """

    prepared_pathways = []

    satisfied_or_pending = (
        set(completed_codes) | set(in_progress_codes)
    )

    for pathway in unsatisfied_pathways:
        recommended = pathway.get("recommended_pathway")

        if recommended:
            required_courses = [
                code
                for code in recommended
                if code not in satisfied_or_pending
            ]

            prepared_pathways.append({
                "name": pathway["name"],
                "mode": "required",
                "required_courses": required_courses,
                "options": [],
                "recommended_pathway": recommended
            })

        else:
            prepared_options = [
                [
                    code
                    for code in option
                    if code not in satisfied_or_pending
                ]
                for option in pathway["options"]
            ]

            prepared_pathways.append({
                "name": pathway["name"],
                "mode": "choice",
                "required_courses": [],
                "options": prepared_options,
                "recommended_pathway": None
            })

    return prepared_pathways