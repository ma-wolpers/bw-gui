from bw_gui.contracts.keybinding import KeyBindingDefinition, KeybindingRuntimeContext
from bw_gui.laufkern import (
    aggregate_completion,
    build_manifest,
    emit_tracking_artifact,
    evaluate_intent_routes,
    validate_step_id,
    verify_manifest,
)
from bw_gui.laufkern.models import LaufKernRoute
from bw_gui.laufkern.reason_codes import LK_RCH_TEXT_INPUT_BLOCKED


def test_manifest_build_and_validate_success():
    manifest = build_manifest(
        manifest_id="demo",
        repo_name="blattwerk",
        intents=("open", "save"),
        keybindings=(
            KeyBindingDefinition(
                binding_id="global.open",
                sequence="<Control-o>",
                intent="open",
            ),
        ),
        routes=(
            LaufKernRoute(
                route_id="route.open.shortcut",
                intent="open",
                route_type="shortcut",
                binding_id="global.open",
            ),
        ),
    )

    ok, errors = verify_manifest(manifest)
    assert ok is True
    assert errors == ()


def test_manifest_rejects_unknown_exclusion_reason():
    manifest = build_manifest(
        manifest_id="demo",
        repo_name="blattwerk",
        intents=("open",),
        keybindings=(),
        routes=(),
        exclusions={"open": "LK-NOT-VALID"},
    )

    ok, errors = verify_manifest(manifest)
    assert ok is False
    assert any("exclusion-reason-unknown" in value for value in errors)


def test_reachability_reports_text_input_blocked():
    definition = KeyBindingDefinition(
        binding_id="global.open",
        sequence="<Control-o>",
        intent="open",
        allow_when_text_input=False,
    )
    manifest = build_manifest(
        manifest_id="demo",
        repo_name="blattwerk",
        intents=("open",),
        keybindings=(definition,),
        routes=(
            LaufKernRoute(
                route_id="route.open.shortcut",
                intent="open",
                route_type="shortcut",
                binding_id="global.open",
            ),
        ),
    )

    result = evaluate_intent_routes(
        manifest=manifest,
        intent="open",
        context=KeybindingRuntimeContext(active_mode="global", text_input_focused=True),
    )
    assert result.reachable is False
    assert result.reason_code == LK_RCH_TEXT_INPUT_BLOCKED


def test_emit_tracking_artifact_and_completion_summary():
    assert validate_step_id("LK-A-ARC-001") is True

    first = emit_tracking_artifact(
        run_id="run-1",
        repo_name="blattwerk",
        step_id="LK-A-ARC-001",
        phase="A",
        state="done",
        sequence=1,
        mandatory=True,
        producer="laufkern",
    )
    second = emit_tracking_artifact(
        run_id="run-1",
        repo_name="blattwerk",
        step_id="LK-B-API-001",
        phase="B",
        state="done",
        sequence=2,
        mandatory=True,
        producer="laufkern",
    )

    summary = aggregate_completion((first, second))
    assert summary.status == "complete"
    assert summary.mandatory_steps == 2
    assert summary.completed_steps == 2


def test_aggregate_completion_detects_missing_mandatory_step():
    artifact = emit_tracking_artifact(
        run_id="run-2",
        repo_name="blattwerk",
        step_id="LK-A-ARC-001",
        phase="A",
        state="done",
        sequence=1,
        mandatory=True,
        producer="laufkern",
    )

    summary = aggregate_completion(
        (artifact,),
        mandatory_steps={"LK-A-ARC-001", "LK-B-API-001"},
    )

    assert summary.status == "non-complete"
    assert summary.mandatory_steps == 2
    assert any("LK-TRK-MISSING_MANDATORY" in blocker for blocker in summary.blockers)
