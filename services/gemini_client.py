"""
Gemini 3 Pro Image (Nano Banana Pro) API Client
Native 2K/4K High-Quality Virtual Try-On Photo Generation

Supports:
- Simple model photos (virtual try-on)
- Marketing catalog posters (with themes, props, typography)
"""

import os
import asyncio
from io import BytesIO
from typing import Optional, Literal, List
from PIL import Image
from google import genai
from google.genai import types


# ============================================
# MODEL CONFIGURATIONS
# ============================================

MODEL_CONFIG = {
    "men": {"description": "adult Indian male", "age_range": "25-35 years old", "default_build": "athletic build"},
    "women": {"description": "adult Indian female", "age_range": "25-35 years old", "default_build": "slim build"},
    "teen_boy": {"description": "Indian teenage boy", "age_range": "12-16 years old", "default_build": "lean build"},
    "teen_girl": {"description": "Indian teenage girl", "age_range": "12-16 years old", "default_build": "slim build"},
    "infant_boy": {"description": "young Indian boy child", "age_range": "4-8 years old", "default_build": "child proportions"},
    "infant_girl": {"description": "young Indian girl child", "age_range": "4-8 years old", "default_build": "child proportions"}
}

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


# ============================================
# MARKETING POSTER CONFIGURATIONS
# ============================================

THEME_CONFIG = {
    "varsity_locker": {
        "background_desc": "a high-school locker room setting with navy blue metal lockers, professional studio lighting, cool blue color palette",
        "lighting": "Cinematic high-contrast lighting, rim lighting on the subject",
        "mood": "Energetic, cool, athletic"
    },
    "studio_color": {
        "background_desc": "a solid sky-blue textured studio wall with a dark blue floor",
        "lighting": "Softbox lighting, even illumination",
        "mood": "Commercial, bright, premium"
    },
    "urban_street": {
        "background_desc": "urban street setting with graffiti-covered walls and concrete",
        "lighting": "Natural golden hour lighting with warm tones",
        "mood": "Edgy, street style, urban cool"
    },
    "studio_minimal": {
        "background_desc": "clean pure white studio backdrop with subtle shadows",
        "lighting": "Soft, diffused studio lighting, no harsh shadows",
        "mood": "Clean, minimal, professional"
    },
    "abstract_color": {
        "background_desc": "abstract colorful gradient background with purple and orange tones",
        "lighting": "Vibrant colored lighting, creative",
        "mood": "Artistic, bold, modern"
    }
}

PROP_INTERACTION = {
    "basketball": "holding a basketball casually on one shoulder, confident sporty stance",
    "skateboard": "leaning on a skateboard with one foot resting on it, relaxed cool pose",
    "headphones": "wearing stylish over-ear headphones around the neck",
    "backpack": "wearing a trendy backpack on one shoulder casually",
    "sunglasses": "wearing stylish aviator or wayfarer sunglasses",
    "chair": "sitting casually on a modern designer chair, relaxed pose",
    "none": "hands in pockets or thumbs hooked in pockets, relaxed confident stance"
}

LAYOUT_STYLES = {
    "framed_breakout": "A white rectangular outline frame positioned behind the model. The model's head and one foot should slightly overlap/break outside the frame to create visual depth and dimension. The brand logo sits at the top center outside the frame.",
    "magazine_style": "High-fashion editorial magazine layout. Bold text placed behind or interacting with the subject. Logo in top corner. Clean typography.",
    "full_bleed": "Edge-to-edge full bleed image with no borders. Logo placed in top corner. Text overlay at bottom with gradient fade.",
    "split_screen": "Vertical split layout - model on one side, product detail or close-up on the other side. Logo centered at top."
}


class GeminiClient:
    """Client for Gemini 3 Pro Image - Native 2K High Quality Photo Generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        self.client = genai.Client(api_key=self.api_key)
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
            # Check for inline_data first
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                if hasattr(part.inline_data, 'data'):
                    return part.inline_data.data
            
            # Try as_image() method
            if hasattr(part, 'as_image'):
                try:
                    img = part.as_image()
                    if img:
                        if hasattr(img, 'save'):
                            buffer = BytesIO()
                            try:
                                img.save(buffer, "PNG")
                            except TypeError:
                                img.save(buffer, format="PNG")
                            buffer.seek(0)
                            return buffer.getvalue()
                        elif hasattr(img, 'image_bytes'):
                            return img.image_bytes
                        elif hasattr(img, '_image_bytes'):
                            return img._image_bytes
                except Exception as e:
                    print(f"Error extracting image: {e}")
            
            if hasattr(part, 'text') and part.text:
                print(f"Got text part: {part.text[:200]}...")
        
        raise ValueError("No image found in response")

    # ============================================
    # SIMPLE PHOTO GENERATION
    # ============================================

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
        """Generate a simple virtual try-on photo (2K resolution)"""
        
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
        
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=[prompt, garment_pil],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="3:4",
                    image_size="2K"
                )
            )
        )
        
        return self._extract_image_from_response(response)

    # ============================================
    # MARKETING POSTER GENERATION
    # ============================================

    async def generate_catalog_poster(
        self,
        garment_image: bytes,
        logo_image: Optional[bytes],
        category: str,
        skin_tone: str = "fair",
        body_type: str = "",
        marketing_theme: str = "studio_minimal",
        prop: str = "none",
        headline_text: str = "",
        sub_text: str = "",
        layout_style: str = "framed_breakout"
    ) -> bytes:
        """Generate a complete marketing catalog poster (2K resolution, 9:16 vertical)"""
        
        config = MODEL_CONFIG.get(category, MODEL_CONFIG["teen_boy"])
        skin_desc = SKIN_TONES.get(skin_tone, SKIN_TONES.get("fair", skin_tone))
        theme = THEME_CONFIG.get(marketing_theme, THEME_CONFIG["studio_minimal"])
        prop_desc = PROP_INTERACTION.get(prop, PROP_INTERACTION["none"])
        layout_desc = LAYOUT_STYLES.get(layout_style, LAYOUT_STYLES["framed_breakout"])
        build = body_type if body_type else config["default_build"]
        
        # Build the poster prompt
        prompt = f"""You are an expert Fashion Art Director and Graphic Designer.
Generate a COMPLETE HIGH-RESOLUTION MARKETING POSTER / ADVERTISEMENT.

--- IMAGE COMPOSITION ---
Type: Commercial Fashion Advertisement / Catalog Poster
Layout Style: {layout_desc}
Background Setting: {theme['background_desc']}
Lighting: {theme['lighting']}
Mood/Aesthetic: {theme['mood']}
Color Palette: Match the background with the garment colors, ensure high contrast for any text.

--- THE MODEL ---
Subject: {config['description']}, {config['age_range']}
Skin Tone: {skin_desc}
Physique: {build}
Pose & Props: The model is {prop_desc}
Expression: Cool, confident, looking slightly away from camera or direct eye contact
Hair: Well-styled, fashionable

--- THE GARMENT (CRITICAL - MUST PRESERVE EXACTLY) ---
The model is wearing the t-shirt/garment provided in the first reference image.
- Transfer the graphic print, logo, text EXACTLY as shown - do not modify or reimagine
- Fabric texture should look premium quality
- Natural draping based on the pose
- Fit should be relaxed but well-fitted

--- BRANDING & TYPOGRAPHY ---
{f'''1. LOGO: Place the provided brand logo (second reference image) prominently at the TOP CENTER or TOP RIGHT of the image. It must be crisp and clearly visible.''' if logo_image else '1. LOGO: Add a subtle brand watermark in the corner.'}
{f'''2. HEADLINE: Render the text "{headline_text}" in a massive, bold, modern sans-serif font.
   - Placement: Lower third of the image or creatively behind/around the model
   - Style: Clean, impactful, commercial advertising style''' if headline_text else ''}
{f'''3. SUBTEXT: Render "{sub_text}" in a smaller, elegant font near the headline or as a tagline.''' if sub_text else ''}
4. GRAPHIC ELEMENTS: If appropriate for the layout, include subtle design elements like:
   - Thin white frame lines
   - Feature callout arrows pointing to garment details
   - Modern minimalist design accents

--- TECHNICAL REQUIREMENTS ---
- Output must look like a FINISHED professional advertisement, not a raw photo
- Any text must be 100% legible and correctly spelled
- Composition should be balanced and commercially appealing
- Quality: Print-ready marketing material

Generate the complete marketing poster image."""

        # Prepare images for multi-modal input
        garment_pil = self._image_to_pil(garment_image)
        
        contents = [prompt, garment_pil]
        if logo_image:
            logo_pil = self._image_to_pil(logo_image)
            contents.append(logo_pil)
        
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="9:16",  # Vertical poster format
                    image_size="2K"
                )
            )
        )
        
        return self._extract_image_from_response(response)
