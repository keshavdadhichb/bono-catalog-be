"""
Batch Service for Gemini Batch API
Handles batch image generation with 50% cost savings
Completely separate from instant generation - does not affect existing code
"""

import os
import json
import time
import base64
import asyncio
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from PIL import Image

from google import genai
from google.genai import types


# Directory to store batch job metadata and results
BATCH_JOBS_DIR = Path(__file__).parent.parent / "batch_jobs"
BATCH_JOBS_DIR.mkdir(parents=True, exist_ok=True)

BATCH_RESULTS_DIR = Path(__file__).parent.parent / "batch_results"
BATCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BatchJobInfo:
    """Stores information about a batch job"""
    job_id: str
    job_name: str
    collection_name: str
    num_products: int
    status: str  # pending, running, succeeded, failed
    created_at: str
    completed_at: Optional[str] = None
    result_file: Optional[str] = None
    error_message: Optional[str] = None
    customer_email: Optional[str] = None


class BatchService:
    """
    Service for handling Gemini Batch API operations.
    This is COMPLETELY SEPARATE from the instant generation in gemini_client.py
    """
    
    # Model for batch image generation
    BATCH_MODEL = "gemini-2.5-flash-image"  # or "gemini-3-pro-image-preview"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        self.client = genai.Client(api_key=self.api_key)
    
    def _save_job_info(self, job_info: BatchJobInfo) -> None:
        """Save job info to disk"""
        job_file = BATCH_JOBS_DIR / f"{job_info.job_id}.json"
        with open(job_file, 'w') as f:
            json.dump(asdict(job_info), f, indent=2)
    
    def _load_job_info(self, job_id: str) -> Optional[BatchJobInfo]:
        """Load job info from disk"""
        job_file = BATCH_JOBS_DIR / f"{job_id}.json"
        if not job_file.exists():
            return None
        
        with open(job_file, 'r') as f:
            data = json.load(f)
            return BatchJobInfo(**data)
    
    def _create_catalog_requests(
        self,
        front_images: List[bytes],
        back_images: List[bytes],
        category: str,
        collection_name: str,
        theme: str,
        skin_tone: str,
        body_type: str,
        image_quality: str
    ) -> List[Dict]:
        """
        Create list of generation requests for batch processing.
        Each request is a dictionary matching GenerateContentRequest format.
        """
        from services.gemini_client import (
            MODEL_CONFIG, SKIN_TONES, THEME_CONFIG,
            STRICT_GARMENT_RULES, CREATIVE_PHRASES, CATALOG_LAYOUT_STYLES
        )
        
        requests = []
        num_products = len(front_images)
        
        config = MODEL_CONFIG.get(category, MODEL_CONFIG["teen_boy"])
        skin_desc = SKIN_TONES.get(skin_tone, SKIN_TONES.get("fair", skin_tone))
        theme_config = THEME_CONFIG.get(theme, THEME_CONFIG["studio_minimal"])
        build = body_type if body_type else config["default_build"]
        
        page_num = 0
        
        # Cover page request
        page_num += 1
        cover_prompt = f"""Generate a STUNNING CATALOG COVER PAGE for "{collection_name}".
        
This is a COVER PAGE - NO MODEL, just branding.
- Collection name large and prominent
- Elegant fashion typography
- Theme: {theme_config['background_desc']}
- Mood: {theme_config['mood']}
- Professional, high-end fashion catalog quality
"""
        requests.append({
            "key": f"page_{page_num:02d}_cover",
            "request": {
                "contents": [{"parts": [{"text": cover_prompt}]}],
                "generation_config": {
                    "responseModalities": ["IMAGE"],
                }
            }
        })
        
        # Product pages (collages and singles)
        for prod_idx in range(num_products):
            page_num += 1
            layout = CATALOG_LAYOUT_STYLES[page_num % len(CATALOG_LAYOUT_STYLES)]
            phrase = CREATIVE_PHRASES[(page_num * 3) % len(CREATIVE_PHRASES)]
            
            # Front image as base64
            front_b64 = base64.b64encode(front_images[prod_idx]).decode('utf-8')
            back_b64 = base64.b64encode(back_images[prod_idx]).decode('utf-8')
            
            prompt = f"""You are a world-class Fashion Photographer creating a PREMIUM CATALOG PAGE.

{STRICT_GARMENT_RULES}

PAGE {page_num} - FRONT VIEW

=== LAYOUT: {layout['name']} ===
{layout['description']}
- Model position: {layout['model_position']}

=== MODEL DETAILS ===
- Subject: {config['description']}, {config['age_range']}
- Skin: {skin_desc}
- Build: {build}
- Pose: Natural, confident

=== CREATIVE PHRASE ===
Small, elegant text: "{phrase}"

=== THEME ===
- Background: {theme_config['background_desc']}
- Lighting: {theme_config['lighting']}
- Mood: {theme_config['mood']}

Generate professional catalog page. PRESERVE GARMENT EXACTLY."""
            
            requests.append({
                "key": f"page_{page_num:02d}_product_{prod_idx + 1}_front",
                "request": {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/png", "data": front_b64}}
                        ]
                    }],
                    "generation_config": {
                        "responseModalities": ["IMAGE"],
                    }
                }
            })
            
            # Back view
            page_num += 1
            phrase = CREATIVE_PHRASES[(page_num * 3 + 7) % len(CREATIVE_PHRASES)]
            
            back_prompt = f"""You are a world-class Fashion Photographer creating a PREMIUM CATALOG PAGE.

{STRICT_GARMENT_RULES}

PAGE {page_num} - BACK VIEW

=== MODEL DETAILS ===
- Subject: {config['description']}, {config['age_range']}
- Skin: {skin_desc}
- Build: {build}
- View: BACK view showing back of garment
- Pose: Natural, showing back of outfit

=== CREATIVE PHRASE ===
Small, elegant text: "{phrase}"

=== THEME ===
- Background: {theme_config['background_desc']}
- Lighting: {theme_config['lighting']}
- Mood: {theme_config['mood']}

Generate professional catalog page. PRESERVE GARMENT EXACTLY."""
            
            requests.append({
                "key": f"page_{page_num:02d}_product_{prod_idx + 1}_back",
                "request": {
                    "contents": [{
                        "parts": [
                            {"text": back_prompt},
                            {"inline_data": {"mime_type": "image/png", "data": back_b64}}
                        ]
                    }],
                    "generation_config": {
                        "responseModalities": ["IMAGE"],
                    }
                }
            })
        
        # Thank you page
        page_num += 1
        thankyou_prompt = f"""Generate a beautiful THANK YOU page for "{collection_name}" catalog.
        
- Elegant "Thank You" text
- Collection name
- Theme: {theme_config['background_desc']}
- Professional fashion catalog quality
- NO MODEL in this image
"""
        requests.append({
            "key": f"page_{page_num:02d}_thankyou",
            "request": {
                "contents": [{"parts": [{"text": thankyou_prompt}]}],
                "generation_config": {
                    "responseModalities": ["IMAGE"],
                }
            }
        })
        
        return requests
    
    async def submit_batch_catalog(
        self,
        front_images: List[bytes],
        back_images: List[bytes],
        category: str,
        collection_name: str,
        theme: str = "studio_minimal",
        skin_tone: str = "fair",
        body_type: str = "",
        image_quality: str = "2K",
        customer_email: Optional[str] = None
    ) -> BatchJobInfo:
        """
        Submit a catalog generation as a batch job.
        Returns job info with ID to track status.
        """
        
        # Generate unique job ID
        job_id = f"catalog_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(front_images)}prod"
        
        print(f"📦 Creating batch job: {job_id}")
        
        # Create requests for all catalog pages
        requests = self._create_catalog_requests(
            front_images=front_images,
            back_images=back_images,
            category=category,
            collection_name=collection_name,
            theme=theme,
            skin_tone=skin_tone,
            body_type=body_type,
            image_quality=image_quality
        )
        
        print(f"📝 Generated {len(requests)} page requests")
        
        # Create JSONL file
        jsonl_path = BATCH_JOBS_DIR / f"{job_id}_requests.jsonl"
        with open(jsonl_path, 'w') as f:
            for req in requests:
                f.write(json.dumps(req) + "\n")
        
        print(f"📄 Created JSONL file: {jsonl_path}")
        
        # Upload file to Gemini
        uploaded_file = await asyncio.to_thread(
            self.client.files.upload,
            file=str(jsonl_path),
            config=types.UploadFileConfig(
                display_name=f'{job_id}_requests',
                mime_type='application/jsonl'
            )
        )
        
        print(f"☁️ Uploaded file: {uploaded_file.name}")
        
        # Create batch job
        batch_job = await asyncio.to_thread(
            self.client.batches.create,
            model=self.BATCH_MODEL,
            src=uploaded_file.name,
            config={'display_name': job_id}
        )
        
        print(f"🚀 Created batch job: {batch_job.name}")
        
        # Save job info
        job_info = BatchJobInfo(
            job_id=job_id,
            job_name=batch_job.name,
            collection_name=collection_name,
            num_products=len(front_images),
            status="pending",
            created_at=datetime.now().isoformat(),
            customer_email=customer_email
        )
        self._save_job_info(job_info)
        
        return job_info
    
    async def check_job_status(self, job_id: str) -> BatchJobInfo:
        """
        Check the status of a batch job.
        """
        job_info = self._load_job_info(job_id)
        if not job_info:
            raise ValueError(f"Job not found: {job_id}")
        
        # If already completed, return saved info
        if job_info.status in ['succeeded', 'failed']:
            return job_info
        
        # Check with Gemini API
        batch_job = await asyncio.to_thread(
            self.client.batches.get,
            name=job_info.job_name
        )
        
        # Map Gemini state to our status
        state_mapping = {
            'JOB_STATE_PENDING': 'pending',
            'JOB_STATE_RUNNING': 'running',
            'JOB_STATE_SUCCEEDED': 'succeeded',
            'JOB_STATE_FAILED': 'failed',
            'JOB_STATE_CANCELLED': 'failed',
            'JOB_STATE_EXPIRED': 'failed',
        }
        
        job_info.status = state_mapping.get(batch_job.state.name, 'pending')
        
        if job_info.status == 'succeeded':
            job_info.completed_at = datetime.now().isoformat()
            job_info.result_file = batch_job.dest.file_name
        elif job_info.status == 'failed':
            job_info.error_message = str(getattr(batch_job, 'error', 'Unknown error'))
        
        self._save_job_info(job_info)
        
        return job_info
    
    async def download_batch_results(self, job_id: str) -> bytes:
        """
        Download completed batch results as a ZIP file.
        """
        job_info = await self.check_job_status(job_id)
        
        if job_info.status != 'succeeded':
            raise ValueError(f"Job not completed: {job_info.status}")
        
        if not job_info.result_file:
            raise ValueError("No result file available")
        
        # Download result file
        print(f"📥 Downloading results: {job_info.result_file}")
        result_content = await asyncio.to_thread(
            self.client.files.download,
            file=job_info.result_file
        )
        
        # Parse JSONL and extract images
        images = []
        result_text = result_content.decode('utf-8')
        
        for line in result_text.splitlines():
            if not line.strip():
                continue
            
            parsed = json.loads(line)
            key = parsed.get('key', f'image_{len(images)}')
            
            if 'response' in parsed and parsed['response']:
                try:
                    parts = parsed['response']['candidates'][0]['content']['parts']
                    for part in parts:
                        if part.get('inlineData'):
                            img_data = base64.b64decode(part['inlineData']['data'])
                            images.append((f"{key}.png", img_data))
                            break
                except (KeyError, IndexError) as e:
                    print(f"⚠️ Failed to parse image from {key}: {e}")
            elif 'error' in parsed:
                print(f"⚠️ Error in {key}: {parsed['error']}")
        
        print(f"📸 Extracted {len(images)} images")
        
        # Create ZIP file
        import zipfile
        from io import BytesIO
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, img_bytes in images:
                zf.writestr(filename, img_bytes)
        
        # Save to results directory
        result_zip_path = BATCH_RESULTS_DIR / f"{job_id}_catalog.zip"
        with open(result_zip_path, 'wb') as f:
            f.write(zip_buffer.getvalue())
        
        print(f"💾 Saved results to: {result_zip_path}")
        
        return zip_buffer.getvalue()
    
    def list_jobs(self) -> List[BatchJobInfo]:
        """List all batch jobs"""
        jobs = []
        for job_file in BATCH_JOBS_DIR.glob("*.json"):
            if not job_file.name.endswith("_requests.json"):
                with open(job_file, 'r') as f:
                    data = json.load(f)
                    jobs.append(BatchJobInfo(**data))
        
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)
