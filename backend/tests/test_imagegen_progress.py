from app.imagegen_worker import _build_step_callback


def test_step_callback_reports_real_percentage_elapsed_and_rolling_eta():
    current = [10.0]
    events = []

    def clock():
        return current[0]

    callback = _build_step_callback(5, 10.0, clock=clock, emit=events.append)
    current[0] = 12.0
    returned = callback(None, 0, None, {"latents": "unchanged"})

    assert returned == {"latents": "unchanged"}
    assert events[-1]["type"] == "progress"
    assert events[-1]["step"] == 1
    assert events[-1]["total_steps"] == 5
    assert events[-1]["percent"] == 20
    assert events[-1]["elapsed_seconds"] == 2.0
    assert events[-1]["eta_seconds"] == 8.0

    current[0] = 13.5
    callback(None, 1, None, {})
    assert events[-1]["step"] == 2
    assert events[-1]["percent"] == 40
    assert events[-1]["elapsed_seconds"] == 3.5
    assert events[-1]["eta_seconds"] == 5.2


def test_step_callback_clamps_step_to_requested_total():
    current = [2.0]
    events = []
    callback = _build_step_callback(3, 1.0, clock=lambda: current[0], emit=events.append)
    callback(None, 99, None, {})
    assert events[-1]["step"] == 3
    assert events[-1]["percent"] == 100
    assert events[-1]["eta_seconds"] == 0.0


def test_streaming_image_and_vision_routes_are_registered():
    from app.main import app

    routes = {route.path for route in app.routes}
    assert "/api/images/generate/stream" in routes
    assert "/api/images/analyze" in routes
    assert "/api/images/vision-status" in routes


def test_ndjson_event_is_single_line_json_with_newline():
    from app.main import _ndjson_event

    serialized = _ndjson_event({"type": "progress", "step": 3, "label": "Generating image"})
    assert serialized.endswith("\n")
    assert serialized.count("\n") == 1
    import json
    assert json.loads(serialized) == {"type": "progress", "step": 3, "label": "Generating image"}
