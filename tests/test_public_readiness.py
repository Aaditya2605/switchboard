from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_launch_docs_and_ci_exist():
    expected = [
        ROOT / ".github" / "workflows" / "ci.yml",
        ROOT / "docs" / "DEMO.md",
        ROOT / "docs" / "PUBLIC_LAUNCH_CHECKLIST.md",
        ROOT / "docs" / "WORKFLOWS.md",
        ROOT / "docs" / "SECURITY.md",
    ]

    for path in expected:
        assert path.exists(), f"missing {path.relative_to(ROOT)}"


def test_readme_explains_public_value_and_demo_flow():
    readme = (ROOT / "README.md").read_text()

    for phrase in [
        "local control plane for AI coding agents",
        "Quick demo",
        "Built-in workflow presets",
        "Public launch checklist",
        "uv tool install",
    ]:
        assert phrase in readme


def test_ci_runs_pytest_on_supported_python_versions():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

    assert "pytest -q" in ci
    assert "3.11" in ci
    assert "3.12" in ci
