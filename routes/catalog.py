"""
Photo & Poster Generation API Routes
SYNCHRONOUS version for Vercel serverless compatibility
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from enum import Enum
import io
import zipfile

from services.gemini_client import GeminiClient
from services.image_processor import ImageProcessor
from services.overlay_service import OverlayService


router = APIRouter()


class CategoryEnum(str, Enum):
    men = "men"
    women = "women"
    teen_boy = "teen_boy"
    teen_girl = "teen_girl"
    infant_boy = "infant_boy"
    infant_girl = "infant_girl"


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
    layout_style: str = Form("framed_breakout"),
    style_preset: str = Form(""),
    
    # Poster mode - TEXT OVERLAY (all optional)
    hero_text: str = Form(""),       # Main headline
    sub_text: str = Form(""),        # Subtitle
    corner_text: str = Form(""),     # Brand name top left
    size_text: str = Form(""),       # Size info bottom left
    price_text: str = Form(""),      # Price bottom right
    text_color: str = Form("white"), # "white" or "black"
    
    # Images
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...),
    logo: Optional[UploadFile] = File(None)
):
    """Generate model photos or marketing posters and return ZIP directly"""
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 5:
        raise HTTPException(status_code=400, detail="Must provide 1-5 products")
    
    try:
        gemini = GeminiClient()
        processor = ImageProcessor()
        overlay = OverlayService()
        
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
                # Generate clean poster (NO text - AI generates model + background only)
                poster = await gemini.generate_catalog_poster(
                    garment_image=front,
                    logo_image=None,  # Added by overlay
                    category=category,
                    skin_tone=skin_tone,
                    body_type=body_type,
                    marketing_theme=marketing_theme,
                    prop=prop,
                    pose_type=pose_type,
                    shot_angle=shot_angle,
                    headline_text="",  # NOT passed to AI
                    sub_text="",       # NOT passed to AI
                    layout_style=layout_style,
                    style_preset=style_preset
                )
                
                # Apply text overlay with PIL (perfect accuracy)
                has_overlay = hero_text or sub_text or corner_text or size_text or price_text or logo_data
                if has_overlay:
                    print(f"Applying text overlay to product {product_num}...")
                    try:
                        final_poster = overlay.apply_poster_overlay(
                            image_bytes=poster,
                            hero_text=hero_text,
                            sub_text=sub_text,
                            corner_text=corner_text,
                            size_text=size_text,
                            price_text=price_text,
                            logo_bytes=logo_data,
                            text_color=text_color
                        )
                    except Exception as e:
                        print(f"Overlay failed: {e}, using raw poster")
                        final_poster = poster
                else:
                    final_poster = poster
                
                generated_images.append((f"product_{product_num}_poster.png", final_poster))
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
        print(f"ZIP size: {zip_buffer.getbuffer().nbytes} bytes")
        
        safe_brand = "".join(c for c in brand_name if c.isalnum() or c in ' -_').strip() or "output"
        mode_suffix = "posters" if is_poster_mode else "photos"
        
        # Use StreamingResponse for Vercel compatibility
        from fastapi.responses import StreamingResponse
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
    """Test endpoint to verify ZIP binary response works on Vercel"""
    from PIL import Image
    from fastapi.responses import StreamingResponse
    
    # Create a test image
    img = Image.new('RGB', (200, 200), color='blue')
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_bytes = img_buffer.getvalue()
    
    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('test_image.png', img_bytes)
    
    zip_buffer.seek(0)
    
    # Use StreamingResponse for better Vercel compatibility
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="test.zip"'
        }
    )


@router.get("/presets")
async def get_style_presets():
    from services.gemini_client import STYLE_PRESETS, POSE_TYPES, PROP_INTERACTION, THEME_CONFIG
    return {
        "presets": {k: v["description"] for k, v in STYLE_PRESETS.items()},
        "poses": list(POSE_TYPES.keys()),
        "props": list(PROP_INTERACTION.keys()),
        "themes": list(THEME_CONFIG.keys())
    }

