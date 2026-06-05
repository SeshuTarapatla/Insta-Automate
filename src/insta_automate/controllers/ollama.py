import base64
from pathlib import Path
from textwrap import dedent
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from insta_automate.models.meta import (
    AccessPrediction,
    EntityAccess,
    Gender,
    GenderPrediction,
)
from insta_automate.vars import OLLAMA_VL_MODEL, VL_SERVER_URL

T = TypeVar("T", bound=BaseModel)


class AiClassifier:
    """Classifies an image via a llama-server (OpenAI-compatible) endpoint.

    The vision model is served by ``scripts/start_vl_server.py`` rather than
    Ollama, so we control ``--image-min-tokens`` (Ollama hardcodes 1024 for
    qwen3-vl, forcing slow ~1067-token CPU vision encodes).
    """

    SYSTEM_PROMPT = ""

    def __init__(self, model: str = OLLAMA_VL_MODEL) -> None:
        self.model = model
        self.client = httpx.Client(base_url=VL_SERVER_URL, timeout=120)

    def _predict(self, image: str | Path, response_model: type[T]) -> T:
        b64 = base64.b64encode(Path(image).read_bytes()).decode()
        response = self.client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Predict"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                            },
                        ],
                    },
                ],
                "temperature": 0,
                "max_tokens": 20,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "schema": response_model.model_json_schema(),
                        "strict": True,
                    },
                },
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return response_model.model_validate_json(content)


class AccessClassifier(AiClassifier):
    SYSTEM_PROMPT = dedent("""
    You are a public/private classifier. You wil receive an image containing a profile picture (dp) with user id (bold white text position top and always present) & username (white text, position below user id, sometimes absent).

    Your task:
    - Look at the image and classify the image as public or private
    - Start with default of private
    - If any of the below conditions pass then mark it as public

    Conditions:
    - If there is a pink story ring around the dp
    - If there is a blue tick in the user id

    Rules:
    - Don't confuse with blue emojis. Emojis will only be present in username never userid.
    - Output ONLY valid JSON, nothing else
    - No explanation, no thinking, no extra text
    - Always output exactly one of these two responses:
    {"result": "public"}
    {"result": "private"}
    """).strip()

    def predict(self, image: str | Path) -> AccessPrediction:
        try:
            return self._predict(image, AccessPrediction)
        except ValidationError:
            return AccessPrediction(result=EntityAccess.UNDEF)


class GenderClassifier(AiClassifier):
    SYSTEM_PROMPT = dedent("""
    You are a gender classifier. You will receive an image containing a profile picture (dp) and a username/ID.

    Your task:
    - Look at the profile picture (dp) in the image
    - Predict the gender of the person shown based on visual appearance cues (face, hair, features)
    - If the dp is an avatar, cartoon, or animal, infer gender from the username text as a fallback
    - If completely uncertain, make your best guess — never refuse

    Rules:
    - Output ONLY valid JSON, nothing else
    - No explanation, no thinking, no extra text
    - Always output exactly one of these two responses:
    {"result": "male"}
    {"result": "female"}
    """).strip()

    def predict(self, image: str | Path) -> GenderPrediction:
        try:
            return self._predict(image, GenderPrediction)
        except ValidationError:
            return GenderPrediction(result=Gender.UNDEF)
