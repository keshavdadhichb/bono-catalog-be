"""
Gemini Image API Client
High-Quality Virtual Try-On Photo Generation

MODEL: gemini-3-pro-image-preview
RESOLUTION: 2K (2048px)
"""

import os
import asyncio
from io import BytesIO
from typing import Optional, Literal
from PIL import Image
from google import genai
from google.genai import types


# Model configurations with enhanced Indian skin tone descriptions
MODEL_CONFIG = {
    "men": {"description": "adult Indian male", "age_range": "25-35 years old", "default_build": "athletic build"},
    "women": {"description": "adult Indian female", "age_range": "25-35 years old", "default_build": "slim build"},
    "teen_boy": {"description": "Indian teenage boy", "age_range": "12-16 years old", "default_build": "lean build"},
    "teen_girl": {"description": "Indian teenage girl", "age_range": "12-16 years old", "default_build": "slim build"},
    "infant_boy": {"description": "young Indian boy child", "age_range": "4-8 years old", "default_build": "child proportions"},
    "infant_girl": {"description": "young Indian girl child", "age_range": "4-8 years old", "default_build": "child proportions"}
}

# Enhanced skin tone descriptions for Indian models
SKIN_TONES = {
    "fair": "fair North Indian skin tone, light complexion typical of Punjab/Kashmir region",
    "light": "light wheat complexion, North Indian skin tone",
    "wheatish": "wheatish skin tone, typical Indian complexion",
    "medium": "medium brown Indian skin tone",
    "medium brown": "medium brown skin tone, typical of Central India",
    "dark brown": "dark brown skin tone, South Indian complexion",
    "deep": "deep dark skin tone"
}

SHOT_ANGLES = {
    "front_facing": "facing directly towards camera, eye contact",
    "three_quarter": "3/4 angle view, slight turn of body",
    "side_profile": "side profile view, body turned 90 degrees",
    "dynamic": "dynamic walking or movement pose",
    "casual": "relaxed, natural casual stance"
}

POSE_TYPES = {
    "catalog_standard": "classic catalog pose, hands relaxed at sides, confident stance",
    "hands_on_hips": "hands on hips, confident and powerful stance",
    "arms_crossed": "arms crossed casually, relaxed expression",
    "walking": "mid-stride walking pose, natural movement",
    "dynamic": "dynamic movement pose with energy"
}


class GeminiClient:
    """Client for Gemini Image API - 2K High Quality Photo Generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        self.client = genai.Client(api_key=self.api_key)
        # Use gemini-3-pro-image-preview for 2K resolution
        self.model = "gemini-3-pro-image-preview"
    
    def _image_to_pil(self, image_bytes: bytes) -> Image.Image:
        return Image.open(BytesIO(image_bytes))
    
    def _pil_to_bytes(self, image: Image.Image, format: str = "PNG", quality: int = 100) -> bytes:
        """Convert PIL Image to bytes with MAXIMUM quality"""
        buffer = BytesIO()
        if format.upper() == "PNG":
            image.save(buffer, format="PNG", optimize=False)
        else:
            image.save(buffer, format="JPEG", quality=quality, subsampling=0)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _extract_image_from_response(self, response) -> bytes:
        """Extract image from Gemini response with NO quality loss"""
        parts = None
        if hasattr(response, 'parts') and response.parts:
            parts = response.parts
        elif hasattr(response, 'candidates') and response.candidates:
            if response.candidates[0].content and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
        
        if not parts:
            print(f"Response has no parts. Type: {type(response)}")
            if hasattr(response, 'text'):
                print(f"Response text: {response.text[:500] if response.text else 'None'}")
            raise ValueError("No parts found in response")
        
        for part in parts:
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                if hasattr(part, 'as_image'):
                    pil_image = part.as_image()
                    if pil_image:
                        return self._pil_to_bytes(pil_image, format="PNG")
                elif hasattr(part.inline_data, 'data'):
                    return part.inline_data.data
            
            if hasattr(part, 'text') and part.text:
                print(f"Got text part: {part.text[:200]}...")
        
        raise ValueError("No image found in response")

    async def generate_model_image(
        self,
        garment_image: bytes,
        category: str,
        view: Literal["front", "back"],
        skin_tone: str = "fair",
        hair_type: str = "short black hair",
        body_type: str = "",
        shot_angle: str = "front_facing",
        pose_type: str = "catalog_standard",
        creative_direction: str = ""
    ) -> bytes:
        """
        Generate a high-quality 2K virtual try-on image
        
        Uses gemini-3-pro-image-preview with medium quality (2K resolution)
        Returns PNG image with ZERO quality degradation
        """
        config = MODEL_CONFIG.get(category, MODEL_CONFIG["teen_boy"])
        
        # Enhanced skin tone description
        skin_desc = SKIN_TONES.get(skin_tone, SKIN_TONES.get("fair", skin_tone))
        
        angle_desc = SHOT_ANGLES.get(shot_angle, SHOT_ANGLES["front_facing"])
        pose_desc = POSE_TYPES.get(pose_type, POSE_TYPES["catalog_standard"])
        build = body_type if body_type else config["default_build"]
        
        prompt = f"""Create a PHOTOREALISTIC high-resolution fashion catalog photograph.

MODEL DESCRIPTION:
- {config['description']}, {config['age_range']}
- Skin: {skin_desc}
- Hair: {hair_type}, well-groomed
- Build: {build}
- Expression: Natural, confident, pleasant

CAMERA & POSE:
- View: {view} view of the model
- Angle: {angle_desc}
- Pose: {pose_desc}
- Framing: Full body shot, head to toe visible

GARMENT REQUIREMENTS (CRITICAL):
- Model is wearing EXACTLY this garment from the reference image
- The garment design, graphics, logos, text MUST be preserved EXACTLY
- Do NOT alter, modify, or reimagine any printed elements
- Fabric color, texture, and pattern must match reference precisely
- Natural draping based on model's pose and body

PHOTOGRAPHY STYLE:
- Clean white studio background
- Professional soft lighting, no harsh shadows
- High-end fashion catalog aesthetic (like Zara, H&M lookbook)
- Crisp, sharp focus throughout
- No visible background elements or props

QUALITY REQUIREMENTS:
- Photorealistic result, indistinguishable from real photography
- No AI artifacts, distortions, or unnatural elements
- Consistent skin texture and natural skin details
- High resolution output suitable for print

{f"ADDITIONAL DIRECTION: {creative_direction}" if creative_direction else ""}

OUTPUT: A single photorealistic image of the model wearing the garment."""

        garment_pil = self._image_to_pil(garment_image)
        
        # Use 2K resolution (medium quality)
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=[prompt, garment_pil],
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE'],
                image_config=types.ImageConfig(
                    image_size="medium"  # 2K resolution (2048px)
                )
            )
        )
        
        return self._extract_image_from_response(response)
