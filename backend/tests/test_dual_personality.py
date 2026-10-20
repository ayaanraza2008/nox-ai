import unittest
from pydantic import ValidationError

from backend.main import (
    ChatRequest,
    SharedChatMessage,
    TTSRequest,
    build_chat_messages,
    build_nox_system_prompt,
    default_tts_voice,
)


class DualPersonalityTests(unittest.TestCase):
    def test_nox_and_lumi_have_distinct_system_identities(self):
        nox = build_nox_system_prompt("auto", "nox")
        lumi = build_nox_system_prompt("auto", "lumi")
        self.assertIn("You are NOX", nox)
        self.assertIn("male-voiced", nox)
        self.assertIn("You are LUMI", lumi)
        self.assertIn("female-voiced", lumi)
        self.assertIn("Hindi, Urdu, English, and Hinglish", nox)
        self.assertIn("Hindi, Urdu, English, and Hinglish", lumi)

    def test_chat_payload_defaults_to_nox_and_accepts_lumi(self):
        self.assertEqual(ChatRequest(message="Hello").personality, "nox")
        self.assertEqual(ChatRequest(message="Hello", personality="lumi").personality, "lumi")
        with self.assertRaises(ValidationError):
            ChatRequest(message="Hello", personality="other")

    def test_selected_personality_reaches_system_message(self):
        messages = build_chat_messages(
            "Namaste", "hinglish",
            [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello", "personality": "nox"}],
            personality="lumi",
        )
        self.assertIn("You are LUMI", messages[0]["content"])
        self.assertEqual(messages[-1], {"role": "user", "content": "Namaste"})

    def test_voice_profiles_use_existing_supported_voice_ids(self):
        self.assertEqual(default_tts_voice("nox", "hi-IN"), "hi-IN-MadhurNeural")
        self.assertEqual(default_tts_voice("lumi", "hi-IN"), "hi-IN-SwaraNeural")
        self.assertEqual(default_tts_voice("nox", "en-IN"), "en-IN-PrabhatNeural")
        self.assertEqual(default_tts_voice("lumi", "en-IN"), "en-IN-NeerjaNeural")
        # The configured voice set only has one Urdu voice, so both profiles fall back to it.
        self.assertEqual(default_tts_voice("lumi", "ur-PK"), "ur-PK-AsadNeural")

    def test_voice_pitch_is_bounded(self):
        self.assertEqual(TTSRequest(text="Hello", personality="lumi", pitch=3).pitch, 3)
        with self.assertRaises(ValidationError):
            TTSRequest(text="Hello", pitch=20)

    def test_conversation_history_can_preserve_personality_metadata(self):
        lumi_message = SharedChatMessage(role="assistant", content="Hello!", personality="lumi")
        nox_message = SharedChatMessage(role="assistant", content="Ready.", personality="nox")
        self.assertEqual(lumi_message.personality, "lumi")
        self.assertEqual(nox_message.personality, "nox")


if __name__ == "__main__":
    unittest.main()
