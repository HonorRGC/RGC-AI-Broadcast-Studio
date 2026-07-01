from openai import OpenAI

from config import OPENAI_API_KEY, USE_OPENAI
from production.prompt_builder import PromptBuilder


class OpenAIDirector:
    def __init__(self, model="gpt-5.5"):
        self.model = model
        self.prompt_builder = PromptBuilder()

        if USE_OPENAI and OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            self.client = None

    def is_enabled(self):
        return self.client is not None

    def generate_commentary(
        self,
        speaker,
        assignment,
        race_state=None,
        race_knowledge=None,
        fallback_text="",
    ):
        if not self.is_enabled():
            return fallback_text

        try:
            prompt = self.prompt_builder.build_prompt(
                speaker=speaker,
                assignment=assignment,
                race_state=race_state,
                race_knowledge=race_knowledge,
            )

            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": prompt["system"],
                    },
                    {
                        "role": "user",
                        "content": prompt["user"],
                    },
                ],
                max_output_tokens=120,
            )

            commentary = response.output_text.strip()

            if not commentary:
                return fallback_text

            return commentary

        except Exception as error:
            print("OpenAI Director error:")
            print(error)
            return fallback_text