from src.constants.app_constants import AdaptiveCardConst


def get_data_source_settings(
    choices: list,
    selected_options: dict,
    analysis_mode: bool = False,
    web_search: bool = False,
) -> dict:
    """Create adaptive card for data source settings.

    Args:
        choices (list): List of data source choices
        selected_options (dict): Currently selected options
        analysis_mode (bool): Whether analysis mode is enabled
        web_search (bool): Whether web search is enabled

    Returns:
        dict: Adaptive card for data source settings

    """
    # Separate choices into common and user collections
    common_collections = [choice for choice in choices if choice["value"]["user_id"] is None]
    user_collections = [choice for choice in choices if choice["value"]["user_id"] is not None]

    # Convert complex objects to strings for the choices
    formatted_common_collections = [
        {"title": choice["title"], "value": choice["value"]["source_name"]} for choice in common_collections
    ]
    formatted_user_collections = [
        {"title": choice["title"], "value": choice["value"]["source_name"]} for choice in user_collections
    ]

    return {
        AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_5,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Select RAG data sources:",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": AdaptiveCardConst.CONTAINER,
                "style": "emphasis",
                "items": [
                    {
                        "type": AdaptiveCardConst.TEXT_BLOCK,
                        "text": "Common Collections",
                        "weight": "Bolder",
                        "size": "Medium",
                    },
                    {
                        "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                        "id": "commonOptions",
                        "style": "expanded",
                        "isMultiSelect": True,
                        "choices": formatted_common_collections,
                        "value": ",".join(
                            [
                                c["value"]
                                for c in formatted_common_collections
                                if c["title"] in selected_options["common"]
                            ],
                        ),
                    },
                ],
            },
            {
                "type": AdaptiveCardConst.CONTAINER,
                "style": "emphasis",
                "items": [
                    {
                        "type": AdaptiveCardConst.TEXT_BLOCK,
                        "text": "My Collections",
                        "weight": "Bolder",
                        "size": "Medium",
                    },
                    {
                        "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                        "id": "userOptions",
                        "style": "expanded",
                        "isMultiSelect": True,
                        "choices": formatted_user_collections,
                        "value": ",".join(
                            [c["value"] for c in formatted_user_collections if c["title"] in selected_options["user"]],
                        ),
                    },
                ],
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Toggle Analysis Mode:",
                "weight": "Bolder",
                "size": "Large",
                "spacing": "Medium",
            },
            {
                "type": AdaptiveCardConst.INPUT_TOGGLE,
                "id": "analysisMode",
                "title": "Analysis mode",
                "value": analysis_mode,
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Toggle Web Search:",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": AdaptiveCardConst.INPUT_TOGGLE,
                "id": "webSearch",
                "title": "Web search",
                "value": str(web_search).lower(),
            },
        ],
        "actions": [
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Submit",
                "data": {"action": "update_data_sources"},
            },
        ],
    }
