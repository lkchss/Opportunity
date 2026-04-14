import json
import pytest
import tempfile
from pathlib import Path

from app.data_loader import (
    load_law_schools,
    DataValidationError,
    _validate_entry,
    _get_data_path,
)


# Valid school entry for testing
VALID_SCHOOL = {
    "id": "test-law",
    "name": "Test Law School",
    "location": "Test City, TS",
    "website_url": "https://test.edu",
    "lsat_25": 150,
    "lsat_50": 160,
    "lsat_75": 170,
    "gpa_25": 3.0,
    "gpa_50": 3.5,
    "gpa_75": 4.0,
    "acceptance_rate": 0.25,
    "scholarship_pct": 0.80,
    "median_scholarship": 25000,
    "biglaw_pct": 0.15,
    "federal_clerkship_pct": 0.05,
    "public_interest_pct": 0.10,
    "government_pct": 0.08,
    "bar_pass_rate_first_time": 0.85,
    "practice_area_strengths": ["corporate", "litigation"],
    "lrap_quality": "basic",
    "annual_tuition": 50000,
    "cost_of_living_index": 3,
}


class TestValidateEntry:
    """Test the _validate_entry function."""

    def test_valid_entry(self):
        """Valid entry should not raise."""
        _validate_entry(VALID_SCHOOL)

    def test_missing_required_field(self):
        """Entry missing a required field should raise DataValidationError."""
        school = VALID_SCHOOL.copy()
        del school["lsat_50"]
        with pytest.raises(DataValidationError, match="missing required fields"):
            _validate_entry(school)

    def test_missing_field_error_includes_school_id(self):
        """Error message should include the school's id."""
        school = VALID_SCHOOL.copy()
        school["id"] = "problem-school"
        del school["name"]
        with pytest.raises(DataValidationError, match="problem-school"):
            _validate_entry(school)

    def test_wrong_type_numeric_field(self):
        """Numeric field with wrong type should raise."""
        school = VALID_SCHOOL.copy()
        school["lsat_50"] = "160"  # Should be int or float
        with pytest.raises(DataValidationError, match="field 'lsat_50'"):
            _validate_entry(school)

    def test_wrong_type_string_field(self):
        """String field with wrong type should raise."""
        school = VALID_SCHOOL.copy()
        school["name"] = 123  # Should be str
        with pytest.raises(DataValidationError, match="field 'name'"):
            _validate_entry(school)

    def test_wrong_type_list_field(self):
        """List field with wrong type should raise."""
        school = VALID_SCHOOL.copy()
        school["practice_area_strengths"] = "corporate"  # Should be list
        with pytest.raises(DataValidationError, match="field 'practice_area_strengths'"):
            _validate_entry(school)

    def test_accepts_float_for_numeric_fields(self):
        """Numeric fields should accept both int and float."""
        school = VALID_SCHOOL.copy()
        school["lsat_50"] = 160.5  # float instead of int
        school["annual_tuition"] = 50000.0
        _validate_entry(school)  # Should not raise


class TestLoadLawSchools:
    """Test the load_law_schools function."""

    def test_happy_path(self, tmp_path):
        """Valid data should load successfully."""
        # Create a temporary JSON file
        data = {"schools": [VALID_SCHOOL]}
        json_file = tmp_path / "law_schools.json"
        json_file.write_text(json.dumps(data))

        # Mock _get_data_path to return our temp file
        import app.data_loader as dl
        original_get_data_path = dl._get_data_path
        dl._get_data_path = lambda: json_file

        try:
            schools = load_law_schools()
            assert len(schools) == 1
            assert schools[0]["id"] == "test-law"
            assert schools[0]["name"] == "Test Law School"
        finally:
            dl._get_data_path = original_get_data_path

    def test_invalid_json(self, tmp_path):
        """Invalid JSON should raise json.JSONDecodeError."""
        json_file = tmp_path / "law_schools.json"
        json_file.write_text("{invalid json")

        import app.data_loader as dl
        original_get_data_path = dl._get_data_path
        dl._get_data_path = lambda: json_file

        try:
            with pytest.raises(json.JSONDecodeError):
                load_law_schools()
        finally:
            dl._get_data_path = original_get_data_path

    def test_missing_file(self, tmp_path):
        """Missing data file should raise FileNotFoundError."""
        json_file = tmp_path / "missing.json"

        import app.data_loader as dl
        original_get_data_path = dl._get_data_path
        dl._get_data_path = lambda: json_file

        try:
            with pytest.raises(FileNotFoundError):
                load_law_schools()
        finally:
            dl._get_data_path = original_get_data_path

    def test_missing_schools_key(self, tmp_path):
        """JSON missing 'schools' key should raise DataValidationError."""
        json_file = tmp_path / "law_schools.json"
        json_file.write_text(json.dumps({"data": []}))

        import app.data_loader as dl
        original_get_data_path = dl._get_data_path
        dl._get_data_path = lambda: json_file

        try:
            with pytest.raises(DataValidationError, match="missing 'schools' key"):
                load_law_schools()
        finally:
            dl._get_data_path = original_get_data_path

    def test_schools_not_list(self, tmp_path):
        """'schools' value that's not a list should raise DataValidationError."""
        json_file = tmp_path / "law_schools.json"
        json_file.write_text(json.dumps({"schools": "not a list"}))

        import app.data_loader as dl
        original_get_data_path = dl._get_data_path
        dl._get_data_path = lambda: json_file

        try:
            with pytest.raises(DataValidationError, match="'schools' must be a list"):
                load_law_schools()
        finally:
            dl._get_data_path = original_get_data_path

    def test_invalid_school_entry(self, tmp_path):
        """Invalid school entry should raise DataValidationError."""
        invalid_school = VALID_SCHOOL.copy()
        del invalid_school["lsat_50"]

        json_file = tmp_path / "law_schools.json"
        json_file.write_text(json.dumps({"schools": [invalid_school]}))

        import app.data_loader as dl
        original_get_data_path = dl._get_data_path
        dl._get_data_path = lambda: json_file

        try:
            with pytest.raises(DataValidationError, match="missing required fields"):
                load_law_schools()
        finally:
            dl._get_data_path = original_get_data_path

    def test_multiple_schools(self, tmp_path):
        """Multiple valid schools should all load."""
        school1 = VALID_SCHOOL.copy()
        school1["id"] = "school-1"

        school2 = VALID_SCHOOL.copy()
        school2["id"] = "school-2"

        data = {"schools": [school1, school2]}
        json_file = tmp_path / "law_schools.json"
        json_file.write_text(json.dumps(data))

        import app.data_loader as dl
        original_get_data_path = dl._get_data_path
        dl._get_data_path = lambda: json_file

        try:
            schools = load_law_schools()
            assert len(schools) == 2
            assert schools[0]["id"] == "school-1"
            assert schools[1]["id"] == "school-2"
        finally:
            dl._get_data_path = original_get_data_path

    def test_actual_data_file_loads(self):
        """The actual law_schools.json file should load successfully."""
        schools = load_law_schools()
        assert len(schools) > 0
        assert all(isinstance(s, dict) for s in schools)
        assert all("id" in s for s in schools)


class TestIntegration:
    """Integration tests."""

    def test_data_path_exists(self):
        """The data path should point to an existing file."""
        path = _get_data_path()
        assert path.exists(), f"Expected {path} to exist"

    def test_real_data_is_valid(self):
        """The real law_schools.json file should pass validation."""
        schools = load_law_schools()
        assert len(schools) >= 50, "Expected at least 50 schools"
        # Check a few T14 schools are present
        school_ids = {s["id"] for s in schools}
        assert "harvard-law" in school_ids
        assert "yale-law" in school_ids
        assert "stanford-law" in school_ids
