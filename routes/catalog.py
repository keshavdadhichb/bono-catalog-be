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
        "text_fields": ["headline", "price", "sizes"],
        "preview": "E-commerce style with product details"
    },
    "diagonal_split": {
        "name": "Diagonal Split",
        "description": "Dynamic diagonal divide with text",
        "text_fields": ["headline", "subtext"],
        "preview": "Diagonal composition for dynamic energy"
    },
    "centered_minimal": {
        "name": "Centered Minimal",
        "description": "Model centered, text above and below",
        "text_fields": ["brand", "headline"],
        "preview": "Balanced, gallery-style presentation"
    },
    "story_card": {
        "name": "Story Card",
        "description": "Instagram story style - 9:16 full bleed",
        "text_fields": ["headline", "cta"],
        "preview": "Social media optimized format"
    },
    "lookbook_spread": {
        "name": "Lookbook Spread",
        "description": "Editorial lookbook with multiple elements",
        "text_fields": ["brand", "headline", "subtext", "price"],
        "preview": "Rich editorial with all text elements"
    },
    "orange_diagonal": {
        "name": "Orange Diagonal",
        "description": "BONO style - split background with diagonal banner",
        "text_fields": ["brand", "headline", "subtext", "tagline"],
        "preview": "White/orange split with dynamic diagonal element"
    },
    "yellow_vibrant": {
        "name": "Yellow Vibrant",
        "description": "Modern pop - bright yellow with purple accents",
        "text_fields": ["headline", "subtext", "brand"],
        "preview": "Bold yellow background with geometric purple elements"
    },
    "pink_elegant": {
        "name": "Pink Elegant",
        "description": "Runway style - soft pink with elegant typography",
        "text_fields": ["headline", "subtext", "brand"],
        "preview": "Blush pink with flowing script and vertical text bars"
    },
    "orange_framed": {
        "name": "Orange Framed",
        "description": "Premium frame - deep orange with white frame",
        "text_fields": ["headline", "tagline", "brand"],
        "preview": "Deep orange with decorative white frame and layered text"
    },
    "minimalist_editorial": {
        "name": "Minimalist Editorial",
        "description": "High-end magazine spread with white space",
        "text_fields": ["headline", "subtext"],
        "preview": "Off-white background, thin serif typography, vertical divider"
    },
    "urban_brutalist": {
        "name": "Urban Brutalist",
        "description": "Edgy streetwear with concrete texture",
        "text_fields": ["headline", "subtext"],
        "preview": "Concrete background, distressed text, technical overlays"
    },
    "warm_earth": {
        "name": "Warm Earth Tones",
        "description": "Organic natural feel with earth colors",
        "text_fields": ["headline", "subtext", "tagline"],
        "preview": "Terracotta, sage, sand collage with botanical elements"
    },
    "dark_luxury": {
        "name": "Dark Mode Luxury",
        "description": "Premium dark with gold accents",
        "text_fields": ["headline", "subtext"],
        "preview": "Charcoal background with metallic gold typography"
    },
    "dynamic_typography": {
        "name": "Dynamic Typography",
        "description": "Text as major visual element",
        "text_fields": ["headline", "subtext"],
        "preview": "Large translucent text overlay, energetic modern feel"
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
    image_quality: str = Form("4K"),  # Options: "1K", "2K", "4K"
    
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
                    text_content=text_content,
                    image_quality=image_quality
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


# ============================================
# MASTER CATALOG FEATURE
# ============================================

# Hardcoded contact details
BONO_CONTACT = {
    "company": "BONOSTYLE CREATIONS LLP",
    "email": "contact@bonostyle.in",
    "phone": "(+91) 9789116300",
    "address": "3238C, 2nd Street, P.N Road, Anna Nagar, Tiruppur, Tamil Nadu - 641602",
    "website": "bonostyle.in"
}

# Assorted options for variety in catalog
CATALOG_POSES = ["catalog_standard", "hands_on_hips", "hands_in_pockets", "arms_crossed", "walking", "leaning_wall", "editorial_dramatic"]
CATALOG_PROPS = ["none", "sunglasses", "cap", "watch", "headphones"]
CATALOG_LAYOUTS = ["hero_bottom", "split_vertical", "magazine_cover", "overlay_gradient", "framed_border", "product_focus", "lookbook_spread"]


@router.post("/generate-catalog")
async def generate_master_catalog(
    # Basic fields
    category: CategoryEnum = Form(...),
    collection_name: str = Form(...),
    collection_number: str = Form(""),
    theme: str = Form("studio_minimal"),
    
    # Model appearance
    skin_tone: str = Form("fair"),
    body_type: str = Form(""),
    
    # Optional text fields (10 total, all optional)
    text_tagline: str = Form(""),
    text_season: str = Form(""),
    text_year: str = Form(""),
    text_price_range: str = Form(""),
    text_fabric: str = Form(""),
    text_brand_message: str = Form(""),
    text_custom_1: str = Form(""),
    text_custom_2: str = Form(""),
    text_custom_3: str = Form(""),
    text_custom_4: str = Form(""),
    
    # Images
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...),
    logo: Optional[UploadFile] = File(None)
):
    """Generate a complete Master Catalog: Cover + N product pages + Thank You page"""
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 20:
        raise HTTPException(status_code=400, detail="Provide 1-20 products")
    
    num_products = len(front_images)
    print(f"Master Catalog: {num_products} products, theme: {theme}")
    
    try:
        gemini = GeminiClient()
        processor = ImageProcessor()
        
        # Read uploads
        front_data = [await f.read() for f in front_images]
        back_data = [await b.read() for b in back_images]
        logo_data = await logo.read() if logo else None
        
        # Preprocess garments
        front_processed = [processor.prepare_garment(f) for f in front_data]
        back_processed = [processor.prepare_garment(b) for b in back_data]
        
        generated_images = []
        
        # Gather optional texts
        text_content = {
            "tagline": text_tagline,
            "season": text_season,
            "year": text_year,
            "price_range": text_price_range,
            "fabric": text_fabric,
            "brand_message": text_brand_message,
            "custom_1": text_custom_1,
            "custom_2": text_custom_2,
            "custom_3": text_custom_3,
            "custom_4": text_custom_4
        }
        
        # ========== 1. COVER PAGE ==========
        print("Generating cover page...")
        cover = await gemini.generate_catalog_cover(
            logo_image=logo_data,
            collection_name=collection_name,
            collection_number=collection_number,
            theme=theme,
            text_content=text_content
        )
        generated_images.append(("00_cover.png", cover))
        
        # ========== 2. PRODUCT PAGES (N pages, assorted styles) ==========
        for i, (front, back) in enumerate(zip(front_processed, back_processed)):
            page_num = i + 1
            
            # Cycle through poses, props, layouts for variety
            pose = CATALOG_POSES[i % len(CATALOG_POSES)]
            prop = CATALOG_PROPS[i % len(CATALOG_PROPS)]
            layout = CATALOG_LAYOUTS[i % len(CATALOG_LAYOUTS)]
            
            print(f"Generating product {page_num}/{num_products} - layout: {layout}")
            
            # Generate FRONT view
            front_page = await gemini.generate_marketing_poster(
                garment_image=front,
                logo_image=logo_data,
                category=category,
                skin_tone=skin_tone,
                body_type=body_type,
                marketing_theme=theme,
                prop=prop,
                pose_type=pose,
                shot_angle="front_facing",
                layout_style=layout,
                text_content={
                    "brand": collection_name,
                    "headline": text_content.get("tagline", ""),
                    "price": text_content.get("price_range", ""),
                    "subtext": text_content.get("fabric", "")
                }
            )
            generated_images.append((f"{page_num:02d}_product_{page_num}_front.png", front_page))
            
            # Generate BACK view with different layout
            back_layout = CATALOG_LAYOUTS[(i + 3) % len(CATALOG_LAYOUTS)]
            back_pose = CATALOG_POSES[(i + 2) % len(CATALOG_POSES)]
            
            back_page = await gemini.generate_marketing_poster(
                garment_image=back,
                logo_image=logo_data,
                category=category,
                skin_tone=skin_tone,
                body_type=body_type,
                marketing_theme=theme,
                prop="none",
                pose_type=back_pose,
                shot_angle="back_view",
                layout_style=back_layout,
                text_content={
                    "brand": collection_name,
                    "subtext": "Back View"
                }
            )
            generated_images.append((f"{page_num:02d}_product_{page_num}_back.png", back_page))
        
        # ========== 3. THANK YOU PAGE ==========
        print("Generating thank you page...")
        thankyou = await gemini.generate_catalog_thankyou(
            logo_image=logo_data,
            collection_name=collection_name,
            theme=theme,
            product_images=front_processed[:6],  # Max 6 for collage
            contact_info=BONO_CONTACT
        )
        generated_images.append(("99_thankyou.png", thankyou))
        
        print(f"Generated {len(generated_images)} images, creating ZIP...")
        
        # Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, image_bytes in generated_images:
                print(f"Adding: {filename} ({len(image_bytes)} bytes)")
                zf.writestr(filename, image_bytes)
        
        zip_buffer.seek(0)
        
        safe_name = "".join(c for c in collection_name if c.isalnum() or c in ' -_').strip() or "catalog"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}_catalog.zip"'
            }
        )
        
    except Exception as e:
        print(f"Catalog generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Catalog generation failed: {str(e)}")

