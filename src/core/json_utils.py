import json


def parse_json_response(raw_response: str, source: str = "LLM") -> dict:
    cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(f"{source} returned invalid JSON:\n{raw_response}") from error
