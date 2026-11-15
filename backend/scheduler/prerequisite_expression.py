
import re

TOKEN_PATTERN = re.compile(
    r"\(|\)|\band\b|\bor\b|"
    r"RMTH\s+\d{2,3}\s+to\s+\d{2,3}|"
    r"[A-Z]{2,5}\s+\d{3}\s+to\s+\d{3}|"
    r"[A-Z]{2,5}\s+\d{3}",
    re.IGNORECASE
)

def parse_expression(text):
    """
    Parse course-code prerequisites with nested AND/OR logic.

    Returns a structured expression tree.
    Raises ValueError for unsupported syntax.
    """

    tokens = TOKEN_PATTERN.findall(text.strip())

    # Reject text that contains unsupported tokens.
    leftover = TOKEN_PATTERN.sub("", text)
    if leftover.strip():
        raise ValueError(
            f"Unsupported prerequisite syntax: {leftover.strip()}"
        )

    if not tokens:
        raise ValueError("Empty prerequisite expression")

    position = 0

    def parse_atom():
        nonlocal position

        if position >= len(tokens):
            raise ValueError("Unexpected end of expression")

        token = tokens[position]

        if token == "(":
            position += 1
            node = parse_or()

            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("Missing closing parenthesis")

            position += 1
            return node

        # Recognize Banner mathematics placement requirements.
        placement_match = re.fullmatch(
            r"RMTH\s+(\d{2,3})\s+to\s+(\d{2,3})",
            token,
            re.IGNORECASE
        )

        if placement_match:
            minimum = int(placement_match.group(1))
            maximum = int(placement_match.group(2))

            if minimum > maximum:
                raise ValueError(
                    f"Invalid placement range: {token}"
                )

            position += 1

            return {
                "type": "placement_requirement",
                "code": "RMTH",
                "minimum_score": minimum,
                "maximum_score": maximum
            }

        # Recognize course ranges such as HUM 200 to 299.
        range_match = re.fullmatch(
            r"([A-Z]{2,5})\s+(\d{3})\s+to\s+(\d{3})",
            token,
            re.IGNORECASE
        )

        if range_match:
            subject = range_match.group(1).upper()
            start = int(range_match.group(2))
            end = int(range_match.group(3))

            if start > end:
                raise ValueError(
                    f"Invalid course range: {token}"
                )

            position += 1

            return {
                "type": "course_range",
                "subject": subject,
                "start": start,
                "end": end
            }

        # Recognize individual courses such as COM 101.
        if re.fullmatch(
            r"[A-Z]{2,5}\s+\d{3}",
            token,
            re.IGNORECASE
        ):
            position += 1
            return {
                "type": "course",
                "code": token.upper()
            }

        raise ValueError(f"Unexpected token: {token}")

    def parse_and():
        nonlocal position

        children = [parse_atom()]

        while (
            position < len(tokens)
            and tokens[position].lower() == "and"
        ):
            position += 1
            children.append(parse_atom())

        if len(children) == 1:
            return children[0]

        return {
            "type": "AND",
            "children": children
        }

    def parse_or():
        nonlocal position

        children = [parse_and()]

        while (
            position < len(tokens)
            and tokens[position].lower() == "or"
        ):
            position += 1
            children.append(parse_and())

        if len(children) == 1:
            return children[0]

        return {
            "type": "OR",
            "children": children
        }

    result = parse_or()

    if position != len(tokens):
        raise ValueError(
            f"Unexpected remaining tokens: {tokens[position:]}"
        )

    return result
