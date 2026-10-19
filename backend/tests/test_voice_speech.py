from backend.main import TTSRequest, normalize_hinglish_for_tts


def test_common_hinglish_is_normalized_for_hindi_tts():
    spoken = normalize_hinglish_for_tts("Mera laptop slow chal raha hai.")
    assert spoken == "मेरा laptop slow चल रहा है।".replace("।", ".")


def test_english_technical_terms_are_preserved():
    spoken = normalize_hinglish_for_tts("Website ka code fix kar do.")
    assert spoken == "Website का code fix कर दो."


def test_pure_english_is_not_transliterated():
    original = "The laptop is slow and the website needs a code fix."
    assert normalize_hinglish_for_tts(original) == original


def test_devanagari_hindi_is_left_unchanged():
    original = "मेरा लैपटॉप धीमा चल रहा है।"
    assert normalize_hinglish_for_tts(original) == original


def test_configured_voice_options_are_accepted():
    assert TTSRequest(text="नमस्ते", language="hi-IN").language == "hi-IN"
    assert TTSRequest(
        text="Hello", language="en-IN", voice="en-IN-PrabhatNeural"
    ).voice == "en-IN-PrabhatNeural"
