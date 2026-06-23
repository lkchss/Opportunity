"""Generate search queries from user context."""
from __future__ import annotations

CATEGORY_TEMPLATES: dict[str, list[str]] = {
    "Jobs": [
        "{role} jobs {location} {year}",
        "{role} hiring {location}",
        "{role} entry level jobs",
        "companies hiring {role} {year}",
    ],
    "Internships": [
        "{role} internship {year}",
        "{role} summer internship {location}",
        "{role} internship program apply {year}",
    ],
    "Graduate school": [
        "{field} graduate programs {year} apply",
        "best {field} master's programs",
        "{field} PhD programs {year} admissions",
        "{field} graduate school no GRE {year}",
    ],
    "Fellowships / Scholarships": [
        "{field} fellowship {year} apply",
        "{background} scholarship {year}",
        "competitive fellowships {field} {year}",
        "fully funded {field} fellowship {year}",
    ],
    "Gap year programs": [
        "gap year programs {year} apply",
        "structured gap year {field}",
        "gap year fellowship {year}",
        "gap year service programs {year}",
    ],
    "Travel / Volunteer": [
        "volunteer abroad programs {field} {year}",
        "paid volunteer programs {year}",
        "{field} volunteer opportunity abroad {year}",
        "travel fellowship {field} {year}",
    ],
}


def build_queries(
    category: str,
    role: str = "",
    field: str = "",
    location: str = "",
    background: str = "",
    year: int = 2025,
) -> list[str]:
    templates = CATEGORY_TEMPLATES.get(category, ["{field} opportunity {year}"])
    queries: list[str] = []
    for t in templates:
        q = t.format(
            role=role or field,
            field=field or role,
            location=location or "USA",
            background=background,
            year=year,
        ).strip()
        queries.append(q)
    return queries
