"""
Gemini 3 Pro Image (Nano Banana Pro) API Client
Native 2K/4K High-Quality Virtual Try-On Photo Generation

Features:
- Simple model photos (virtual try-on)
- Marketing catalog posters (with themes, props, typography)
- Hybrid overlay system for perfect text
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
    "teen_boy": {"description": "Indian teenage boy", "age_range": "14-18 years old", "default_build": "lean athletic build"},
    "teen_girl": {"description": "Indian teenage girl", "age_range": "14-18 years old", "default_build": "slim build"},
    "infant_boy": {"description": "young Indian boy child", "age_range": "6-10 years old", "default_build": "child proportions"},
    "infant_girl": {"description": "young Indian girl child", "age_range": "6-10 years old", "default_build": "child proportions"}
}

SKIN_TONES = {
    "fair": "fair North Indian skin tone, light porcelain complexion typical of Kashmir/Punjab/Himachal, glowing healthy skin",
    "light": "light wheat complexion, North Indian skin tone, warm golden undertones, clear skin",
    "wheatish": "wheatish skin tone, classic Indian complexion, warm golden-olive undertones",
    "medium": "medium brown Indian skin tone, warm olive undertones, even complexion",
    "medium brown": "medium brown skin tone, typical of Central India, healthy glow",
    "dark brown": "dark brown skin tone, South Indian complexion, rich melanin, radiant skin",
    "deep": "deep dark skin tone, beautiful ebony complexion, luminous skin"
}

# ============================================
# EXPANDED POSES (NEW!)
# ============================================

POSE_TYPES = {
    # Standing poses
    "catalog_standard": "classic catalog pose, standing straight with hands relaxed at sides, feet shoulder-width apart, confident shoulders-back stance, direct eye contact",
    "hands_on_hips": "power pose with hands firmly on hips, elbows out, weight on one leg, confident assertive expression",
    "arms_crossed": "arms crossed casually across chest, relaxed confident stance, slight head tilt, approachable expression",
    "hands_in_pockets": "relaxed stance with both hands in pockets, weight shifted to one leg, casual cool demeanor",
    "one_hand_pocket": "one hand casually in pocket, other arm relaxed at side, natural confident stance",
    
    # Walking/Movement poses
    "walking": "mid-stride walking pose, one leg forward, natural arm swing, fluid movement, captured motion",
    "walking_towards": "walking towards camera with purpose, confident stride, direct eye contact",
    "dynamic_movement": "dynamic energetic movement pose, body in motion, action shot feel, athletic energy",
    
    # Sitting poses (NEW!)
    "sitting_chair": "sitting casually on a sleek modern designer chair, legs crossed elegantly, one arm resting on armrest, relaxed confident model pose",
    "sitting_stool": "sitting on a high stool, one foot on footrest, leaning slightly forward, engaging pose",
    "sitting_floor": "sitting cross-legged on the floor, relaxed urban street style pose, hands resting on knees",
    "sitting_edge": "sitting on the edge of a platform/box, legs dangling, casual youthful energy",
    
    # Leaning poses (NEW!)
    "leaning_wall": "leaning casually against a wall, one foot flat against wall, arms crossed or in pockets, cool relaxed vibe",
    "leaning_forward": "leaning forward slightly towards camera, hands on knees or thighs, engaging intense look",
    "shoulder_lean": "leaning on one shoulder against wall, relaxed street style pose, nonchalant attitude",
    
    # Dynamic poses (NEW!)
    "crouching": "low athletic crouch, one knee down, dynamic street style pose, intense focused expression",
    "jumping": "captured mid-air jump, legs bent, arms dynamic, energetic joyful expression, athletic",
    "stretching": "casual stretch pose, arms above head, relaxed expression, showing garment fit",
    "turning": "captured mid-turn, body in rotation, dynamic fashion photography moment",
    
    # Editorial poses (NEW!)
    "editorial_dramatic": "high-fashion editorial pose, dramatic angle, one hand touching face or hair, intense gaze",
    "editorial_relaxed": "editorial soft pose, slight lean, natural lighting expression, effortless chic"
}

# ============================================
# EXPANDED SHOT ANGLES
# ============================================

SHOT_ANGLES = {
    "front_facing": "facing directly towards camera, straight-on shot, direct eye contact, symmetrical framing",
    "three_quarter": "3/4 angle view, body turned 30-45 degrees, one shoulder closer to camera, dynamic depth",
    "side_profile": "full side profile view, body turned 90 degrees, showcasing garment silhouette",
    "low_angle": "low angle hero shot, camera looking up at model, powerful commanding presence",
    "high_angle": "slight high angle, camera above eye level, approachable friendly feel",
    "dutch_angle": "slight dutch angle tilt, creative dynamic composition, editorial style",
    "over_shoulder": "shot from slightly behind over the shoulder, showing back of garment",
    "dynamic": "dynamic varied angle, movement captured, action photography style"
}

# ============================================
# EXPANDED PROPS (NEW!)
# ============================================

PROP_INTERACTION = {
    "none": "no props, hands naturally positioned - in pockets, at sides, or arms crossed",
    
    # Sports
    "basketball": "holding a basketball casually on one shoulder or tucked under arm, confident sporty stance",
    "skateboard": "standing with one foot on skateboard, or holding skateboard under arm, street style cool",
    "football": "holding a football casually, athletic sporty pose",
    "tennis_racket": "holding tennis racket over shoulder, preppy athletic look",
    
    # Accessories (NEW!)
    "cap": "wearing a trendy baseball cap, brim slightly to the side or backwards, street style",
    "beanie": "wearing a stylish beanie/knit cap, casual cool winter vibe",
    "sunglasses": "wearing stylish sunglasses (aviators or wayfarers), cool mysterious vibe",
    "sunglasses_holding": "holding sunglasses in hand or hooked on collar, casual gesture",
    "watch": "visible luxury wristwatch, wrist positioned to show watch prominently",
    "chain": "wearing a gold or silver chain necklace visible over/under the garment",
    "bracelet": "visible stylish bracelet or wristband, casual accessories",
    
    # Bags (NEW!)
    "backpack": "wearing a trendy backpack on one shoulder, urban street style",
    "sling_bag": "wearing cross-body sling bag, modern casual look",
    "duffle_bag": "holding gym duffle bag, athletic lifestyle vibe",
    
    # Lifestyle (NEW!)
    "headphones": "wearing over-ear headphones around neck or on head, music lover vibe",
    "earbuds": "wireless earbuds in ears, modern tech-savvy look",
    "coffee": "holding takeaway coffee cup casually, urban lifestyle pose",
    "phone": "casually looking at or holding smartphone, modern connected lifestyle",
    "book": "holding a book or magazine, intellectual casual vibe",
    
    # Furniture (NEW!)
    "chair": "interacting with a modern designer chair - sitting, leaning, or standing near",
    "stool": "using a high stool as prop - sitting or leaning",
    "box": "sitting on or leaning against a studio box/cube",
    
    # Creative (NEW!)
    "jacket_shoulder": "jacket draped over one shoulder, additional styling layer",
    "hoodie_up": "hoodie worn with hood up, street style urban look",
    "hands_gesture": "expressive hand gestures, talking/pointing, dynamic interaction"
}

# ============================================
# MARKETING THEME CONFIGURATIONS
# ============================================

THEME_CONFIG = {
    "studio_minimal": {
        "background_desc": "clean pure white seamless studio backdrop with subtle shadows",
        "lighting": "Professional soft diffused studio lighting, beauty dish key light, no harsh shadows",
        "mood": "Clean, minimal, premium commercial catalog",
        "camera": "Shot on Sony A7R IV with 85mm f/1.4 lens, crisp sharp focus"
    },
    "varsity_locker": {
        "background_desc": "high-school locker room setting with navy blue metal lockers in background, polished floor",
        "lighting": "Cinematic high-contrast lighting, strong rim lights, cool blue tones",
        "mood": "Energetic, athletic, youthful, sporty cool",
        "camera": "Shot on Canon 5D Mark IV, 50mm lens, dramatic lighting"
    },
    "studio_color": {
        "background_desc": "solid colored studio wall (complementary to garment color) with matching floor",
        "lighting": "Professional softbox lighting with colored gels, even illumination",
        "mood": "Commercial, vibrant, premium lookbook style",
        "camera": "Medium format Hasselblad quality, exceptional detail"
    },
    "urban_street": {
        "background_desc": "urban street setting with graffiti walls, concrete textures, city environment",
        "lighting": "Natural golden hour lighting, warm tones, authentic street photography",
        "mood": "Edgy, street style, raw urban cool, authentic",
        "camera": "Shot on Fuji X-T4, 35mm lens, film grain aesthetic"
    },
    "abstract_color": {
        "background_desc": "abstract colorful gradient background with flowing purple, orange, and blue tones",
        "lighting": "Creative artistic lighting with colored highlights",
        "mood": "Artistic, bold, modern, creative campaign",
        "camera": "Fashion editorial style photography, high contrast"
    },
    "industrial": {
        "background_desc": "industrial warehouse setting with exposed brick, metal beams, raw textures",
        "lighting": "Moody directional lighting, dramatic shadows, industrial feel",
        "mood": "Edgy, raw, urban industrial, fashion forward",
        "camera": "Shot with dramatic contrast, selective focus"
    },
    "nature_outdoor": {
        "background_desc": "natural outdoor setting with soft bokeh foliage background",
        "lighting": "Soft natural daylight, golden hour warmth",
        "mood": "Fresh, natural, organic, lifestyle",
        "camera": "Shot at f/2.8, beautiful background blur"
    },
    "neon_night": {
        "background_desc": "night city setting with neon lights, urban nightlife atmosphere",
        "lighting": "Neon colored lighting, pink and blue tones, night photography",
        "mood": "Nightlife, edgy, modern, vibrant energy",
        "camera": "High ISO night photography, neon glow effects"
    }
}

# ============================================
# LAYOUT STYLES
# ============================================

LAYOUT_STYLES = {
    "framed_breakout": "A clean white rectangular outline frame positioned behind the model. The model's head and one foot should slightly overlap/break outside the frame to create visual depth and dimension. Clean negative space around the frame for text placement.",
    "magazine_style": "High-fashion editorial magazine layout. Bold asymmetric composition. Model positioned dynamically with ample space for text elements. Fashion magazine cover aesthetic.",
    "full_bleed": "Edge-to-edge full bleed image composition with no borders. Model as hero element. Space at bottom for text overlay with subtle gradient fade.",
    "split_screen": "Creative split composition with model on one side and complementary negative space on other side for branding/text. Modern editorial design.",
    "centered_minimal": "Model perfectly centered with generous white space on all sides. Ultra-minimal clean aesthetic. Maximum focus on the garment.",
    "off_center_dramatic": "Model positioned off-center using rule of thirds. Dramatic negative space for bold typography. High-fashion campaign feel."
}

# ============================================
# STYLE PRESETS (NEW!)
# ============================================

STYLE_PRESETS = {
    "editorial_high_fashion": {
        "description": "High-end fashion editorial style",
        "pose": "editorial_dramatic",
        "angle": "three_quarter",
        "theme": "studio_minimal",
        "layout": "magazine_style",
        "prompt_addon": "High-fashion editorial photography. Dramatic lighting. Shot for Vogue or GQ. Exceptional attention to styling details."
    },
    "street_urban": {
        "description": "Urban streetwear photography",
        "pose": "leaning_wall",
        "angle": "low_angle",
        "theme": "urban_street",
        "layout": "full_bleed",
        "prompt_addon": "Authentic street photography vibe. Raw urban energy. Hypebeast aesthetic. Shot like Supreme or Off-White lookbook."
    },
    "catalog_clean": {
        "description": "Clean e-commerce catalog style",
        "pose": "catalog_standard",
        "angle": "front_facing",
        "theme": "studio_minimal",
        "layout": "centered_minimal",
        "prompt_addon": "Clean, crisp e-commerce photography. Crystal clear product focus. Shot like Zara or Uniqlo catalog."
    },
    "sporty_athletic": {
        "description": "Athletic sportswear style",
        "pose": "dynamic_movement",
        "angle": "dynamic",
        "theme": "varsity_locker",
        "layout": "framed_breakout",
        "prompt_addon": "Dynamic athletic photography. Energy and movement. Shot like Nike or Adidas campaign."
    },
    "lifestyle_casual": {
        "description": "Casual lifestyle photography",
        "pose": "sitting_chair",
        "angle": "three_quarter",
        "theme": "nature_outdoor",
        "layout": "off_center_dramatic",
        "prompt_addon": "Relaxed lifestyle photography. Natural and authentic. Shot like lifestyle brand campaign."
    }
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
    
    def _validate_image_bytes(self, data: bytes) -> bytes:
        """Validate that bytes are a valid image, convert if needed"""
        try:
            # Try to open as image to validate
            img = Image.open(BytesIO(data))
            # Re-save as PNG to ensure correct format
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.getvalue()
        except Exception as e:
            print(f"Image validation failed: {e}")
            raise ValueError(f"Invalid image data: {e}")
    
    def _extract_image_from_response(self, response) -> bytes:
        """Extract image from Gemini response with robust fallbacks"""
        import base64
        
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
            raise ValueError("No parts found in response - API may have returned text only")
        
        for part in parts:
            # Method 1: inline_data.data (raw bytes)
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                if hasattr(part.inline_data, 'data'):
                    data = part.inline_data.data
                    if data:
                        print(f"Got inline_data, length: {len(data)}, type: {type(data)}")
                        # Check if it's base64 encoded string
                        if isinstance(data, str):
                            try:
                                data = base64.b64decode(data)
                            except:
                                pass
                        return self._validate_image_bytes(data)
            
            # Method 2: as_image() returns PIL Image
            if hasattr(part, 'as_image'):
                try:
                    img = part.as_image()
                    if img:
                        print(f"Got as_image, type: {type(img)}")
                        buffer = BytesIO()
                        # Try positional arg first (Google's Image object)
                        try:
                            img.save(buffer, "PNG")
                        except TypeError:
                            # Fall back to keyword arg (PIL Image)
                            img.save(buffer, format="PNG")
                        buffer.seek(0)
                        return buffer.getvalue()
                except Exception as e:
                    print(f"as_image() failed: {e}")
            
            # Method 3: Check for image_bytes attribute
            for attr in ['image_bytes', '_image_bytes', 'data']:
                if hasattr(part, attr):
                    data = getattr(part, attr)
                    if data and isinstance(data, (bytes, bytearray)):
                        print(f"Got {attr}, length: {len(data)}")
                        return self._validate_image_bytes(data)
            
            # Log text parts
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
Shot on professional medium format camera with 85mm f/1.8 lens. Exceptional sharpness and detail.

=== MODEL ===
Subject: {config['description']}, {config['age_range']}
Skin: {skin_desc}
Hair: {hair_type}, professionally styled, well-groomed
Build: {build}
Expression: Natural, confident, pleasant - professional model expression

=== CAMERA & COMPOSITION ===
View: {view} view of the model
Camera Angle: {angle_desc}
Pose: {pose_desc}
Framing: Full body shot, complete head to toe visible with small margin
Background: Pure white (#FFFFFF) seamless studio backdrop, no shadows on background

=== THE GARMENT (CRITICAL) ===
The model MUST wear EXACTLY this garment from the reference image:
- Preserve 100% of graphic prints, logos, text, patterns - NO modifications
- Exact color reproduction - match reference perfectly
- Natural fabric draping based on pose and body position
- Realistic wrinkles and folds

=== PROFESSIONAL PHOTOGRAPHY ===
- Lighting: Soft diffused beauty lighting, subtle rim light, no harsh shadows
- Quality: Ultra-sharp focus throughout, professional fashion photography
- Style: Premium catalog aesthetic (Zara, H&M, COS quality)
- Realism: Indistinguishable from real professional photoshoot

{f"ADDITIONAL DIRECTION: {creative_direction}" if creative_direction else ""}

Output: Single photorealistic image of the model wearing this exact garment."""

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
        pose_type: str = "catalog_standard",
        shot_angle: str = "front_facing",
        headline_text: str = "",
        sub_text: str = "",
        layout_style: str = "framed_breakout",
        style_preset: str = ""
    ) -> bytes:
        """Generate a complete marketing catalog poster (2K resolution, 9:16 vertical)"""
        
        config = MODEL_CONFIG.get(category, MODEL_CONFIG["teen_boy"])
        skin_desc = SKIN_TONES.get(skin_tone, SKIN_TONES.get("fair", skin_tone))
        theme = THEME_CONFIG.get(marketing_theme, THEME_CONFIG["studio_minimal"])
        prop_desc = PROP_INTERACTION.get(prop, PROP_INTERACTION["none"])
        pose_desc = POSE_TYPES.get(pose_type, POSE_TYPES["catalog_standard"])
        angle_desc = SHOT_ANGLES.get(shot_angle, SHOT_ANGLES["front_facing"])
        layout_desc = LAYOUT_STYLES.get(layout_style, LAYOUT_STYLES["framed_breakout"])
        build = body_type if body_type else config["default_build"]
        
        # Apply style preset if selected
        preset_addon = ""
        if style_preset and style_preset in STYLE_PRESETS:
            preset = STYLE_PRESETS[style_preset]
            preset_addon = preset.get("prompt_addon", "")
        
        prompt = f"""You are a world-class Fashion Art Director and Commercial Photographer.
Generate a STUNNING HIGH-RESOLUTION MARKETING POSTER / ADVERTISEMENT.
{theme['camera']}

=== COMPOSITION & LAYOUT ===
Type: Premium Fashion Advertisement / Lookbook Poster
Layout: {layout_desc}
Background: {theme['background_desc']}
Lighting: {theme['lighting']}
Mood: {theme['mood']}

=== THE MODEL ===
Subject: {config['description']}, {config['age_range']}
Skin: {skin_desc}
Build: {build}
Hair: Well-styled, fashionable, photo-ready
Expression: Cool, confident, professional model expression
Pose: {pose_desc}
Camera Angle: {angle_desc}
Props/Styling: {prop_desc}

=== THE GARMENT (CRITICAL - EXACT REPRODUCTION) ===
The model wears the garment from the reference image:
- Reproduce graphic prints, logos, text with 100% accuracy
- Exact color match to reference
- Premium fabric appearance, natural draping
- Visible fit and quality

=== DESIGN ELEMENTS ===
{f'FRAME/LAYOUT: Apply the {layout_style} layout style as described above' if layout_style else ''}
Leave strategic negative space for text overlay (will be added in post).
The image should work as a complete composition even without text.

{preset_addon}

=== TECHNICAL EXCELLENCE ===
- Resolution: 2K, print-ready quality
- Sharpness: Razor-sharp focus on model
- Color: Rich, vibrant, commercially appealing
- Quality: Indistinguishable from real photoshoot

Generate the complete marketing poster image WITHOUT any text or brand logos.
Text and logo will be overlaid in post-production for guaranteed accuracy."""

        garment_pil = self._image_to_pil(garment_image)
        
        contents = [prompt, garment_pil]
        # Note: Logo will be overlaid by overlay_service, not by AI
        
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="9:16",
                    image_size="2K"
                )
            )
        )
        
        return self._extract_image_from_response(response)
