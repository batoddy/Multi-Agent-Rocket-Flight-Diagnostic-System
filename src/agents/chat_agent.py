import json
from pathlib import Path

from src.core.gemini_client import GeminiClient
from src.agents.coordinator_agent import CoordinatorAgent


class ChatAgent:
    """
    Conversational interface agent.

    Maintains conversation history across turns. On each message:
    - Decides whether the user is asking about a drone flight (routes to CoordinatorAgent)
    - Or asking something general (responds via Gemini directly)

    For follow-up questions ("what about 3pm?"), enriches the short message
    with previous context before passing it to CoordinatorAgent.
    """

    EXIT_COMMANDS = {"exit", "quit", "çıkış", "cikis", "bye"}
    OUTPUT_PATH = Path("outputs") / "latest_result.json"
    HISTORY_CONTEXT_LIMIT = 10
    HISTORY_CONTENT_TRUNCATE = 600

    def __init__(self):
        self.llm_client = GeminiClient()
        self.coordinator = CoordinatorAgent()
        self.history: list[dict] = []

    def is_exit_command(self, message: str) -> bool:
        return message.strip().lower() in self.EXIT_COMMANDS

    def chat(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        classification = self._classify_message(user_message)

        if classification == "NOT_FLIGHT":
            response = self._handle_general_chat(user_message)
        elif classification == "COMPLETE":
            response = self._handle_flight_query(user_message)
        else:
            response = self._ask_clarification(classification)

        self.history.append({"role": "assistant", "content": response})
        return response

    def _classify_message(self, message: str) -> str:
        """
        Returns one of: NOT_FLIGHT | COMPLETE | ASK_TIME | ASK_LOCATION

        Combines intent detection and completeness check in a single Gemini call.
        """
        prompt = f"""You are analyzing a message sent to a drone flight suitability assistant.
Classify it using the conversation history as context.

Conversation history:
{self._format_history(include_last_user=False)}

New message: {message}

Rules:
- NOT_FLIGHT   : not related to checking drone flight suitability (greeting, general question, thanks, etc.)
- COMPLETE     : flight suitability request with both a location AND a time or time-of-day mentioned
                 (e.g. "at 14:00", "tomorrow morning", "around noon", "saat 12'de")
                 If location or time were already established in history, treat them as available.
- ASK_LOCATION : flight suitability request but no location is mentioned anywhere in history or message
- ASK_TIME     : flight suitability request with a location but no time mentioned anywhere

Answer with ONLY one word: NOT_FLIGHT, COMPLETE, ASK_LOCATION, or ASK_TIME
"""
        result = self.llm_client.generate(prompt).strip().upper()
        for label in ("NOT_FLIGHT", "COMPLETE", "ASK_LOCATION", "ASK_TIME"):
            if label in result:
                return label
        return "COMPLETE"

    def _ask_clarification(self, missing: str) -> str:
        missing_descriptions = {
            "ASK_TIME": "the time they want to fly (e.g. 14:00, morning, around noon)",
            "ASK_LOCATION": "the location where they want to fly",
        }
        what = missing_descriptions.get(missing, "more details about the planned flight")

        prompt = f"""You are a drone flight suitability assistant. The user wants to check flight conditions but their request is missing information.

Conversation so far:
{self._format_history(include_last_user=True)}

Ask the user for: {what}

Keep the question short and natural. Match the language the user is writing in (Turkish or English).
Plain text only, no markdown, no emojis.
"""
        return self.llm_client.generate(prompt)

    def _handle_flight_query(self, message: str) -> str:
        enriched_query = self._enrich_with_history(message)

        result = self.coordinator.handle_user_request(enriched_query)

        self.OUTPUT_PATH.parent.mkdir(exist_ok=True)
        with open(self.OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        if result.get("final_report"):
            return result["final_report"]

        return self._format_error_response(result)

    def _handle_general_chat(self, message: str) -> str:
        prompt = f"""You are a drone flight suitability assistant. You help users check whether weather and location conditions are suitable for drone flights.

You can answer general questions too, but keep responses concise and relevant.

Conversation so far:
{self._format_history(include_last_user=False)}

User: {message}

Respond naturally. Do not use markdown formatting, emojis, or bullet lists. Plain text only.
"""
        return self.llm_client.generate(prompt)

    def _enrich_with_history(self, message: str) -> str:
        if len(self.history) <= 1:
            return message

        prompt = f"""A user is asking about drone flight suitability. Their new message may be a short follow-up that references a previous conversation.

Previous conversation:
{self._format_history(include_last_user=False)}

New message: {message}

If this is a follow-up (e.g. "what about 3pm?", "peki ya yarın?", "same location but at 15:00?"),
expand it into a complete standalone drone flight query that includes all necessary details:
location, date, time, and drone model (if mentioned earlier).

If the message is already a complete and standalone query, return it unchanged.

Return ONLY the final query text. No explanations.
"""
        return self.llm_client.generate(prompt).strip()

    def _format_history(self, include_last_user: bool = True) -> str:
        history = self.history if include_last_user else self.history[:-1]
        recent = history[-self.HISTORY_CONTEXT_LIMIT :]

        lines = []
        for entry in recent:
            role = "User" if entry["role"] == "user" else "Assistant"
            content = entry["content"]
            if len(content) > self.HISTORY_CONTENT_TRUNCATE:
                content = content[: self.HISTORY_CONTENT_TRUNCATE] + "... [truncated]"
            lines.append(f"{role}: {content}")

        return "\n".join(lines) if lines else "(no previous conversation)"

    def _format_error_response(self, result: dict) -> str:
        stage = result.get("stage", "unknown")
        error = result.get("error", "An unknown error occurred.")

        messages = {
            "location_not_found": (
                "The location could not be found. "
                "Please try again with a more specific address or landmark."
            ),
            "weather_forecast_failed": (
                "Weather forecast data could not be retrieved for that location and time. "
                "Please try again later."
            ),
        }

        return messages.get(
            stage, f"The request could not be completed ({stage}): {error}"
        )
