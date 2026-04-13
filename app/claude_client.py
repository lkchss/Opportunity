import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def get_recommendations(background: str, goals: str) -> str:
    """
    Send the user's background and goals to Claude and return opportunity recommendations.
    """
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": (
                    "You are an expert career and life coach. Based on the following profile, "
                    "recommend specific opportunities (graduate programs, jobs, gap year programs, etc.) "
                    "that would be a strong fit.\n\n"
                    f"Background:\n{background}\n\n"
                    f"Goals:\n{goals}\n\n"
                    "Provide 5-10 specific, actionable recommendations. For each one, include:\n"
                    "- The name of the opportunity\n"
                    "- Why it fits this person\n"
                    "- A concrete next step to pursue it"
                ),
            }
        ],
    )
    return message.content[0].text
