from config import USE_OPENAI, OPENAI_API_KEY
from commentary.generator import CommentaryGenerator
from ai.prompt_builder import PromptBuilder
from ai.openai_client import OpenAIClient


class Commentator:
    def __init__(self):
        self.generator = CommentaryGenerator()
        self.prompt_builder = PromptBuilder()

        if USE_OPENAI and OPENAI_API_KEY:
            self.ai_client = OpenAIClient(OPENAI_API_KEY)
        else:
            self.ai_client = None

    def speak(self, event, driver=None):
        if self.ai_client and driver:
            prompt = self.prompt_builder.build(event, driver)
            return self.ai_client.generate(prompt)

        return self.generator.generate(event)