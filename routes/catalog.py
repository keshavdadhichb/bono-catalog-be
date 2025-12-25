"""
Photo & Poster Generation API Routes
Supports simple virtual try-on photos and full marketing posters
With hybrid overlay system for perfect text/logo rendering
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
from enum import Enum
import io
import zipfile

from services.gemini_client import GeminiClient
from services.image_processor import ImageProcessor
from services.overlay_service import OverlayService


router = APIRouter()
jobs = {}


class CategoryEnum(str, Enum):
    men = "men"
    women = "women"
    teen_boy = "teen_boy"
    teen_girl = "teen_girl"
    infant_boy = "infant_boy"
    infant_girl = "infant_girl"


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    generating = "generating"
    overlaying = "overlaying"
    completed = "completed"
    failed = "failed"


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = 0
    message: str = ""
    download_url: Optional[str] = None


@router.post("/generate", response_model=JobResponse)
async def start_generation(
    background_tasks: BackgroundTasks,
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
    text_color: str = Form("white"),  # "white" or "black"
    
    # Images
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...),
    logo: Optional[UploadFile] = File(None)
):
    """Generate model photos or marketing posters"""
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 10:
        raise HTTPException(status_code=400, detail="Must provide between 1 and 10 products")
    
    job_id = str(uuid.uuid4())
    
    front_data = [await f.read() for f in front_images]
    back_data = [await b.read() for b in back_images]
    logo_data = await logo.read() if logo else None
    
    jobs[job_id] = {
        "status": JobStatus.pending,
        "progress": 0,
        "message": "Job queued",
        "created_at": datetime.now(),
        "brand_name": brand_name,
        "category": category,
        "generation_mode": generation_mode,
        
        # Model appearance
        "skin_tone": skin_tone,
        "hair_type": hair_type,
        "body_type": body_type,
        
        # Photo mode
        "shot_angle": shot_angle,
        "pose_type": pose_type,
        "creative_direction": creative_direction,
        
        # Poster mode
        "marketing_theme": marketing_theme,
        "prop": prop,
        "headline_text": headline_text,
        "sub_text": sub_text,
        "layout_style": layout_style,
        "style_preset": style_preset,
        "text_color": text_color,
        
        # Images
        "front_images": front_data,
        "back_images": back_data,
        "logo": logo_data,
        "generated_images": []
    }
    
    background_tasks.add_task(process_generation_job, job_id)
    
    return JobResponse(
        job_id=job_id,
        status=JobStatus.pending,
        progress=0,
        message="Job started"
    )


async def process_generation_job(job_id: str):
    """Process photo or poster generation job with hybrid overlay"""
    
    job = jobs.get(job_id)
    if not job:
        return
    
    try:
        gemini = GeminiClient()
        processor = ImageProcessor()
        overlay = OverlayService()
        
        job["status"] = JobStatus.processing
        job["message"] = "Preprocessing images..."
        
        # Preprocess garment images
        front_processed = []
        back_processed = []
        for i, (front, back) in enumerate(zip(job["front_images"], job["back_images"])):
            front_processed.append(processor.prepare_garment(front))
            back_processed.append(processor.prepare_garment(back))
            job["progress"] = int((i + 1) / len(job["front_images"]) * 10)
        
        job["status"] = JobStatus.generating
        
        total_products = len(front_processed)
        is_poster_mode = job["generation_mode"] == "poster"
        
        if is_poster_mode:
            job["message"] = "Generating marketing posters..."
        else:
            job["message"] = "Generating model photos..."
        
        for i, (front, back) in enumerate(zip(front_processed, back_processed)):
            product_num = i + 1
            job["message"] = f"Generating product {product_num}/{total_products}..."
            
            if is_poster_mode:
                # Generate marketing poster (without text - AI generates clean image)
                poster = await gemini.generate_catalog_poster(
                    garment_image=front,
                    logo_image=None,  # Logo added by overlay service
                    category=job["category"],
                    skin_tone=job["skin_tone"],
                    body_type=job["body_type"],
                    marketing_theme=job["marketing_theme"],
                    prop=job["prop"],
                    pose_type=job["pose_type"],
                    shot_angle=job["shot_angle"],
                    headline_text="",  # Text added by overlay service
                    sub_text="",
                    layout_style=job["layout_style"],
                    style_preset=job.get("style_preset", "")
                )
                
                # Apply overlay with PIL for perfect text/logo
                job["status"] = JobStatus.overlaying
                job["message"] = f"Applying text overlay to product {product_num}..."
                
                final_poster = overlay.apply_overlay(
                    image_bytes=poster,
                    logo_bytes=job["logo"],
                    headline_text=job["headline_text"],
                    sub_text=job["sub_text"],
                    text_color=job.get("text_color", "white")
                )
                
                job["generated_images"].append((f"product_{product_num}_poster.png", final_poster))
                job["status"] = JobStatus.generating
            else:
                # Generate simple photos (front + back views)
                front_model = await gemini.generate_model_image(
                    garment_image=front,
                    category=job["category"],
                    view="front",
                    skin_tone=job["skin_tone"],
                    hair_type=job["hair_type"],
                    body_type=job["body_type"],
                    shot_angle=job["shot_angle"],
                    pose_type=job["pose_type"],
                    creative_direction=job["creative_direction"]
                )
                
                back_model = await gemini.generate_model_image(
                    garment_image=back,
                    category=job["category"],
                    view="back",
                    skin_tone=job["skin_tone"],
                    hair_type=job["hair_type"],
                    body_type=job["body_type"],
                    shot_angle=job["shot_angle"],
                    pose_type=job["pose_type"],
                    creative_direction=job["creative_direction"]
                )
                
                job["generated_images"].append((f"product_{product_num}_front.png", front_model))
                job["generated_images"].append((f"product_{product_num}_back.png", back_model))
            
            job["progress"] = 10 + int((i + 1) / total_products * 90)
        
        # Clear input images to free memory
        job["front_images"] = []
        job["back_images"] = []
        job["logo"] = None
        
        job["status"] = JobStatus.completed
        job["progress"] = 100
        job["message"] = f"Generated {len(job['generated_images'])} images"
        
    except Exception as e:
        job["status"] = JobStatus.failed
        job["message"] = f"Error: {str(e)}"
        print(f"Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()


@router.get("/status/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    download_url = f"/api/download/{job_id}" if job["status"] == JobStatus.completed else None
    
    return JobResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        download_url=download_url
    )


@router.get("/download/{job_id}")
async def download_photos_zip(job_id: str):
    """Download all generated images as ZIP"""
    
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != JobStatus.completed:
        raise HTTPException(status_code=400, detail="Images not ready")
    
    if not job["generated_images"]:
        raise HTTPException(status_code=404, detail="No images found")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, image_bytes in job["generated_images"]:
            zip_file.writestr(filename, image_bytes)
    
    zip_buffer.seek(0)
    
    mode_suffix = "posters" if job["generation_mode"] == "poster" else "photos"
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={job['brand_name']}_{mode_suffix}.zip"
        }
    )


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
