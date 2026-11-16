from app.model_team import (
    add_peer_review,
    build_reviewer_messages,
    resolve_model_team,
    should_use_peer_review,
)


def test_default_team_selects_qwen35_lead_and_qwen3_reviewer():
    team = resolve_model_team([
        "qwen3.5:9b", "qwen2.5vl:7b", "qwen3:8b"
    ])
    assert team.primary == "qwen3.5:9b"
    assert team.reviewer == "qwen3:8b"
    assert "qwen2.5vl:7b" in team.installed


def test_requested_model_is_respected_and_reviewer_is_distinct():
    team = resolve_model_team(["qwen3.5:9b", "qwen3:8b"], requested_primary="qwen3:8b")
    assert team.primary == "qwen3:8b"
    assert team.reviewer == "qwen3.5:9b"


def test_vision_model_is_not_selected_for_text_chat():
    team = resolve_model_team(["qwen2.5vl:7b", "qwen3.5:9b"], requested_primary="qwen2.5vl:7b")
    assert team.primary == "qwen3.5:9b"
    assert team.reviewer is None


def test_single_text_model_falls_back_to_single_member_team():
    team = resolve_model_team(["qwen3.5:9b", "qwen2.5vl:7b"])
    assert team.primary == "qwen3.5:9b"
    assert team.reviewer is None


def test_acknowledgements_skip_review_but_real_requests_use_it():
    assert should_use_peer_review("Thanks, Jarvis!") is False
    assert should_use_peer_review("Can you explain how microservices communicate?") is True


def test_review_is_inserted_before_current_user_message():
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "prior answer"},
        {"role": "user", "content": "current task"},
    ]
    reviewer = build_reviewer_messages(messages)
    assert reviewer[-1]["role"] == "user"
    assert "current task" in reviewer[-1]["content"]
    combined = add_peer_review(messages, "Check edge cases.", "qwen3:8b")
    assert combined[-1]["content"] == "current task"
    assert combined[-2]["role"] == "system"
    assert "qwen3:8b" in combined[-2]["content"]


def test_gpu_scheduler_is_shared_by_text_vision_and_image_generation():
    import app.main as main

    assert main.LOCAL_INFERENCE_LOCK is main.IMAGE_GENERATION_LOCK
    routes = {route.path for route in main.app.routes}
    assert "/api/model-team" in routes
