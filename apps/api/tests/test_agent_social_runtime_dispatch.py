from allpha_api.tool_registry import get_tool, validate_tool_input


def test_social_tools_are_registered_as_approval_bound_side_effects():
    expected = {
        "social.comment": "Publish approved Social comment",
        "social.reply": "Publish approved Social reply",
        "social.story_reply": "Send approved Story reply",
    }
    for key, name in expected.items():
        definition = get_tool(key)
        assert definition.name == name
        assert definition.execution_class == "side_effecting"
        assert definition.risk_level == "high"
        validate_tool_input(key, {"approval_id": "12345678-1234-1234-1234-123456789012"})
