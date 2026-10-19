import unittest

from backend.main import TTSRequest, normalize_hinglish_for_tts


class VoiceSpeechTests(unittest.TestCase):
    def test_common_hinglish_is_normalized_for_hindi_tts(self):
        spoken = normalize_hinglish_for_tts("Mera laptop slow chal raha hai.")
        self.assertEqual(spoken, "मेरा laptop slow चल रहा है.")

    def test_english_technical_terms_are_preserved(self):
        spoken = normalize_hinglish_for_tts("Website ka code fix kar do.")
        self.assertEqual(spoken, "Website का code fix कर दो.")

    def test_pure_english_is_not_transliterated(self):
        original = "The laptop is slow and the website needs a code fix."
        self.assertEqual(normalize_hinglish_for_tts(original), original)

    def test_devanagari_hindi_is_left_unchanged(self):
        original = "मेरा लैपटॉप धीमा चल रहा है।"
        self.assertEqual(normalize_hinglish_for_tts(original), original)

    def test_configured_voice_options_are_accepted(self):
        self.assertEqual(TTSRequest(text="नमस्ते", language="hi-IN").language, "hi-IN")
        self.assertEqual(
            TTSRequest(text="Hello", language="en-IN", voice="en-IN-PrabhatNeural").voice,
            "en-IN-PrabhatNeural",
        )


if __name__ == "__main__":
    unittest.main()
