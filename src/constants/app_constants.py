from typing import ClassVar

MIME_TYPE = "application/json"

class AdaptiveCardConst:
    """Constants related to adaptive cards."""

    # Common card versions
    CARD_VERSION_1_3: ClassVar[str] = "1.3"
    CARD_VERSION_1_4: ClassVar[str] = "1.4"
    CARD_VERSION_1_5: ClassVar[str] = "1.5"

    # Common card types
    TEXT_BLOCK: ClassVar[str] = "TextBlock"
    CONTAINER: ClassVar[str] = "Container"
    COLUMN_SET: ClassVar[str] = "ColumnSet"
    COLUMN: ClassVar[str] = "Column"
    ACTION_SET: ClassVar[str] = "ActionSet"
    FACT_SET: ClassVar[str] = "FactSet"
    CONTENT_TYPE: ClassVar[str] = "application/vnd.microsoft.card.adaptive"
    SCHEMA: ClassVar[str] = "https://adaptivecards.io/schemas/adaptive-card.json"
    SCHEMA_ATTRIBUTE: ClassVar[str] = "$schema"
    INPUT_TEXT: ClassVar[str] = "Input.Text"
    INPUT_CHOICE_SET: ClassVar[str] = "Input.ChoiceSet"
    INPUT_TOGGLE: ClassVar[str] = "Input.Toggle"
    ACTION_SUBMIT: ClassVar[str] = "Action.Submit"
    ACTION_OPEN_URL: ClassVar[str] = "Action.OpenUrl"

    # Common text styles
    TEXT_STYLE_DEFAULT: ClassVar[dict] = {"weight": "Normal", "size": "Default"}
    TEXT_STYLE_HEADING: ClassVar[dict] = {"weight": "Bolder", "size": "Medium"}
    TEXT_STYLE_SUBHEADING: ClassVar[dict] = {"weight": "Bolder", "size": "Default"}
    TEXT_STYLE_CAPTION: ClassVar[dict] = {"size": "Small", "isSubtle": True}

    # Common colors
    COLOR_DEFAULT: ClassVar[str | None] = None
    COLOR_ACCENT: ClassVar[str] = "Accent"
    COLOR_GOOD: ClassVar[str] = "Good"
    COLOR_ATTENTION: ClassVar[str] = "Attention"
    COLOR_WARNING: ClassVar[str] = "Warning"

class PagingConst:
    """Constants related to paging."""

    PAGING_SIZE: int = 10
