import json
from pathlib import Path
from typing import Optional


# Schema definition for law school entries
REQUIRED_FIELDS = {
    # Basic info
    "id": str,
    "name": str,
    "location": str,
    "website_url": str,
    # ABA 509 admissions data
    "lsat_25": (int, float),
    "lsat_50": (int, float),
    "lsat_75": (int, float),
    "gpa_25": (int, float),
    "gpa_50": (int, float),
    "gpa_75": (int, float),
    "acceptance_rate": (int, float),
    "scholarship_pct": (int, float),
    "median_scholarship": (int, float),
    # NALP / ABA employment data
    "biglaw_pct": (int, float),
    "federal_clerkship_pct": (int, float),
    "public_interest_pct": (int, float),
    "government_pct": (int, float),
    "bar_pass_rate_first_time": (int, float),
    # Programmatic strengths
    "practice_area_strengths": list,
    "lrap_quality": str,
    # Cost
    "annual_tuition": (int, float),
    "cost_of_living_index": (int, float),
}


class DataValidationError(Exception):
    """Raised when law school data fails validation."""
    pass


def _get_data_path() -> Path:
    """Get the path to law_schools.json relative to this module."""
    return Path(__file__).parent / "data" / "law_schools.json"


def _validate_entry(entry: dict) -> None:
    """
    Validate a single law school entry has all required fields and correct types.

    Args:
        entry: The law school entry to validate

    Raises:
        DataValidationError: If validation fails
    """
    school_id = entry.get("id", "<unknown>")

    # Check all required fields are present
    missing_fields = [field for field in REQUIRED_FIELDS if field not in entry]
    if missing_fields:
        raise DataValidationError(
            f"School '{school_id}': missing required fields: {', '.join(missing_fields)}"
        )

    # Validate each field type
    for field, expected_type in REQUIRED_FIELDS.items():
        value = entry[field]

        if isinstance(expected_type, tuple):
            # Allow multiple types (e.g., int or float)
            if not isinstance(value, expected_type):
                raise DataValidationError(
                    f"School '{school_id}': field '{field}' has type {type(value).__name__}, "
                    f"expected {' or '.join(t.__name__ for t in expected_type)}"
                )
        else:
            # Single type check
            if not isinstance(value, expected_type):
                raise DataValidationError(
                    f"School '{school_id}': field '{field}' has type {type(value).__name__}, "
                    f"expected {expected_type.__name__}"
                )


def load_law_schools() -> list[dict]:
    """
    Load and validate law schools from law_schools.json.

    Returns:
        List of validated law school dictionaries

    Raises:
        DataValidationError: If any entry fails validation
        FileNotFoundError: If the data file doesn't exist
        json.JSONDecodeError: If the JSON is malformed
    """
    data_path = _get_data_path()

    if not data_path.exists():
        raise FileNotFoundError(f"Law schools data file not found at {data_path}")

    # Load JSON
    try:
        with open(data_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in {data_path}: {e.msg}",
            e.doc,
            e.pos,
        )

    # Extract schools list
    if "schools" not in data:
        raise DataValidationError("Data file missing 'schools' key")

    schools = data["schools"]
    if not isinstance(schools, list):
        raise DataValidationError("'schools' must be a list")

    # Validate each school
    for school in schools:
        if not isinstance(school, dict):
            raise DataValidationError("Each school entry must be a dictionary")
        _validate_entry(school)

    return schools
