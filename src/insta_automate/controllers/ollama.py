from pathlib import Path
from textwrap import dedent
from typing import TypeVar

from ollama import Client
from pydantic import BaseModel, ValidationError

from insta_automate.models.meta import (
    AccessPrediction,
    EntityAccess,
    Gender,
    GenderPrediction,
)
from insta_automate.vars import OLLAMA_URL, OLLAMA_VL_MODEL

T = TypeVar("T", bound=BaseModel)


class AiClassifier:
    SYSTEM_PROMPT = ""

    def __init__(self, model: str = OLLAMA_VL_MODEL) -> None:
        self.model = model
        self.client = Client(host=OLLAMA_URL)
        self.client.generate(model=self.model, prompt="Hi", keep_alive=-1)

    def _predict(self, image: str | Path, response_model: type[T]) -> T:
        response = self.client.generate(
            model=self.model,
            system=self.SYSTEM_PROMPT,
            prompt="Predict",
            images=[str(image)],
            options={"temperature": 0},
            format=response_model.model_json_schema(),
        ).response
        return response_model.model_validate_json(response)

    def _generate(self, prompt: str) -> None:
        response = self.client.generate(model=self.model, prompt=prompt).response
        print(response)


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

    def __init__(self, model: str = OLLAMA_VL_MODEL) -> None:
        super().__init__(model)

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

    def __init__(self, model: str = OLLAMA_VL_MODEL) -> None:
        super().__init__(model)

    def predict(self, image: str | Path) -> GenderPrediction:
        try:
            return self._predict(image, GenderPrediction)
        except ValidationError:
            return GenderPrediction(result=Gender.UNDEF)
