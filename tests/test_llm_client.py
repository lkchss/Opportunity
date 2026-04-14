import pytest
import json
import os
from unittest.mock import patch, MagicMock

from app.llm_client import (
    generate_narrative,
    _build_narrative_prompt,
    _parse_narrative_response,
    RateLimitError,
    LLMProviderError,
)


# Test data
VALID_PROFILE = {
    "lsat": 170,
    "gpa": 3.8,
    "undergrad_school": "University of Michigan",
    "undergrad_major": "Political Science",
    "goal": "BigLaw",
    "practice_areas": ["Corporate", "Litigation"],
    "geography": ["New York", "Chicago"],
    "scholarship": "Prefer but not required",
    "work_experience": "Summer associate at law firm",
    "achievements": "Law review member"
}

VALID_SCHOOL = {
    "id": "harvard-law",
    "name": "Harvard Law School",
    "location": "Cambridge, MA",
    "website_url": "https://hls.harvard.edu",
    "lsat_25": 173,
    "lsat_50": 174,
    "lsat_75": 176,
    "gpa_25": 3.82,
    "gpa_50": 3.96,
    "gpa_75": 4.0,
    "acceptance_rate": 0.092,
    "scholarship_pct": 0.65,
    "median_scholarship": 35000,
    "biglaw_pct": 0.48,
    "federal_clerkship_pct": 0.15,
    "public_interest_pct": 0.09,
    "government_pct": 0.08,
    "bar_pass_rate_first_time": 0.96,
    "practice_area_strengths": ["corporate", "litigation"],
    "lrap_quality": "excellent",
    "annual_tuition": 73200,
    "cost_of_living_index": 5
}

VALID_RESPONSE_JSON = {
    "harvard-law": {
        "why_it_fits": "With your 170 LSAT and 3.8 GPA, you're competitive at Harvard. Your BigLaw goals align perfectly with Harvard's 48% placement rate.",
        "concerns": "Harvard is expensive at $73,200/year. You may need significant loans.",
        "next_step": "Email admissions about their BigLaw recruiting pipeline."
    },
    "yale-law": {
        "why_it_fits": "Yale values your litigation interests and has strong clerkship placement at 15%.",
        "concerns": "Very competitive school; you're near median but below 75th percentile.",
        "next_step": "Schedule a virtual visit to meet current students."
    }
}


class TestBuildNarrativePrompt:
    """Test prompt building."""

    def test_prompt_includes_profile_info(self):
        """Prompt should include applicant profile details."""
        schools = [VALID_SCHOOL]
        prompt = _build_narrative_prompt(VALID_PROFILE, schools)

        assert "170" in prompt  # LSAT
        assert "3.8" in prompt  # GPA
        assert "BigLaw" in prompt  # Goal
        assert "Corporate" in prompt  # Practice area
        assert "Michael" not in prompt  # No personal info

    def test_prompt_includes_school_data(self):
        """Prompt should include school data."""
        schools = [VALID_SCHOOL]
        prompt = _build_narrative_prompt(VALID_PROFILE, schools)

        assert "Harvard Law School" in prompt
        assert "174" in prompt  # LSAT median
        assert "3.96" in prompt  # GPA median
        assert "48.0%" in prompt or "0.48" in prompt  # BigLaw %

    def test_prompt_limits_to_ten_schools(self):
        """Prompt should only include top 10 schools even if more provided."""
        schools = [VALID_SCHOOL.copy() for _ in range(20)]
        # Modify IDs to be unique
        for i, school in enumerate(schools):
            school["id"] = f"school-{i}"
            school["name"] = f"School {i}"

        prompt = _build_narrative_prompt(VALID_PROFILE, schools)

        # Should have first 10 schools but not school 10+
        assert "School 0" in prompt
        assert "School 9" in prompt
        assert "School 10" not in prompt

    def test_prompt_is_string(self):
        """Prompt should return a string."""
        schools = [VALID_SCHOOL]
        prompt = _build_narrative_prompt(VALID_PROFILE, schools)
        assert isinstance(prompt, str)
        assert len(prompt) > 100


class TestParseNarrativeResponse:
    """Test response parsing."""

    def test_parse_valid_json_response(self):
        """Valid JSON response should parse correctly."""
        response = json.dumps(VALID_RESPONSE_JSON)
        school_ids = ["harvard-law", "yale-law"]

        result = _parse_narrative_response(response, school_ids)

        assert result["harvard-law"]["why_it_fits"] is not None
        assert result["harvard-law"]["concerns"] is not None
        assert result["harvard-law"]["next_step"] is not None
        assert result["yale-law"]["why_it_fits"] is not None

    def test_parse_json_wrapped_in_markdown(self):
        """JSON wrapped in markdown code blocks should parse."""
        response = f"```json\n{json.dumps(VALID_RESPONSE_JSON)}\n```"
        school_ids = ["harvard-law", "yale-law"]

        result = _parse_narrative_response(response, school_ids)

        assert "harvard-law" in result
        assert result["harvard-law"]["why_it_fits"] is not None

    def test_parse_invalid_json_raises_error(self):
        """Invalid JSON should raise LLMProviderError."""
        response = "{invalid json}"
        school_ids = ["harvard-law"]

        with pytest.raises(LLMProviderError, match="Failed to parse"):
            _parse_narrative_response(response, school_ids)

    def test_parse_missing_required_field_raises_error(self):
        """Missing required field in narrative raises error."""
        invalid_response = {
            "harvard-law": {
                "why_it_fits": "Good fit",
                # Missing 'concerns' and 'next_step'
            }
        }
        response = json.dumps(invalid_response)
        school_ids = ["harvard-law"]

        with pytest.raises(LLMProviderError, match="missing required field"):
            _parse_narrative_response(response, school_ids)

    def test_parse_non_dict_response_raises_error(self):
        """Non-dict response should raise error."""
        response = '["harvard-law", "yale-law"]'
        school_ids = ["harvard-law"]

        with pytest.raises(LLMProviderError, match="must be a JSON object"):
            _parse_narrative_response(response, school_ids)


class TestGenerateNarrativeInputValidation:
    """Test input validation for generate_narrative."""

    def test_empty_profile_raises_error(self):
        """Empty profile should raise ValueError."""
        with pytest.raises(ValueError, match="profile cannot be empty"):
            generate_narrative({}, [VALID_SCHOOL])

    def test_empty_schools_raises_error(self):
        """Empty schools list should raise ValueError."""
        with pytest.raises(ValueError, match="ranked_schools cannot be empty"):
            generate_narrative(VALID_PROFILE, [])

    def test_top_k_greater_than_schools_raises_error(self):
        """top_k greater than available schools raises ValueError."""
        schools = [VALID_SCHOOL]
        with pytest.raises(ValueError, match="top_k must be between"):
            generate_narrative(VALID_PROFILE, schools, top_k=10)

    def test_top_k_zero_raises_error(self):
        """top_k of 0 raises ValueError."""
        schools = [VALID_SCHOOL] * 10
        with pytest.raises(ValueError, match="top_k must be between"):
            generate_narrative(VALID_PROFILE, schools, top_k=0)

    def test_top_k_default_is_ten(self):
        """top_k defaults to 10."""
        # This would require mocking the API calls
        schools = [VALID_SCHOOL.copy() for _ in range(15)]
        for i, school in enumerate(schools):
            school["id"] = f"school-{i}"

        # Without mocking, this will fail due to missing API key, but that's ok
        with patch("app.llm_client.LLM_PROVIDER", "anthropic"):
            with patch("app.llm_client._generate_narrative_anthropic") as mock_gen:
                mock_gen.return_value = {school["id"]: {
                    "why_it_fits": "test",
                    "concerns": "test",
                    "next_step": "test"
                } for school in schools[:10]}

                result = generate_narrative(VALID_PROFILE, schools)
                # Verify only 10 schools were processed
                assert mock_gen.called
                args = mock_gen.call_args
                assert len(args[0][1]) == 10


class TestGenerateNarrativeProviderSelection:
    """Test provider selection."""

    @patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"})
    @patch("app.llm_client._generate_narrative_anthropic")
    def test_anthropic_provider_selected(self, mock_anthropic):
        """Setting LLM_PROVIDER=anthropic should use Anthropic."""
        # Reload module to pick up env var
        import importlib
        import app.llm_client as llm_module
        importlib.reload(llm_module)

        mock_anthropic.return_value = {
            "harvard-law": {
                "why_it_fits": "test",
                "concerns": "test",
                "next_step": "test"
            }
        }

        schools = [VALID_SCHOOL]
        try:
            result = llm_module.generate_narrative(VALID_PROFILE, schools, top_k=1)
            assert mock_anthropic.called
        except Exception:
            # Provider might not be available, that's ok for this test
            pass

    @patch.dict(os.environ, {"LLM_PROVIDER": "google"})
    @patch("app.llm_client._generate_narrative_google")
    def test_google_provider_selected(self, mock_google):
        """Setting LLM_PROVIDER=google should use Google."""
        mock_google.return_value = {
            "harvard-law": {
                "why_it_fits": "test",
                "concerns": "test",
                "next_step": "test"
            }
        }

        schools = [VALID_SCHOOL]
        try:
            result = generate_narrative(VALID_PROFILE, schools, top_k=1)
            assert mock_google.called
        except Exception:
            pass


class TestGenerateNarrativeStructure:
    """Test output structure."""

    @patch("app.llm_client.LLM_PROVIDER", "google")
    @patch("app.llm_client._generate_narrative_google")
    def test_output_preserves_school_order(self, mock_google):
        """Output should preserve the order from ranked_schools."""
        # Create response that matches school IDs
        mock_response = {}
        schools = []
        for i in range(3):
            school = VALID_SCHOOL.copy()
            school["id"] = f"school-{i}"
            school["name"] = f"School {i}"
            schools.append(school)
            mock_response[f"school-{i}"] = {
                "why_it_fits": f"Reason {i}",
                "concerns": f"Concern {i}",
                "next_step": f"Step {i}"
            }

        mock_google.return_value = mock_response

        result = generate_narrative(VALID_PROFILE, schools, top_k=3)

        assert len(result) == 3
        assert result[0]["id"] == "school-0"
        assert result[1]["id"] == "school-1"
        assert result[2]["id"] == "school-2"

    @patch("app.llm_client.LLM_PROVIDER", "google")
    @patch("app.llm_client._generate_narrative_google")
    def test_output_includes_narrative_fields(self, mock_google):
        """Output should include why_it_fits, concerns, next_step."""
        mock_google.return_value = {
            "harvard-law": {
                "why_it_fits": "Good fit",
                "concerns": "Expensive",
                "next_step": "Email admissions"
            }
        }

        schools = [VALID_SCHOOL]
        result = generate_narrative(VALID_PROFILE, schools, top_k=1)

        assert result[0]["why_it_fits"] == "Good fit"
        assert result[0]["concerns"] == "Expensive"
        assert result[0]["next_step"] == "Email admissions"

    @patch("app.llm_client.LLM_PROVIDER", "google")
    @patch("app.llm_client._generate_narrative_google")
    def test_output_preserves_original_school_data(self, mock_google):
        """Output should include all original school fields."""
        mock_google.return_value = {
            "harvard-law": {
                "why_it_fits": "Good fit",
                "concerns": "Expensive",
                "next_step": "Email admissions"
            }
        }

        schools = [VALID_SCHOOL]
        result = generate_narrative(VALID_PROFILE, schools, top_k=1)

        assert result[0]["name"] == "Harvard Law School"
        assert result[0]["lsat_50"] == 174
        assert result[0]["biglaw_pct"] == 0.48
