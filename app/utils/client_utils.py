from typing import Union, List
from PIL import Image

def calculate_image_tokens(image: Image.Image) -> int:
    width, height = image.size
    if width <= 384 and height <= 384:
        return 258
    else:
        tiles = ((width - 1) // 768 + 1) * ((height - 1) // 768 + 1)
        return tiles * 258

def calculate_text_tokens(text: str) -> int:
    # Rough estimation: average 1.33 tokens per word 
    return int(len(text.split()) * 1.33)

def calculate_input_tokens(prompt: Union[str, List[Union[str, Image.Image]]]) -> float:
    total_tokens = 0
    if isinstance(prompt, str):
        total_tokens += calculate_text_tokens(prompt)
    elif isinstance(prompt, list):
        for item in prompt:
            if isinstance(item, str):
                total_tokens += calculate_text_tokens(item)
            elif isinstance(item, Image.Image):
                total_tokens += calculate_image_tokens(item)
    return float(total_tokens)

def calculate_output_tokens(text: str) -> float:
    # Output is text only
    return float(calculate_text_tokens(text))
