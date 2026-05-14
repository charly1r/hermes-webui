import sys
import types
from datetime import date


def _install_fake_skill_tool(monkeypatch):
    def _parse_frontmatter(content):
        if not content.startswith("---"):
            return {}, content
        try:
            _start, frontmatter, body = content.split("---", 2)
        except ValueError:
            return {}, content
        parsed = {}
        for line in frontmatter.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            parsed[key.strip()] = value.strip().strip('"')
        return parsed, body

    tools_pkg = types.ModuleType("tools")
    skills_tool = types.ModuleType("tools.skills_tool")
    skills_tool._EXCLUDED_SKILL_DIRS = {".git", "__pycache__"}
    skills_tool._parse_frontmatter = _parse_frontmatter
    monkeypatch.setitem(sys.modules, "tools", tools_pkg)
    monkeypatch.setitem(sys.modules, "tools.skills_tool", skills_tool)


def test_find_skill_in_dir_recurses_and_matches_frontmatter_name(tmp_path, monkeypatch):
    _install_fake_skill_tool(monkeypatch)
    from api.routes import _find_skill_in_dir

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "automation" / "vbs-wsl-launch"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: vbs-wsl-launch\ndescription: Launch VBS from WSL.\n---\n\n# Launch\n",
        encoding="utf-8",
    )

    found_dir, found_md = _find_skill_in_dir("vbs-wsl-launch.md", skills_dir)

    assert found_dir == skill_dir
    assert found_md == skill_md


def test_find_skill_in_dir_prefers_frontmatter_over_directory_name(tmp_path, monkeypatch):
    _install_fake_skill_tool(monkeypatch)
    from api.routes import _find_skill_in_dir

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "automation" / "launcher"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: vbs-wsl-launch\ndescription: Launch VBS from WSL.\n---\n\n# Launch\n",
        encoding="utf-8",
    )

    found_dir, found_md = _find_skill_in_dir("vbs-wsl-launch", skills_dir)

    assert found_dir == skill_dir
    assert found_md == skill_md


def test_skill_view_from_active_dir_reads_resolved_skill_content(tmp_path, monkeypatch):
    _install_fake_skill_tool(monkeypatch)
    import api.routes as routes

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "creative" / "comfyui"
    (skill_dir / "references").mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: comfyui\ndescription: Generate images with ComfyUI.\n---\n\n# ComfyUI\n\nRun workflows.\n",
        encoding="utf-8",
    )
    (skill_dir / "references" / "official-cli.md").write_text("cli notes\n", encoding="utf-8")
    monkeypatch.setattr(routes, "_active_skills_dir", lambda: skills_dir)

    data = routes._skill_view_from_active_dir("comfyui")

    assert data["name"] == "comfyui"
    assert data["description"] == "Generate images with ComfyUI."
    assert data["content"] == skill_md.read_text(encoding="utf-8")
    assert data["linked_files"] == {"references": ["references/official-cli.md"]}


def test_skill_view_frontmatter_is_json_serializable(tmp_path, monkeypatch):
    _install_fake_skill_tool(monkeypatch)
    import api.routes as routes

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "automation" / "vbs-wsl-launch"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: vbs-wsl-launch\ndescription: Launch from WSL.\ncreated: 2024-10-27\n---\n\n# Launch\n",
        encoding="utf-8",
    )

    def parse_with_date(_content):
        return {
            "name": "vbs-wsl-launch",
            "description": "Launch from WSL.",
            "created": date(2024, 10, 27),
        }, "# Launch\n"

    sys.modules["tools.skills_tool"]._parse_frontmatter = parse_with_date
    monkeypatch.setattr(routes, "_active_skills_dir", lambda: skills_dir)

    data = routes._skill_view_from_active_dir("vbs-wsl-launch")

    assert data["frontmatter"]["created"] == "2024-10-27"


def test_ensure_skill_frontmatter_prepends_required_yaml():
    from api.routes import _ensure_skill_frontmatter

    content = "# VBS WSL Launch\n\nOpen Windows launchers from WSL."

    saved = _ensure_skill_frontmatter("vbs-wsl-launch", content)

    assert saved.startswith(
        '---\nname: "vbs-wsl-launch"\ndescription: "Open Windows launchers from WSL."\n---\n\n'
    )
    assert saved.endswith(content)


def test_normalize_local_path_accepts_windows_and_wsl_paths():
    from api.routes import _normalize_local_path

    assert str(_normalize_local_path(r"C:\Users\charl\.hermes\skills")) == "/mnt/c/Users/charl/.hermes/skills"
    assert str(_normalize_local_path(r"\\wsl$\Ubuntu\home\charl\.hermes\skills")) == "/home/charl/.hermes/skills"
