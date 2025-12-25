"""
Photo Generation API Routes
Simple virtual try-on photo generation (Vercel compatible - in-memory storage)
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
    brand_name: str = Form(...),
    category: CategoryEnum = Form(...),
    creative_direction: str = Form(""),
    skin_tone: str = Form("medium brown"),
    hair_type: str = Form("short black hair"),
    body_type: str = Form(""),
    shot_angle: str = Form("front_facing"),
    pose_type: str = Form("catalog_standard"),
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...)
):
    """Generate high-quality model photos"""
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 10:
        raise HTTPException(status_code=400, detail="Must provide between 1 and 10 products")
    
    job_id = str(uuid.uuid4())
    
    front_data = [await f.read() for f in front_images]
    back_data = [await b.read() for b in back_images]
    
    jobs[job_id] = {
        "status": JobStatus.pending,
        "progress": 0,
        "message": "Job queued",
        "created_at": datetime.now(),
        "brand_name": brand_name,
        "category": category,
        "creative_direction": creative_direction,
        "skin_tone": skin_tone,
        "hair_type": hair_type,
        "body_type": body_type,
        "shot_angle": shot_angle,
        "pose_type": pose_type,
        "front_images": front_data,
        "back_images": back_data,
        "generated_images": []  # List of (filename, bytes)
    }
    
    background_tasks.add_task(process_photo_job, job_id)
    
    return JobResponse(
        job_id=job_id,
        status=JobStatus.pending,
        progress=0,
        message="Job started"
    )


async def process_photo_job(job_id: str):
    """Generate high-quality model photos - all in memory"""
    
    job = jobs.get(job_id)
    if not job:
        return
    
    try:
        gemini = GeminiClient()
        processor = ImageProcessor()
        
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
        job["message"] = "Generating model photos..."
        
        total_products = len(front_processed)
        
        for i, (front, back) in enumerate(zip(front_processed, back_processed)):
            product_num = i + 1
            job["message"] = f"Generating product {product_num}/{total_products}..."
            
            # Generate front view
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
            
            # Generate back view
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
            
            # Store in memory only
            job["generated_images"].append((f"product_{product_num}_front.png", front_model))
            job["generated_images"].append((f"product_{product_num}_back.png", back_model))
            
            job["progress"] = 10 + int((i + 1) / total_products * 90)
        
        # Clear input images to free memory
        job["front_images"] = []
        job["back_images"] = []
        
        job["status"] = JobStatus.completed
        job["progress"] = 100
        job["message"] = f"Generated {len(job['generated_images'])} photos"
        
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
    """Download all photos as ZIP - from memory"""
    
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != JobStatus.completed:
        raise HTTPException(status_code=400, detail="Photos not ready")
    
    if not job["generated_images"]:
        raise HTTPException(status_code=404, detail="No images found")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, image_bytes in job["generated_images"]:
            zip_file.writestr(filename, image_bytes)
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={job['brand_name']}_photos.zip"
        }
    )
