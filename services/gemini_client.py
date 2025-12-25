"""
Gemini 3 Pro Image (Nano Banana Pro) API Client
Native 2K/4K High-Quality Virtual Try-On Photo Generation

MODEL: gemini-3-pro-image-preview
RESOLUTION: Native 2K (2048px) or 4K (3072px)
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
    "fair": "fair North Indian skin tone, light complexion typical of Punjab/Kashmir/Himachal region, porcelain-like fair skin",
    "light": "light wheat complexion, North Indian skin tone, warm undertones",
    "wheatish": "wheatish skin tone, typical Indian complexion, golden undertones",
    "medium": "medium brown Indian skin tone, warm olive undertones",
    "medium brown": "medium brown skin tone, typical of Central India",
    "dark brown": "dark brown skin tone, South Indian complexion, rich melanin",
    "deep": "deep dark skin tone, ebony complexion"
}

SHOT_ANGLES = {
    "front_facing": "facing directly towards camera, direct eye contact",
    "three_quarter": "3/4 angle view, slight turn of body, one shoulder closer to camera",
    "side_profile": "side profile view, body turned 90 degrees",
    "dynamic": "dynamic walking or movement pose, slight motion blur effect",
    "casual": "relaxed, natural casual stance, weight on one leg"
}

POSE_TYPES = {
    "catalog_standard": "classic catalog pose, hands relaxed at sides, confident stance, shoulders back",
    "hands_on_hips": "hands on hips, confident and powerful stance, elbows out",
    "arms_crossed": "arms crossed casually across chest, relaxed expression",
    "walking": "mid-stride walking pose, natural arm swing, fluid movement",
    "dynamic": "dynamic movement pose with energy, action shot feel"
}


class GeminiClient:
    """Client for Gemini 3 Pro Image - Native 2K High Quality Photo Generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        self.client = genai.Client(api_key=self.api_key)
        # Gemini 3 Pro Image Preview - supports native 2K and 4K
        self.model = "gemini-3-pro-image-preview"
    
    def _image_to_pil(self, image_bytes: bytes) -> Image.Image:
        return Image.open(BytesIO(image_bytes))
    
    def _pil_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        """Convert PIL Image to bytes with MAXIMUM quality"""
        buffer = BytesIO()
        if format.upper() == "PNG":
            image.save(buffer, format="PNG", optimize=False)
        else:
            image.save(buffer, format="JPEG", quality=100, subsampling=0)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _extract_image_from_response(self, response) -> bytes:
        """Extract image from Gemini response"""
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
        Generate a native 2K virtual try-on image
        
        Uses gemini-3-pro-image-preview with image_size="2K"
        Returns PNG image at 2048px resolution
        """
        config = MODEL_CONFIG.get(category, MODEL_CONFIG["teen_boy"])
        skin_desc = SKIN_TONES.get(skin_tone, SKIN_TONES.get("fair", skin_tone))
        angle_desc = SHOT_ANGLES.get(shot_angle, SHOT_ANGLES["front_facing"])
        pose_desc = POSE_TYPES.get(pose_type, POSE_TYPES["catalog_standard"])
        build = body_type if body_type else config["default_build"]
        
        prompt = f"""Generate a PHOTOREALISTIC high-resolution fashion catalog photograph.

MODEL SPECIFICATIONS:
- Ethnicity: {config['description']}
- Age: {config['age_range']}
- Skin: {skin_desc}
- Hair: {hair_type}, well-styled and groomed
- Build: {build}
- Expression: Natural, confident, pleasant smile

CAMERA & COMPOSITION:
- View: {view} view of the model
- Camera Angle: {angle_desc}
- Pose: {pose_desc}
- Framing: Full body shot, complete head to toe visible
- Background: Clean pure white studio backdrop, no shadows

GARMENT REQUIREMENTS (CRITICAL - MUST FOLLOW EXACTLY):
- The model must wear PRECISELY this garment from the reference image
- Preserve EVERY detail: graphics, logos, text, prints, patterns
- Do NOT modify, reimagine, or alter ANY printed elements on the garment
- Fabric color and texture must be IDENTICAL to reference
- Natural draping and wrinkles based on pose

PROFESSIONAL PHOTOGRAPHY STANDARDS:
- Lighting: Soft, diffused studio lighting, no harsh shadows
- Quality: Ultra-sharp focus, professional fashion photography
- Style: Premium catalog aesthetic (Zara, H&M, Mango quality)
- Realism: Indistinguishable from real professional photoshoot

{f"CREATIVE DIRECTION: {creative_direction}" if creative_direction else ""}

Generate a single photorealistic image of the model wearing this exact garment."""

        garment_pil = self._image_to_pil(garment_image)
        
        # Use Gemini 3 Pro Image with native 2K resolution
        # Using dict for image_config for SDK compatibility
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=[prompt, garment_pil],
            config={
                "response_modalities": ["TEXT", "IMAGE"],
                "image_config": {
                    "aspect_ratio": "3:4",
                    "image_size": "2K"
                }
            }
        )
        
        return self._extract_image_from_response(response)
