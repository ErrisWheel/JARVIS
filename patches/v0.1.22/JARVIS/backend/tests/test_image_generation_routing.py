from app.main import ImageGenerateRequest, IMAGE_FILENAME_RE, IMAGE_SVG_FILENAME_RE


def test_long_educational_poster_prompt_is_accepted_by_api_schema():
    prompt = ("Create a highly detailed educational poster about elements. " + "Required content and visual explanations. " * 70)
    assert len(prompt) > 2400
    request = ImageGenerateRequest(prompt=prompt, conversation_id="main", poster=True)
    assert request.poster is True
    assert len(request.prompt) > 2400


def test_generated_svg_filename_is_restricted_to_a_local_uuid_name():
    assert IMAGE_SVG_FILENAME_RE.fullmatch("0123456789abcdef0123456789abcdef.svg")
    assert not IMAGE_SVG_FILENAME_RE.fullmatch("../../secret.svg")
    assert IMAGE_FILENAME_RE.fullmatch("0123456789abcdef0123456789abcdef.png")


def test_poster_request_accepts_distinct_redesign_variants():
    prompt = "REDESIGN AN EDUCATIONAL POSTER from the original brief."
    assert ImageGenerateRequest(prompt=prompt, poster=True, design_variant="timeline").design_variant == "timeline"
    assert ImageGenerateRequest(prompt=prompt, poster=True, design_variant="orbit").design_variant == "orbit"
    assert ImageGenerateRequest(prompt=prompt, poster=True).design_variant == "cards"
