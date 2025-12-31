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
from services.upscaler import upscale_to_target


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
                    creative_direction=creative_direction,
                    image_quality=image_quality
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
                    creative_direction=creative_direction,
                    image_quality=image_quality
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
# MASTER CATALOG FEATURE (ENHANCED)
# ============================================

# Layout types for catalog pages
LAYOUT_TYPES = ['front', 'back', 'combo', 'fabric_closeup', 'detail_highlight', 'model_callout']

# Assorted options for variety in catalog
CATALOG_POSES = ["catalog_standard", "hands_on_hips", "hands_in_pockets", "arms_crossed", "walking", "leaning_wall", "editorial_dramatic"]
CATALOG_PROPS = ["none", "sunglasses", "cap", "watch", "headphones"]
CATALOG_LAYOUTS = ["hero_bottom", "split_vertical", "magazine_cover", "overlay_gradient", "framed_border", "product_focus", "lookbook_spread"]


def plan_catalog_pages(num_products: int, max_pages: int = 10) -> list:
    """
    Plan smart layout distribution for catalog pages.
    Returns list of tuples: (layout_type, product_index, additional_data)
    
    Target: 10-12 pages for up to 10 products (OPTIMIZED for cost)
    - Collages are 2x efficient (front+back in 1 page)
    - More collages = fewer total generations = lower cost
    """
    pages = []
    
    # For very few products, show all views in collages
    if num_products <= 2:
        for i in range(num_products):
            pages.append(('collage', i, {'page_number': i + 1}))
        # Add one fabric closeup
        pages.append(('fabric_v2', 0, {'page_number': num_products + 1}))
        return pages
    
    # For 3-10 products, use smart distribution
    content_pages = max_pages - 2  # Reserve for cover and thank you (= 8 pages)
    
    # COST-OPTIMIZED Distribution:
    # - More collages (each shows front+back = 2 views for 1 generation)
    # - 1 fabric close-up only
    # - Fewer single pages
    
    # Use collages for most products (each collage = 2 views, 1 generation)
    num_collages = min(num_products, 4)  # Up to 4 collages (= 8 product views)
    num_fabric = 1  # Only 1 fabric shot to save cost
    
    # Remaining slots for single views
    remaining = content_pages - num_collages - num_fabric
    
    used_products = set()
    page_idx = 0
    
    # 1. Add collage pages (front+back in creative compositions)
    for i in range(num_collages):
        prod_idx = i % num_products
        pages.append(('collage', prod_idx, {'page_number': i + 1}))
        used_products.add(prod_idx)
        page_idx += 1
    
    # 2. Add fabric closeup pages (artsy fabric shots)
    fabric_idx = num_collages
    for i in range(num_fabric):
        prod_idx = (fabric_idx + i) % num_products
        pages.append(('fabric_v2', prod_idx, {'page_number': page_idx + 1}))
        page_idx += 1
    
    # 3. Fill remaining with single product pages (alternating front/back)
    view_toggle = True
    current_product = 0
    
    for i in range(remaining):
        if page_idx >= content_pages:
            break
        
        prod_idx = current_product % num_products
        view = 'front' if view_toggle else 'back'
        
        pages.append(('single_v2', prod_idx, {'view': view, 'page_number': page_idx + 1}))
        
        view_toggle = not view_toggle
        if not view_toggle:  # After back view, move to next product
            current_product += 1
        page_idx += 1
    
    return pages


def create_pdf_from_images(image_bytes_list: list) -> bytes:
    """Create a PDF from a list of image bytes (one image per page)"""
    from PIL import Image
    from io import BytesIO
    
    if not image_bytes_list:
        raise ValueError("No images to create PDF")
    
    # Convert all images to PIL and RGB mode
    pil_images = []
    for img_bytes in image_bytes_list:
        img = Image.open(BytesIO(img_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        pil_images.append(img)
    
    # Create PDF
    pdf_buffer = BytesIO()
    pil_images[0].save(
        pdf_buffer, 
        'PDF', 
        save_all=True, 
        append_images=pil_images[1:] if len(pil_images) > 1 else []
    )
    
    return pdf_buffer.getvalue()



@router.post("/generate-catalog")
async def generate_master_catalog(
    # Basic fields
    category: CategoryEnum = Form(...),
    collection_name: str = Form(...),
    collection_number: str = Form(""),  # Original field name from frontend
    theme: str = Form("studio_minimal"),
    
    # Model appearance
    skin_tone: str = Form("fair"),
    body_type: str = Form(""),
    
    # Quality
    image_quality: str = Form("4K"),
    
    # Images
    front_images: List[UploadFile] = File(...),
    back_images: List[UploadFile] = File(...),
    logo: Optional[UploadFile] = File(None)
):
    """Generate enhanced Master Catalog with smart layout distribution"""
    
    if len(front_images) != len(back_images):
        raise HTTPException(status_code=400, detail="Number of front and back images must match")
    
    if len(front_images) < 1 or len(front_images) > 10:
        raise HTTPException(status_code=400, detail="Provide 1-10 products")
    
    num_products = len(front_images)
    
    # Parse quality selection - 5 options:
    # 1K          = Generate at 1K, no upscale
    # 2K          = Generate at 2K pure, no upscale
    # 4K          = Generate at 4K pure, no upscale
    # 2K_UPSCALE  = Generate at 2K, upscale to 4K
    # 4K_UPSCALE  = Generate at 4K, upscale to 8K
    
    if image_quality == "2K_UPSCALE":
        internal_quality = "2K"
        should_upscale = True
        upscale_target = "4K"
    elif image_quality == "4K_UPSCALE":
        internal_quality = "4K"
        should_upscale = True
        upscale_target = "8K"
    else:
        # Pure modes: 1K, 2K, 4K - use directly, no upscale
        internal_quality = image_quality
        should_upscale = False
        upscale_target = None
    
    print(f"📊 Catalog: {num_products} products, theme: {theme}")
    print(f"🎨 Quality: {image_quality} (generate: {internal_quality}, upscale: {should_upscale})")
    
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
        
        # ========== 1. COVER PAGE ==========
        print("Generating enhanced cover page...")
        cover = await gemini.generate_catalog_cover_enhanced(
            logo_image=logo_data,
            collection_name=collection_name,
            style_number=collection_number,  # Use collection_number from frontend
            theme=theme,
            image_quality=internal_quality  # Use 2K internally
        )
        generated_images.append(("00_cover.png", cover))
        
        # ========== 2. PRODUCT PAGES (Smart Layout) ==========
        page_plan = plan_catalog_pages(num_products, max_pages=10)
        print(f"Page plan: {len(page_plan)} content pages")
        
        for page_num, (layout_type, prod_idx, extra) in enumerate(page_plan, start=1):
            print(f"Page {page_num}/{len(page_plan)}: {layout_type} for product {prod_idx + 1}")
            
            try:
                if layout_type == 'collage':
                    # V2: Creative collage layout (front + back)
                    page_number = extra.get('page_number', page_num)
                    page = await gemini.generate_collage_layout(
                        front_image=front_processed[prod_idx],
                        back_image=back_processed[prod_idx],
                        category=category,
                        skin_tone=skin_tone,
                        body_type=body_type,
                        theme=theme,
                        page_number=page_number,
                        image_quality=internal_quality  # Use 2K internally
                    )
                    generated_images.append((f"{page_num:02d}_collage_product_{prod_idx + 1}.png", page))
                
                elif layout_type == 'fabric_v2':
                    # V2: Artistic fabric close-up (no brand text)
                    page_number = extra.get('page_number', page_num)
                    page = await gemini.generate_fabric_closeup_v2(
                        garment_image=front_processed[prod_idx],
                        theme=theme,
                        page_number=page_number,
                        image_quality=internal_quality  # Use 2K internally
                    )
                    generated_images.append((f"{page_num:02d}_fabric_art_{prod_idx + 1}.png", page))
                
                elif layout_type == 'single_v2':
                    # V2: Single product page with variety (no brand text, AI phrase)
                    view = extra.get('view', 'front')
                    page_number = extra.get('page_number', page_num)
                    garment = front_processed[prod_idx] if view == 'front' else back_processed[prod_idx]
                    
                    page = await gemini.generate_catalog_product_page_v2(
                        garment_image=garment,
                        category=category,
                        view=view,
                        skin_tone=skin_tone,
                        body_type=body_type,
                        theme=theme,
                        page_number=page_number,
                        total_pages=len(page_plan),
                        image_quality=internal_quality  # Use 2K internally
                    )
                    generated_images.append((f"{page_num:02d}_{view}_product_{prod_idx + 1}.png", page))
                
                # Legacy fallback for old layout types
                elif layout_type == 'combo':
                    page = await gemini.generate_combo_layout(
                        front_image=front_processed[prod_idx],
                        back_image=back_processed[prod_idx],
                        logo_image=logo_data,
                        category=category,
                        skin_tone=skin_tone,
                        body_type=body_type,
                        theme=theme,
                        collection_name=collection_name,
                        image_quality=internal_quality  # Use 2K internally
                    )
                    generated_images.append((f"{page_num:02d}_combo_product_{prod_idx + 1}.png", page))
                
                elif layout_type in ['front', 'back']:
                    view = layout_type
                    garment = front_processed[prod_idx] if view == 'front' else back_processed[prod_idx]
                    page = await gemini.generate_catalog_product_page_v2(
                        garment_image=garment,
                        category=category,
                        view=view,
                        skin_tone=skin_tone,
                        body_type=body_type,
                        theme=theme,
                        page_number=page_num,
                        total_pages=len(page_plan),
                        image_quality=internal_quality  # Use 2K internally
                    )
                    generated_images.append((f"{page_num:02d}_{view}_product_{prod_idx + 1}.png", page))
                    
            except Exception as e:
                print(f"Failed to generate {layout_type} for product {prod_idx + 1}: {e}")
                import traceback
                traceback.print_exc()
                # Continue with other pages
                continue
        
        # ========== 3. THANK YOU PAGE ==========
        print("Generating thank you page...")
        thankyou = await gemini.generate_catalog_thankyou_simple(
            logo_image=logo_data,
            collection_name=collection_name,
            theme=theme,
            image_quality=internal_quality  # Use 2K internally
        )
        generated_images.append(("99_thankyou.png", thankyou))
        
        print(f"Generated {len(generated_images)} images")
        
        # ========== 4. UPSCALE IF NEEDED ==========
        if should_upscale:
            print(f"📐 Upscaling images to {upscale_target}...")
            upscaled_images = []
            for filename, image_bytes in generated_images:
                try:
                    upscaled = upscale_to_target(image_bytes, upscale_target)
                    upscaled_images.append((filename, upscaled))
                except Exception as upscale_error:
                    print(f"⚠️ Upscale failed for {filename}: {upscale_error}")
                    upscaled_images.append((filename, image_bytes))  # Use original
            generated_images = upscaled_images
            print(f"✅ Upscaled {len(generated_images)} images to {upscale_target}")
        
        print("Creating ZIP and PDF...")
        
        # ========== 5. CREATE PDF ==========
        print("Creating PDF from images...")
        try:
            image_bytes_only = [img_bytes for _, img_bytes in generated_images]
            pdf_bytes = create_pdf_from_images(image_bytes_only)
            print(f"PDF created: {len(pdf_bytes)} bytes")
        except Exception as pdf_error:
            print(f"PDF creation failed: {pdf_error}")
            pdf_bytes = None
        
        # ========== 5. CREATE ZIP WITH IMAGES + PDF ==========
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, image_bytes in generated_images:
                print(f"Adding: {filename} ({len(image_bytes)} bytes)")
                zf.writestr(filename, image_bytes)
            
            # Add PDF if created successfully
            if pdf_bytes:
                pdf_filename = f"{collection_name or 'catalog'}_complete.pdf"
                safe_pdf_name = "".join(c for c in pdf_filename if c.isalnum() or c in ' -_.').strip()
                zf.writestr(safe_pdf_name, pdf_bytes)
                print(f"Added PDF: {safe_pdf_name}")
        
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

