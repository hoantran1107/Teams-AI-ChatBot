from langchain_core.messages import HumanMessage

from src.services.custom_llm.services.llm_utils import LLMUtils

PROMPT_TEXT = "Based on this image, summarize this image."


def summary_image_using_llm(image_base64: str, is_process_summary: bool) -> tuple[bool, str]:
    """Summarize the image using LLM.

    Check if the image is an icon or an actual image.
    If it is an icon, return is_icon = true and summary of the icon.
    If it is an actual image, return is_icon = false and summary of the image.
    """
    # Check if the image is an icon (e.g., small size, specific patterns, etc.)
    is_icon = check_if_icon(image_base64)

    if is_icon:
        prompt_text = "Based on this icon, summarize this icon. Return only string like, yes, no, maybe, etc."
    else:
        if is_process_summary:
            prompt_text = PROMPT_TEXT
        else:
            return is_icon, ""

    request_content = [
        {"type": "text", "text": prompt_text},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
    ]

    llm_instance = LLMUtils.get_azure_openai_llm(timeout=30)
    response = llm_instance.invoke([HumanMessage(content=request_content)])
    return is_icon, str(response.content)


def check_if_icon(image_base64: str) -> bool:
    """
    Check if the image is an icon based on its characteristics.
    This function checks if the image size is small and if the file size is small.
    """
    import base64
    from io import BytesIO

    from PIL import Image

    # Decode the base64 image
    image_data = base64.b64decode(image_base64)
    image = Image.open(BytesIO(image_data))

    # Check if the image size is small (e.g., less than 64x64 pixels)
    if image.size[0] <= 64 and image.size[1] <= 64:
        return True

    # Check if the file size is small (e.g., less than 10 KB)
    file_size_kb = len(image_data) / 1024
    if file_size_kb <= 10:
        return True

    return False
