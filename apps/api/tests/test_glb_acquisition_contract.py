import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ACQUISITION_SCRIPT = ROOT / "tools" / "3d-assets" / "acquire_glb_assets.py"


def _load_category_function():
    source = ast.parse(ACQUISITION_SCRIPT.read_text(encoding="utf-8"))
    wanted = [
        node for node in source.body
        if (isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "CATEGORIES" for target in node.targets))
        or (isinstance(node, ast.FunctionDef) and node.name == "category")
    ]
    namespace = {}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(ACQUISITION_SCRIPT), "exec"), namespace)
    return namespace["category"], namespace["CATEGORIES"]


def test_unknown_glb_candidates_are_not_silently_mapped_to_district():
    category, canonical = _load_category_function()
    assert "unmapped" not in canonical
    assert category("asset_001.glb", "unknown-source/repository") == "unmapped"


def test_glb_category_heuristics_remain_candidates_not_production_approval():
    category, canonical = _load_category_function()
    assert category("robot_character.glb", "source/repository") == "agent-character"
    assert category("city_district.glb", "source/repository") == "district"
    # The acquisition manifest separately marks these matches as heuristic candidates.
    script = ACQUISITION_SCRIPT.read_text(encoding="utf-8")
    assert '"category_mapping_status":"heuristic_candidate" if candidate_category in CATEGORIES else "unmapped"' in script
