"""
Bono Catalog - AI Virtual Try-On & Catalog Generation System
FastAPI Backend
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from routes.catalog import router as catalog_router
from routes.batch import router as batch_router

load_dotenv()

app = FastAPI(
    title="Bono Catalog API",
    description="AI-powered virtual try-on and catalog generation system",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create output directories
os.makedirs("outputs/images", exist_ok=True)
os.makedirs("outputs/catalogs", exist_ok=True)
os.makedirs("batch_jobs", exist_ok=True)
os.makedirs("batch_results", exist_ok=True)

# Mount static files for serving generated content
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Include routers
app.include_router(catalog_router, prefix="/api", tags=["catalog"])
app.include_router(batch_router, prefix="/api", tags=["batch"])


@app.get("/")
async def root():
    return {
        "name": "Bono Catalog API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
