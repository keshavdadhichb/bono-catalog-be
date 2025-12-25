"""
Photo Generation API Routes
Simple virtual try-on photo generation with 2K quality export
"""

import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from enum import Enum
from PIL import Image
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
    preview_images: List[str] = []
    download_url: Optional[str] = None


@router.post("/generate", response_model=JobResponse)
async def start_generation(
    background_tasks: BackgroundTasks,
    brand_name: str = Form(...),
    category: CategoryEnum = Form(...),
    creative_direction: str = Form(""),
    # Model description
    skin_tone: str = Form("medium brown"),
    hair_type: str = Form("short black hair"),
    body_type: str = Form(""),
    shot_angle: str = Form("front_facing"),
    pose_type: str = Form("catalog_standard"),
    # Files
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...)
):
    """Generate high-quality 2K model photos"""
    
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
        "generated_images": [],  # List of (filename, bytes) tuples
        "preview_urls": []
    }
    
    background_tasks.add_task(process_photo_job, job_id)
    
    return JobResponse(
        job_id=job_id,
        status=JobStatus.pending,
        progress=0,
        message="Job started"
    )


async def process_photo_job(job_id: str):
    """Generate high-quality model photos"""
    
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
        
        output_dir = f"outputs/images/{job_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        total_products = len(front_processed)
        
        for i, (front, back) in enumerate(zip(front_processed, back_processed)):
            product_num = i + 1
            job["message"] = f"Generating product {product_num}/{total_products}..."
            
            # Generate front view - HIGH QUALITY
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
            
            # Generate back view - HIGH QUALITY
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
            
            # Save as PNG (lossless) for maximum quality
            front_filename = f"product_{product_num}_front_2K.png"
            back_filename = f"product_{product_num}_back_2K.png"
            
            with open(f"{output_dir}/{front_filename}", "wb") as f:
                f.write(front_model)
            with open(f"{output_dir}/{back_filename}", "wb") as f:
                f.write(back_model)
            
            # Store for download
            job["generated_images"].append((front_filename, front_model))
            job["generated_images"].append((back_filename, back_model))
            
            # Preview URLs
            job["preview_urls"].append(f"/outputs/images/{job_id}/{front_filename}")
            job["preview_urls"].append(f"/outputs/images/{job_id}/{back_filename}")
            
            job["progress"] = 10 + int((i + 1) / total_products * 90)
        
        job["status"] = JobStatus.completed
        job["progress"] = 100
        job["message"] = f"Generated {len(job['generated_images'])} high-quality photos!"
        
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
        preview_images=job.get("preview_urls", []),
        download_url=download_url
    )


@router.get("/download/{job_id}")
async def download_photos_zip(job_id: str):
    """Download all generated photos as a ZIP file (full 2K quality)"""
    
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != JobStatus.completed:
        raise HTTPException(status_code=400, detail="Photos not ready")
    
    if not job["generated_images"]:
        raise HTTPException(status_code=404, detail="No images found")
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, image_bytes in job["generated_images"]:
            # Add each image at FULL QUALITY (no recompression)
            zip_file.writestr(filename, image_bytes)
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={job['brand_name']}_photos_2K.zip"
        }
    )


@router.get("/download/{job_id}/{filename}")
async def download_single_photo(job_id: str, filename: str):
    """Download a single photo at full 2K quality"""
    
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Find the image
    for fname, image_bytes in job["generated_images"]:
        if fname == filename:
            return Response(
                content=image_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
    
    raise HTTPException(status_code=404, detail="Image not found")
