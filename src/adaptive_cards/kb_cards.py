from src.constants.app_constants import AdaptiveCardConst

KB_INTRO = "📝 Our knowledge base will grow over time as we add more information to the page [Copilot Bot Knowledge Base](https://infodation.atlassian.net/wiki/spaces/IFDRD/pages/3384934401/Copilot+Bot+-+Knowledge+Base+-+POC+version)"
kb_guide = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_3,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Greeting!",
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "👋 Hi there! The IFD Copilot RAG is here to assist you with various tasks. Let me know how I can help!",
            "wrap": True,
        },
    ],
    "actions": [
        {
            "type": AdaptiveCardConst.ACTION_OPEN_URL,
            "title": "🌐 User Guide",
            "url": "https://infodation.atlassian.net/wiki/spaces/IFDRD/pages/3528425969/Copilot+Bot+RAG+-+User+Guide",
        },
        {
            "type": AdaptiveCardConst.ACTION_OPEN_URL,
            "title": "🌐 Share Your Feedback",
            "url": "https://infodation.atlassian.net/wiki/spaces/IFDRD/pages/3279257602/Copilot+Bot+-+User+Feedback+-+POC+version",
        },
        {"type": AdaptiveCardConst.ACTION_SUBMIT, "title": "🔍 Function", "data": {"action": "function"}},
    ],
}

manage_config_card = {
    "Select Data Source": {
        "action": "select_source",
        "icon": "📂",
    },
    "Confluence Pages": {
        "action": "manage_pages",
        "icon": "📄",
    },
    "Knowledge Collections": {
        "action": "manage_collections",
        "icon": "📚",
    },
    "Jira": {
        "action": "manage_jira",
        "icon": "📝",
    },
    "Clear Chat History": {
        "action": "clear_chat_history",
        "icon": "🗑️",
    },
    "Reset": {
        "action": "reset",
        "icon": "🔄",
    },
}
supported_commands = {
    "📋 List Project": "list_projects",
    "📝 Document Sprint": "create_document_sprint",
    "🗑️ Clear Chat History": "clear_chat_history",
    "🔄 Reset": "reset",
}
manage_pages_card = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_3,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "📄 Confluence Pages",
            "weight": "Bolder",
            "color": "Good",
            "size": "Medium",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "isSubtle": True,
            "text": "You can manage your Confluence pages here. Choose an action to proceed.",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.ACTION_SET,
            "actions": [
                {
                    "type": AdaptiveCardConst.ACTION_SUBMIT,
                    "title": "➕ Add Confluence Page",
                    "style": "positive",
                    "data": {"action": "add_confluence_page"},
                },
            ],
        },
        {
            "type": AdaptiveCardConst.ACTION_SET,
            "actions": [
                {
                    "type": AdaptiveCardConst.ACTION_SUBMIT,
                    "title": "📄 Show Confluence Pages",
                    "style": "default",
                    "data": {"action": "show_document"},
                },
            ],
        },
    ],
}

manage_collections_card = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_3,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "📚 Knowledge Collections",
            "weight": "Bolder",
            "color": "Good",
            "size": "Medium",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "isSubtle": True,
            "text": "You can manage your knowledge collections here. Choose an action to proceed.",
            "wrap": True,
        },
    ],
    "actions": [
        {
            "type": AdaptiveCardConst.ACTION_SUBMIT,
            "style": "positive",
            "title": "➕ Create New Knowledge Collection",
            "data": {"action": "create_new_knowledge_base"},
        },
        {
            "type": AdaptiveCardConst.ACTION_SUBMIT,
            "style": "default",
            "title": "📚 View Knowledge Base Collection",
            "data": {"action": "show_document"},
        },
        {
            "type": AdaptiveCardConst.ACTION_SUBMIT,
            "style": "default",
            "title": "🗑️ Remove your Knowledge Base Collection",
            "data": {"action": "remove_document"},
        },
    ],
}
manage_jira_card = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_3,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": " 📝 Jira",
            "color": "Good",
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "isSubtle": True,
            "text": "You can get information about Jira projects, sprints, and tickets here.",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.ACTION_SET,
            "actions": [
                {
                    "type": AdaptiveCardConst.ACTION_SUBMIT,
                    "title": "📝 Generate Sprint Document",
                    "style": "positive",
                    "data": {"action": "create_document_sprint"},
                },
            ],
        },
        {
            "type": AdaptiveCardConst.ACTION_SET,
            "actions": [
                {
                    "type": AdaptiveCardConst.ACTION_SUBMIT,
                    "title": "📋 List project",
                    "style": "default",
                    "data": {"action": "list_projects"},
                },
            ],
        },
    ],
}


commands_card = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_3,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "📘 List of Supported Commands",
            "color": "Good",
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "isSubtle": True,
            "text": "You can use the following commands to interact with the bot:",
            "wrap": True,
        },
        *[
            {
                "type": AdaptiveCardConst.ACTION_SET,
                "actions": [
                    {
                        "type": AdaptiveCardConst.ACTION_SUBMIT,
                        "title": f"{item['icon']} {label}",
                        "data": {"action": item["action"]},
                    },
                ],
            }
            for label, item in manage_config_card.items()
        ],
    ],
}

clear_chat_history_card = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_3,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "🧹 Chat History Cleared",
            "weight": "Bolder",
            "size": "Medium",
            "color": "Good",
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Chat history cleared! Starting fresh conversation.",
            "wrap": True,
        },
    ],
}
clear_history_error_card = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_3,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "⚠️ Error Clearing History",
            "weight": "Bolder",
            "size": "Medium",
            "color": "Warning",
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Error clearing history, but you can continue chatting.",
            "wrap": True,
        },
    ],
}

create_collection_card = {
    "type": "AdaptiveCard",
    "version": AdaptiveCardConst.CARD_VERSION_1_5,
    "body": [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "📚 Create New Knowledge Collection",
            "weight": "Bolder",
            "size": "Medium",
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Enter collection details below:",
            "wrap": True,
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Collection Name:",
            "wrap": True,
            "spacing": "Medium",
        },
        {
            "type": AdaptiveCardConst.INPUT_TEXT,
            "id": "collectionName",
            "placeholder": "Enter collection name",
            "isRequired": True,
            "errorMessage": "Collection name is required",
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Collection Description:",
            "wrap": True,
            "spacing": "Medium",
        },
        {
            "type": AdaptiveCardConst.INPUT_TEXT,
            "id": "note",
            "placeholder": "Enter a description for this collection",
            "isMultiline": True,
            "isRequired": False,
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": (
                "💡 Tips: A detailed description helps the AI understand the context and purpose of "
                "your collection, resulting in more accurate and relevant answers when you search "
                "this knowledge base."
            ),
            "wrap": True,
            "isSubtle": True,
            "size": "Small",
            "spacing": "Medium",
        },
    ],
    "actions": [
        {
            "type": AdaptiveCardConst.ACTION_SUBMIT,
            "title": "Create Collection",
            "data": {"action": "create_collection_submit"},
        },
    ],
    AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
}
