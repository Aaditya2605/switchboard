from switchboard.presets import PRESET_WORKFLOWS, workflows_for_profile


def test_workflow_presets_include_high_value_agent_operations():
    names = {workflow.name for workflow in PRESET_WORKFLOWS}

    assert {
        "code-review",
        "bugfix-loop",
        "feature-build",
        "launch-audit",
        "daily-triage",
    }.issubset(names)


def test_workflows_for_profile_filters_launch_and_daily_sets():
    launch_names = {workflow.name for workflow in workflows_for_profile("launch")}
    daily_names = {workflow.name for workflow in workflows_for_profile("daily")}

    assert "launch-audit" in launch_names
    assert "code-review" in launch_names
    assert "daily-triage" in daily_names
    assert "launch-audit" not in daily_names
