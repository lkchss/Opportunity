import os
import json
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Provider selection
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "google").lower()


class RateLimitError(Exception):
    """Raised when LLM provider rate limits the request."""
    pass


class LLMProviderError(Exception):
    """Raised when LLM provider encounters an error."""
    pass


def _import_anthropic():
    """Lazy import Anthropic client."""
    try:
        import anthropic
        return anthropic
    except ImportError:
        raise ImportError("anthropic package required for Anthropic provider. Install with: pip install anthropic")


def _import_google():
    """Lazy import Google Generative AI client."""
    try:
        import google.generativeai as genai
        return genai
    except ImportError:
        raise ImportError("google-generativeai package required for Google provider. Install with: pip install google-generativeai")


def _build_narrative_prompt(profile: dict, schools: list[dict]) -> str:
    """
    Build the prompt for generating law school narratives.

    Args:
        profile: User's profile dict with LSAT, GPA, goals, etc.
        schools: List of top schools (already ranked by algorithm)

    Returns:
        Formatted prompt string
    """
    # Format user profile
    profile_summary = f"""
APPLICANT PROFILE:
- LSAT Score: {profile.get('lsat', 'Not yet taken')}
- GPA: {profile.get('gpa', 'N/A')}
- Undergraduate School: {profile.get('undergrad_school', 'N/A')}
- Major: {profile.get('undergrad_major', 'N/A')}
- Primary Goal: {profile.get('goal', 'N/A')}
- Practice Area Interests: {', '.join(profile.get('practice_areas', [])) if profile.get('practice_areas') else 'N/A'}
- Geographic Preferences: {', '.join(profile.get('geography', [])) if profile.get('geography') else 'Flexible'}
- Scholarship Importance: {profile.get('scholarship', 'N/A')}
- Work Experience: {profile.get('work_experience', 'None provided')}
- Notable Achievements: {profile.get('achievements', 'None provided')}
"""

    # Format schools data
    schools_summary = "\n\nTOP SCHOOLS (ranked by algorithm fit):\n"
    for i, school in enumerate(schools[:10], 1):
        schools_summary += f"""
{i}. {school['name']} (ID: {school['id']})
   Location: {school['location']}
   LSAT Median: {school['lsat_50']} | GPA Median: {school['gpa_50']} | Acceptance: {school['acceptance_rate']*100:.1f}%
   BigLaw: {school['biglaw_pct']*100:.1f}% | Federal Clerkships: {school['federal_clerkship_pct']*100:.1f}% | Public Interest: {school['public_interest_pct']*100:.1f}%
   Bar Pass Rate: {school['bar_pass_rate_first_time']*100:.1f}% | Strengths: {', '.join(school['practice_area_strengths'][:3])}
   Scholarship %: {school['scholarship_pct']*100:.0f}% | Median Scholarship: ${school.get('median_scholarship', 0):,.0f}
"""

    prompt = f"""You are an expert law school admissions advisor. For the applicant profile below,
generate personalized narratives for the top 10 law schools they've been matched with.

{profile_summary}
{schools_summary}

For EACH of the 10 schools above, generate a JSON object with these fields:
- "id": the school ID
- "why_it_fits": 2-3 sentences explaining why this school is a good fit, tying the applicant's goals/interests to concrete school data (e.g., bar pass rate, clerkship placement, practice area strength)
- "concerns": honest concerns specific to this applicant at this school (e.g., "Your LSAT is below median" or "High tuition may require substantial loans given cost of living")
- "next_step": one specific, concrete action they should take (e.g., "Schedule a virtual chat with admissions about their Public Interest Scholar program" or "Contact the career services office about BigLaw recruiting")

IMPORTANT:
- Do NOT re-rank the schools. Preserve the algorithm's ranking.
- Be specific and personalized to this applicant's profile.
- Reference actual school data when possible.
- Be honest about concerns—don't sugarcoat.
- next_step should be something they can do in the next week.

Output the narratives as a JSON object where keys are school IDs and values are the narrative objects.
Example format:
{{"harvard-law": {{"why_it_fits": "...", "concerns": "...", "next_step": "..."}}, "yale-law": {{...}}}}

Generate narratives for all 10 schools now:"""

    return prompt


def _parse_narrative_response(response_text: str, school_ids: list[str]) -> dict:
    """
    Parse the LLM's JSON response into structured narratives.

    Args:
        response_text: Raw text response from LLM
        school_ids: List of school IDs for validation

    Returns:
        Dict of narratives keyed by school ID
    """
    # Extract JSON from response (LLM might wrap it in markdown or other text)
    json_str = response_text

    # Try to extract JSON if wrapped in markdown
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        if end > start:
            json_str = response_text[start:end]
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        if end > start:
            json_str = response_text[start:end]

    try:
        narratives = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise LLMProviderError(f"Failed to parse LLM response as JSON: {e}")

    # Validate all required schools have narratives
    if not isinstance(narratives, dict):
        raise LLMProviderError("Response must be a JSON object with school IDs as keys")

    # Ensure all schools have required fields
    for school_id in school_ids:
        if school_id in narratives:
            narrative = narratives[school_id]
            for field in ["why_it_fits", "concerns", "next_step"]:
                if field not in narrative:
                    raise LLMProviderError(
                        f"School '{school_id}' missing required field: '{field}'"
                    )

    return narratives


def _generate_narrative_anthropic(profile: dict, ranked_schools: list[dict]) -> dict:
    """Generate narratives using Claude Haiku."""
    anthropic = _import_anthropic()

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = _build_narrative_prompt(profile, ranked_schools)
    school_ids = [s["id"] for s in ranked_schools[:10]]

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        response_text = message.content[0].text
    except anthropic.RateLimitError as e:
        raise RateLimitError(
            "Claude API rate limited. Please try again in a few moments."
        ) from e
    except anthropic.APIError as e:
        if "rate" in str(e).lower():
            raise RateLimitError(
                "Claude API rate limited. Please try again in a few moments."
            ) from e
        raise LLMProviderError(f"Claude API error: {e}") from e

    return _parse_narrative_response(response_text, school_ids)


def _generate_narrative_google(profile: dict, ranked_schools: list[dict]) -> dict:
    """Generate narratives using Google Gemini Flash."""
    genai = _import_google()

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise LLMProviderError(
            "GOOGLE_API_KEY environment variable not set. Please add it to .env"
        )

    genai.configure(api_key=api_key)
    prompt = _build_narrative_prompt(profile, ranked_schools)
    school_ids = [s["id"] for s in ranked_schools[:10]]

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt, generation_config={"max_output_tokens": 4096})
        response_text = response.text
    except Exception as e:
        error_str = str(e)
        if "rate" in error_str.lower() or "quota" in error_str.lower():
            raise RateLimitError(
                "Google API rate limited. Please try again in a few moments."
            ) from e
        if "API key" in error_str or "authentication" in error_str.lower():
            raise LLMProviderError(
                "Invalid GOOGLE_API_KEY. Please check your .env file."
            ) from e
        raise LLMProviderError(f"Google API error: {e}") from e

    return _parse_narrative_response(response_text, school_ids)


def generate_narrative(
    profile: dict,
    ranked_schools: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """
    Generate personalized narratives for the top law schools.

    Args:
        profile: User profile dict with LSAT, GPA, goals, practice areas, etc.
        ranked_schools: List of schools ranked by the matching algorithm (should be top ~20)
        top_k: Number of schools to generate narratives for (default 10)

    Returns:
        List of school dicts with added narrative fields:
            - why_it_fits: 2-3 sentences on fit
            - concerns: honest concerns
            - next_step: concrete next action

    Raises:
        RateLimitError: If LLM provider rate limits
        LLMProviderError: For other LLM errors
    """
    # Validate inputs
    if not profile:
        raise ValueError("profile cannot be empty")
    if not ranked_schools:
        raise ValueError("ranked_schools cannot be empty")
    if top_k < 1 or top_k > len(ranked_schools):
        raise ValueError(f"top_k must be between 1 and {len(ranked_schools)}")

    # Take only top K schools
    schools_to_process = ranked_schools[:top_k]

    # Generate narratives using selected provider
    if LLM_PROVIDER == "anthropic":
        narratives = _generate_narrative_anthropic(profile, schools_to_process)
    elif LLM_PROVIDER == "google":
        narratives = _generate_narrative_google(profile, schools_to_process)
    else:
        raise LLMProviderError(
            f"Unknown LLM_PROVIDER: {LLM_PROVIDER}. Must be 'anthropic' or 'google'"
        )

    # Augment schools with narratives, preserving order
    result = []
    for school in schools_to_process:
        school_id = school["id"]
        if school_id in narratives:
            # Add narrative fields to school
            school_with_narrative = school.copy()
            school_with_narrative.update(narratives[school_id])
            result.append(school_with_narrative)
        else:
            # School didn't get a narrative (shouldn't happen, but handle gracefully)
            school_with_narrative = school.copy()
            school_with_narrative["why_it_fits"] = "Unable to generate narrative"
            school_with_narrative["concerns"] = "Unable to generate narrative"
            school_with_narrative["next_step"] = "Contact school directly"
            result.append(school_with_narrative)

    return result
