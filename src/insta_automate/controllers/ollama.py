from pathlib import Path
from textwrap import dedent

from ollama import Client
from pydantic import ValidationError

from insta_automate.models.meta import Gender, GenderPrediction
from insta_automate.vars import OLLAMA_URL, OLLAMA_VL_MODEL

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


class GenderClassifier:
    def __init__(self, model: str = OLLAMA_VL_MODEL) -> None:
        self.model = model
        self.client = Client(host=OLLAMA_URL)
        self.client.generate(model=self.model, prompt="Hi", keep_alive=-1)

    def _generate(self, prompt: str) -> None:
        response = self.client.generate(model=self.model, prompt=prompt).response
        print(response)

    def predict(self, image: str | Path) -> GenderPrediction:
        response = self.client.generate(
            model=self.model,
            system=SYSTEM_PROMPT,
            prompt="Predict",
            images=[str(image)],
            options={"temperature": 0},
            format=GenderPrediction.model_json_schema(),
        ).response
        try:
            return GenderPrediction.model_validate_json(response)
        except ValidationError:
            return GenderPrediction(result=Gender.UNDEF)
