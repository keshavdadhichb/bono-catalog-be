"""
Photo & Poster Generation API Routes
Full Gemini-based generation (no PIL overlay)
"""

import io
import zipfile
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from enum import Enum

from services.gemini_client import GeminiClient
from services.image_processor import ImageProcessor


router = APIRouter()


class CategoryEnum(str, Enum):
    men = "men"
    women = "women"
    teen_boy = "teen_boy"
    teen_girl = "teen_girl"
    infant_boy = "infant_boy"
    infant_girl = "infant_girl"


# Layout styles with descriptions for frontend
LAYOUT_CONFIGS = {
    "hero_bottom": {
        "name": "Hero Bottom",
        "description": "Large headline at bottom, model above",
        "text_fields": ["headline", "subtext"],
        "preview": "Model takes 70% of image, bold headline at bottom 30%"
    },
    "split_vertical": {
        "name": "Split Vertical",
        "description": "Image left, text panel right",
        "text_fields": ["headline", "subtext", "price"],
        "preview": "50/50 split - model on left, clean text panel on right"
    },
    "magazine_cover": {
        "name": "Magazine Cover",
        "description": "Title at top, model center, details at bottom",
        "text_fields": ["brand", "headline", "subtext"],
        "preview": "Classic magazine style with brand masthead"
    },
    "minimal_corner": {
        "name": "Minimal Corner",
        "description": "Small text in corner, model dominates",
        "text_fields": ["brand", "tagline"],
        "preview": "95% model, subtle brand in corner"
    },
    "overlay_gradient": {
        "name": "Overlay Gradient",
        "description": "Gradient overlay with text on image",
        "text_fields": ["headline", "subtext", "cta"],
        "preview": "Full-bleed image with gradient text overlay"
    },
    "framed_border": {
        "name": "Framed Border",
        "description": "White border frame around image",
        "text_fields": ["headline", "subtext"],
        "preview": "Image with elegant white border and text below"
    },
    "bold_typography": {
        "name": "Bold Typography",
        "description": "Huge impactful text, model secondary",
        "text_fields": ["headline"],
        "preview": "60% typography, 40% model - high impact"
    },
    "product_focus": {
        "name": "Product Focus",
        "description": "Clean, product-centric catalog style",
        "text_fields": ["product_name", "price", "sizes"],
        "preview": "E-commerce style with product details"
    }
}


@router.get("/layouts")
async def get_layouts():
    """Get available layouts with their configurations"""
    return LAYOUT_CONFIGS


@router.post("/generate")
async def generate_and_download(
    # Basic fields
    brand_name: str = Form(...),
    category: CategoryEnum = Form(...),
    generation_mode: str = Form("photo"),
    
    # Model appearance
    skin_tone: str = Form("fair"),
    hair_type: str = Form("short black hair"),
    body_type: str = Form(""),
    
    # Shared fields
    shot_angle: str = Form("front_facing"),
    pose_type: str = Form("catalog_standard"),
    
    # Photo mode
    creative_direction: str = Form(""),
    
    # Poster mode - Theme & Layout
    marketing_theme: str = Form("studio_minimal"),
    prop: str = Form("none"),
    layout_style: str = Form("hero_bottom"),
    
    # Text fields for poster (Gemini renders these directly)
    headline: str = Form(""),
    subtext: str = Form(""),
    brand_text: str = Form(""),
    price: str = Form(""),
    cta: str = Form(""),
    tagline: str = Form(""),
    
    # Images
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...),
    logo: Optional[UploadFile] = File(None)
):
    """Generate model photos or marketing posters and return ZIP"""
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 5:
        raise HTTPException(status_code=400, detail="Must provide 1-5 products")
    
    try:
        gemini = GeminiClient()
        processor = ImageProcessor()
        
        # Read uploads
        front_data = [await f.read() for f in front_images]
        back_data = [await b.read() for b in back_images]
        logo_data = await logo.read() if logo else None
        
        # Preprocess garments
        print(f"Processing {len(front_data)} products...")
        front_processed = [processor.prepare_garment(f) for f in front_data]
        back_processed = [processor.prepare_garment(b) for b in back_data]
        
        generated_images = []
        is_poster_mode = generation_mode == "poster"
        
        for i, (front, back) in enumerate(zip(front_processed, back_processed)):
            product_num = i + 1
            print(f"Generating product {product_num}/{len(front_processed)}...")
            
            if is_poster_mode:
                # Build text dict for the layout
                text_content = {
                    "headline": headline,
                    "subtext": subtext,
                    "brand": brand_text or brand_name,
                    "price": price,
                    "cta": cta,
                    "tagline": tagline
                }
                
                # Generate poster with Gemini (text included in generation)
                poster = await gemini.generate_marketing_poster(
                    garment_image=front,
                    logo_image=logo_data,
                    category=category,
                    skin_tone=skin_tone,
                    body_type=body_type,
                    marketing_theme=marketing_theme,
                    prop=prop,
                    pose_type=pose_type,
                    shot_angle=shot_angle,
                    layout_style=layout_style,
                    text_content=text_content
                )
                
                generated_images.append((f"product_{product_num}_poster.png", poster))
            else:
                # Generate simple photos
                front_model = await gemini.generate_model_image(
                    garment_image=front,
                    category=category,
                    view="front",
                    skin_tone=skin_tone,
                    hair_type=hair_type,
                    body_type=body_type,
                    shot_angle=shot_angle,
                    pose_type=pose_type,
                    creative_direction=creative_direction
                )
                
                back_model = await gemini.generate_model_image(
                    garment_image=back,
                    category=category,
                    view="back",
                    skin_tone=skin_tone,
                    hair_type=hair_type,
                    body_type=body_type,
                    shot_angle=shot_angle,
                    pose_type=pose_type,
                    creative_direction=creative_direction
                )
                
                generated_images.append((f"product_{product_num}_front.png", front_model))
                generated_images.append((f"product_{product_num}_back.png", back_model))
        
        print(f"Generated {len(generated_images)} images, creating ZIP...")
        
        # Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, image_bytes in generated_images:
                print(f"Adding: {filename} ({len(image_bytes)} bytes)")
                zf.writestr(filename, image_bytes)
        
        zip_buffer.seek(0)
        
        safe_brand = "".join(c for c in brand_name if c.isalnum() or c in ' -_').strip() or "output"
        mode_suffix = "posters" if is_poster_mode else "photos"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_brand}_{mode_suffix}.zip"'
            }
        )
        
    except Exception as e:
        print(f"Generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/test-zip")
async def test_zip():
    """Test endpoint for ZIP downloads"""
    from PIL import Image
    
    img = Image.new('RGB', (200, 200), color='blue')
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_bytes = img_buffer.getvalue()
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('test.png', img_bytes)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="test.zip"'}
    )


@router.get("/presets")
async def get_style_presets():
    from services.gemini_client import STYLE_PRESETS, POSE_TYPES, PROP_INTERACTION, THEME_CONFIG
    return {
        "presets": {k: v["description"] for k, v in STYLE_PRESETS.items()},
        "poses": list(POSE_TYPES.keys()),
        "props": list(PROP_INTERACTION.keys()),
        "themes": list(THEME_CONFIG.keys()),
        "layouts": LAYOUT_CONFIGS
    }
