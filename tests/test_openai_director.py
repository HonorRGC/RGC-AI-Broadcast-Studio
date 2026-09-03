from types import SimpleNamespace

from production.openai_director import OpenAIDirector


class FakeResponses:
    def __init__(self, text):
        self.text = text
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.text)


def build_director(text):
    director = OpenAIDirector()
    responses = FakeResponses(text)
    director.client = SimpleNamespace(responses=responses)
    return director, responses


def test_incomplete_ai_sentence_falls_back_instead_of_airing_cutoff_text():
    director, _ = build_director("The number 14 is closing quickly and could")
    assignment = SimpleNamespace(headline="Battle", summary="Complete fallback.")

    commentary = director.generate_commentary(
        speaker="lead",
        assignment=assignment,
        fallback_text="Complete fallback.",
    )

    assert commentary == "Complete fallback."


def test_ai_director_allows_enough_output_room_for_complete_sentences():
    director, responses = build_director("The battle is building.")
    assignment = SimpleNamespace(headline="Battle", summary="Fallback.")

    director.generate_commentary(
        speaker="lead",
        assignment=assignment,
        fallback_text="Fallback.",
    )

    assert responses.kwargs["max_output_tokens"] == 300


def test_ai_director_runtime_toggle_uses_fallback_text():
    director, _ = build_director("The battle is building.")
    assignment = SimpleNamespace(headline="Battle", summary="Fallback.")

    director.set_enabled(False)
    commentary = director.generate_commentary(
        speaker="lead",
        assignment=assignment,
        fallback_text="Fallback.",
    )

    assert commentary == "Fallback."
