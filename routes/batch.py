"""
Batch API Routes
Separate endpoints for batch catalog generation with 50% cost savings
Does NOT affect existing instant generation routes in catalog.py
"""

import io
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from services.batch_service import BatchService
from services.image_processor import ImageProcessor


router = APIRouter(prefix="/batch", tags=["Batch Processing"])


class BatchJobResponse(BaseModel):
    """Response model for batch job submission"""
    job_id: str
    status: str
    message: str
    estimated_time: str


class BatchStatusResponse(BaseModel):
    """Response model for batch job status"""
    job_id: str
    job_name: str
    collection_name: str
    num_products: int
    status: str
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


@router.post("/submit-catalog", response_model=BatchJobResponse)
async def submit_batch_catalog(
    # Basic fields (same as instant generation)
    category: str = Form(...),
    collection_name: str = Form(...),
    collection_number: str = Form(""),
    theme: str = Form("studio_minimal"),
    
    # Model appearance
    skin_tone: str = Form("fair"),
    body_type: str = Form(""),
    
    # Quality (2K recommended for batch - best value)
    image_quality: str = Form("2K"),
    
    # Customer email for notification (optional)
    customer_email: Optional[str] = Form(None),
    
    # Images
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...),
    logo: Optional[UploadFile] = File(None)
):
    """
    Submit a catalog for batch processing (50% cost savings).
    
    The catalog will be queued for processing and typically completes
    within 1-24 hours. Check status using the returned job_id.
    """
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 10:
        raise HTTPException(status_code=400, detail="Provide 1-10 products")
    
    num_products = len(front_images)
    print(f"📦 Batch catalog request: {num_products} products, theme: {theme}")
    
    try:
        batch_service = BatchService()
        processor = ImageProcessor()
        
        # Read and preprocess images
        front_data = []
        back_data = []
        
        for f in front_images:
            raw = await f.read()
            processed = processor.prepare_garment(raw)
            front_data.append(processed)
        
        for b in back_images:
            raw = await b.read()
            processed = processor.prepare_garment(raw)
            back_data.append(processed)
        
        # Submit batch job
        job_info = await batch_service.submit_batch_catalog(
            front_images=front_data,
            back_images=back_data,
            category=category,
            collection_name=collection_name,
            theme=theme,
            skin_tone=skin_tone,
            body_type=body_type,
            image_quality=image_quality,
            customer_email=customer_email
        )
        
        return BatchJobResponse(
            job_id=job_info.job_id,
            status="pending",
            message=f"Batch job submitted successfully. {len(front_data) * 2 + 2} pages will be generated.",
            estimated_time="1-24 hours (typically 1-2 hours)"
        )
        
    except Exception as e:
        print(f"❌ Batch submission failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Batch submission failed: {str(e)}")


@router.get("/status/{job_id}", response_model=BatchStatusResponse)
async def get_batch_status(job_id: str):
    """
    Check the status of a batch job.
    
    Status values:
    - pending: Job is queued, waiting to start
    - running: Job is being processed
    - succeeded: Job completed, results ready to download
    - failed: Job failed, check error_message
    """
    
    try:
        batch_service = BatchService()
        job_info = await batch_service.check_job_status(job_id)
        
        return BatchStatusResponse(
            job_id=job_info.job_id,
            job_name=job_info.job_name,
            collection_name=job_info.collection_name,
            num_products=job_info.num_products,
            status=job_info.status,
            created_at=job_info.created_at,
            completed_at=job_info.completed_at,
            error_message=job_info.error_message
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/download/{job_id}")
async def download_batch_results(job_id: str):
    """
    Download completed batch results as a ZIP file.
    
    Only available when job status is 'succeeded'.
    """
    
    try:
        batch_service = BatchService()
        
        # First check status
        job_info = await batch_service.check_job_status(job_id)
        
        if job_info.status != 'succeeded':
            raise HTTPException(
                status_code=400, 
                detail=f"Job not ready. Current status: {job_info.status}"
            )
        
        # Download results
        zip_bytes = await batch_service.download_batch_results(job_id)
        
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{job_info.collection_name}_batch_catalog.zip"'
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Download failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/jobs")
async def list_batch_jobs():
    """
    List all batch jobs with their current status.
    """
    
    try:
        batch_service = BatchService()
        jobs = batch_service.list_jobs()
        
        return {
            "jobs": [
                {
                    "job_id": j.job_id,
                    "collection_name": j.collection_name,
                    "num_products": j.num_products,
                    "status": j.status,
                    "created_at": j.created_at,
                    "completed_at": j.completed_at
                }
                for j in jobs
            ]
        }
        
    except Exception as e:
        print(f"❌ List jobs failed: {e}")
        raise HTTPException(status_code=500, detail=f"List jobs failed: {str(e)}")
