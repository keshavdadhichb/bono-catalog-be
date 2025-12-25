"""
Gemini Image API Client
High-Quality Virtual Try-On Photo Generation

OUTPUT: 2K resolution images with ZERO quality degradation
"""

import os
import asyncio
from io import BytesIO
from typing import Optional, Literal
from PIL import Image
from google import genai
from google.genai import types


# Model configurations
MODEL_CONFIG = {
    "men": {"description": "adult male", "age_range": "25-35 years old", "default_build": "athletic build"},
    "women": {"description": "adult female", "age_range": "25-35 years old", "default_build": "slim build"},
    "teen_boy": {"description": "teenage boy", "age_range": "12-16 years old", "default_build": "lean build"},
    "teen_girl": {"description": "teenage girl", "age_range": "12-16 years old", "default_build": "slim build"},
    "infant_boy": {"description": "young boy child", "age_range": "4-8 years old", "default_build": "child proportions"},
    "infant_girl": {"description": "young girl child", "age_range": "4-8 years old", "default_build": "child proportions"}
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
    """Client for Gemini Image API - High Quality Photo Generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash-exp"
    
    def _image_to_pil(self, image_bytes: bytes) -> Image.Image:
        return Image.open(BytesIO(image_bytes))
    
    def _pil_to_bytes(self, image: Image.Image, format: str = "PNG", quality: int = 100) -> bytes:
        """Convert PIL Image to bytes with MAXIMUM quality"""
        buffer = BytesIO()
        if format.upper() == "PNG":
            # PNG is lossless - best quality
            image.save(buffer, format="PNG", optimize=False)
        else:
            # JPEG with max quality
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
                        # Return as PNG for lossless quality
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
        skin_tone: str = "medium brown",
        hair_type: str = "short black hair",
        body_type: str = "",
        shot_angle: str = "front_facing",
        pose_type: str = "catalog_standard",
        creative_direction: str = ""
    ) -> bytes:
        """
        Generate a high-quality 2K virtual try-on image
        
        Returns PNG image with ZERO quality degradation
        """
        config = MODEL_CONFIG.get(category, MODEL_CONFIG["men"])
        angle_desc = SHOT_ANGLES.get(shot_angle, SHOT_ANGLES["front_facing"])
        pose_desc = POSE_TYPES.get(pose_type, POSE_TYPES["catalog_standard"])
        build = body_type if body_type else config["default_build"]
        
        prompt = f"""Create a HIGH RESOLUTION professional fashion catalog photograph.

MODEL DESCRIPTION:
- {config['description']}, {config['age_range']}
- Skin tone: {skin_tone}
- Hair: {hair_type}
- Body type: {build}

POSE & CAMERA:
- View: {view} view of the model
- Angle: {angle_desc}
- Pose: {pose_desc}

GARMENT REQUIREMENTS:
- Model is wearing EXACTLY this garment shown in the reference image
- Preserve ALL graphics, logos, text, and printed elements EXACTLY as shown
- Do NOT alter, reimagine, or regenerate any design elements on the garment
- The fabric texture, color, and pattern must match the reference precisely
- Natural fabric draping and realistic wrinkles based on the model's pose

PHOTOGRAPHY STYLE:
- Clean white/off-white studio background
- Professional soft lighting, no harsh shadows
- High-end fashion catalog aesthetic
- FULL BODY shot showing complete outfit
- Sharp focus, high resolution, studio quality

OUTPUT QUALITY:
- Photorealistic result indistinguishable from a real photoshoot
- No synthetic or AI-looking artifacts
- Maximum detail and clarity

{f"CREATIVE DIRECTION: {creative_direction}" if creative_direction else ""}

CRITICAL: The garment design must be EXACTLY preserved from the reference image."""

        garment_pil = self._image_to_pil(garment_image)
        
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=[prompt, garment_pil],
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )
        
        return self._extract_image_from_response(response)
