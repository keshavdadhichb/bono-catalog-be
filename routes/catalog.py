"""
Photo & Poster Generation API Routes
SYNCHRONOUS version for Vercel serverless compatibility
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from enum import Enum
import io
import zipfile
import asyncio

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


class GenerateResponse(BaseModel):
    success: bool
    message: str
    image_count: int = 0


@router.post("/generate")
async def generate_and_download(
    # Basic fields
    brand_name: str = Form(...),
    category: CategoryEnum = Form(...),
    generation_mode: str = Form("photo"),  # "photo" or "poster"
    
    # Model appearance
    skin_tone: str = Form("fair"),
    hair_type: str = Form("short black hair"),
    body_type: str = Form(""),
    
    # Photo mode fields
    shot_angle: str = Form("front_facing"),
    pose_type: str = Form("catalog_standard"),
    creative_direction: str = Form(""),
    
    # Poster mode fields
    marketing_theme: str = Form("studio_minimal"),
    prop: str = Form("none"),
    headline_text: str = Form(""),
    sub_text: str = Form(""),
    layout_style: str = Form("framed_breakout"),
    style_preset: str = Form(""),
    text_color: str = Form("white"),
    
    # Images
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...),
    logo: Optional[UploadFile] = File(None)
):
    """Generate model photos or marketing posters and return ZIP directly"""
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 5:
        raise HTTPException(status_code=400, detail="Must provide between 1 and 5 products")
    
    try:
        gemini = GeminiClient()
        processor = ImageProcessor()
        overlay = OverlayService()
        
        # Read all uploaded files
        front_data = [await f.read() for f in front_images]
        back_data = [await b.read() for b in back_images]
        logo_data = await logo.read() if logo else None
        
        # Preprocess garment images
        print(f"Processing {len(front_data)} products...")
        front_processed = [processor.prepare_garment(f) for f in front_data]
        back_processed = [processor.prepare_garment(b) for b in back_data]
        
        generated_images = []
        is_poster_mode = generation_mode == "poster"
        
        for i, (front, back) in enumerate(zip(front_processed, back_processed)):
            product_num = i + 1
            print(f"Generating product {product_num}/{len(front_processed)}...")
            
            if is_poster_mode:
                # Generate marketing poster
                poster = await gemini.generate_catalog_poster(
                    garment_image=front,
                    logo_image=None,
                    category=category,
                    skin_tone=skin_tone,
                    body_type=body_type,
                    marketing_theme=marketing_theme,
                    prop=prop,
                    pose_type=pose_type,
                    shot_angle=shot_angle,
                    headline_text="",
                    sub_text="",
                    layout_style=layout_style,
                    style_preset=style_preset
                )
                
                # Apply overlay (with fallback)
                final_poster = poster
                if headline_text or sub_text or logo_data:
                    try:
                        final_poster = overlay.apply_overlay(
                            image_bytes=poster,
                            logo_bytes=logo_data,
                            headline_text=headline_text,
                            sub_text=sub_text,
                            text_color=text_color
                        )
                    except Exception as e:
                        print(f"Overlay failed: {e}, using raw poster")
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
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, image_bytes in generated_images:
                print(f"Adding to ZIP: {filename} ({len(image_bytes)} bytes)")
                zip_file.writestr(filename, image_bytes)
        
        zip_buffer.seek(0)
        zip_content = zip_buffer.getvalue()
        
        print(f"ZIP created: {len(zip_content)} bytes")
        
        # Sanitize filename
        safe_brand = "".join(c for c in brand_name if c.isalnum() or c in ' -_').strip() or "output"
        mode_suffix = "posters" if is_poster_mode else "photos"
        
        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_brand}_{mode_suffix}.zip"',
                "Content-Type": "application/zip",
                "Content-Length": str(len(zip_content))
            }
        )
        
    except Exception as e:
        print(f"Generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/presets")
async def get_style_presets():
    """Get available style presets"""
    from services.gemini_client import STYLE_PRESETS, POSE_TYPES, PROP_INTERACTION, THEME_CONFIG
    
    return {
        "presets": {k: v["description"] for k, v in STYLE_PRESETS.items()},
        "poses": list(POSE_TYPES.keys()),
        "props": list(PROP_INTERACTION.keys()),
        "themes": list(THEME_CONFIG.keys())
    }
