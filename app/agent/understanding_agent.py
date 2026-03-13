import json
from typing import Any

from app.agent.understanding_schema import Understanding
from app.agent.prompts.understanding_prompt import UNDERSTANDING_SYSTEM_PROMPT


def build_understanding(llm_client: Any, conversation: str) -> Understanding:
    """
    Analyze a raw business conversation and extract structured understanding.

    Args:
        llm_client: The LLM client to use for analysis (e.g., Anthropic client)
        conversation: The raw business conversation text to analyze

    Returns:
        Understanding: A parsed Understanding object with extracted information

    Raises:
        json.JSONDecodeError: If the LLM response is not valid JSON
        ValueError: If the JSON doesn't match the Understanding schema
    """
    # Call the LLM with the system prompt and conversation
    response = llm_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        system=UNDERSTANDING_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Analyze this business conversation:\n\n{conversation}",
            }
        ],
    )

    # Extract the text response from the LLM
    response_text = response.content[0].text

    # Parse the JSON response
    try:
        understanding_dict = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Failed to parse LLM response as JSON: {e.msg}",
            response_text,
            e.pos,
        ) from e

    # Validate and convert to Understanding object
    try:
        understanding = Understanding(**understanding_dict)
    except ValueError as e:
        raise ValueError(
            f"LLM response doesn't match Understanding schema: {e}"
        ) from e

    return understanding
