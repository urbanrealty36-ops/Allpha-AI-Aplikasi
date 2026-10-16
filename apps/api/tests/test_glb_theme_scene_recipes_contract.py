import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "3d-assets" / "acquire_glb_assets.py"
RECIPES = ROOT / "tools" / "3d-assets" / "theme_scene_recipes.json"


def test_acquisition_sources_cover_all_eight_user_supplied_repositories():
    source = SCRIPT.read_text(encoding="utf-8")
    expected = {
        "rostock/3DModels",
        "ToxSam/os3a-gallery",
        "SpectraStudios/SourceCityToolkit_glb",
        "c-frame/valid-avatars-glb",
        "KhronosGroupArchives/glTF-Sample-Models",
        "ramjigeddam/3d",
        "ToxSam/open-source-3D-assets",
        "ladybug-tools/3d-models",
    }
    found = {repo for repo in expected if f'"repo":"{repo}"' in source}
    assert found == expected


def test_scene_recipes_cover_fourteen_categories_and_composite_layouts():
    source = SCRIPT.read_text(encoding="utf-8")
    category_block = source.split("CATEGORIES = [", 1)[1].split("]", 1)[0]
    categories = {part.strip().strip('"') for part in category_block.split(",") if part.strip()}
    recipe = json.loads(RECIPES.read_text(encoding="utf-8"))
    recipe_categories = {item["key"] for item in recipe["theme_categories"]}
    assert len(categories) == 14
    assert categories == recipe_categories
    composite_keys = {item["key"] for item in recipe["composite_recipes"]}
    assert {"district-city", "creator-booth", "ai-character", "human-avatar",
            "live-stage", "ads-billboard", "universe-navigation",
            "social-feed-spatial-card"} <= composite_keys
    assert recipe["status"] == "design_mapping_only"
    assert any("license evidence" in item for item in recipe["acceptance_requirements"])
