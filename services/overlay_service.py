"""
Overlay Service - Professional Text/Logo Overlay
PIL-based overlay for PERFECT typography on marketing posters

This service applies text and logos AFTER AI generation to ensure:
- 100% accurate spelling
- Crisp, professional typography
- Perfect alignment and positioning
"""

import io
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple
import os


class OverlayService:
    """Apply professional text and logo overlays to generated images"""
    
    def __init__(self):
        self.fonts_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
    
    def _get_font(self, font_type: str, size: int) -> ImageFont.FreeTypeFont:
        """Get font with fallback to default"""
        # On Vercel, we use default font
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            pass
        try:
            return ImageFont.truetype("Arial Bold", size)
        except:
            pass
        try:
            return ImageFont.truetype("Helvetica", size)
        except:
            pass
        # Ultimate fallback
        return ImageFont.load_default()
    
    def apply_poster_overlay(
        self,
        image_bytes: bytes,
        hero_text: str = "",
        sub_text: str = "",
        corner_text: str = "",
        size_text: str = "",
        price_text: str = "",
        logo_bytes: Optional[bytes] = None,
        text_color: str = "white"
    ) -> bytes:
        """
        Apply complete poster overlay with all text elements
        
        Text Positions:
        - Hero Text: Large, centered, bottom third of image
        - Sub Text: Below hero text, smaller
        - Corner Text: Top left corner (brand name)
        - Size Text: Bottom left
        - Price Text: Bottom right
        - Logo: Top right corner
        
        Args:
            image_bytes: The base AI-generated image
            hero_text: Main headline (e.g., "RELAXED FIT")
            sub_text: Subtitle (e.g., "Premium Cotton")
            corner_text: Brand/tagline (e.g., "BONO")
            size_text: Product size (e.g., "S M L XL XXL")
            price_text: Price (e.g., "₹1,299")
            logo_bytes: Logo image bytes
            text_color: "white" or "black"
        """
        # Open and prepare image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        width, height = img.size
        
        # Create transparent overlay
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Color setup
        if text_color == "white":
            main_color = (255, 255, 255, 255)
            shadow_color = (0, 0, 0, 150)
        else:
            main_color = (20, 20, 20, 255)
            shadow_color = (255, 255, 255, 100)
        
        padding = int(width * 0.04)  # 4% padding from edges
        
        # === CORNER TEXT (Top Left) ===
        if corner_text:
            corner_font = self._get_font("bold", int(width * 0.05))
            self._draw_text_with_shadow(
                draw, corner_text.upper(), corner_font,
                x=padding, y=padding,
                color=main_color, shadow_color=shadow_color,
                align="left"
            )
        
        # === LOGO (Top Right) ===
        if logo_bytes:
            try:
                logo = Image.open(io.BytesIO(logo_bytes))
                if logo.mode != 'RGBA':
                    logo = logo.convert('RGBA')
                
                # Size: 8% of image width
                logo_width = int(width * 0.08)
                ratio = logo.width / logo.height
                logo_height = int(logo_width / ratio)
                logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
                
                # Position: top right
                logo_x = width - logo_width - padding
                logo_y = padding
                img.paste(logo, (logo_x, logo_y), logo)
            except Exception as e:
                print(f"Logo overlay failed: {e}")
        
        # === HERO TEXT (Bottom center, large) ===
        if hero_text:
            hero_font = self._get_font("bold", int(width * 0.12))  # 12% of width
            hero_y = height - int(height * 0.25)  # 25% from bottom
            self._draw_centered_text(
                draw, hero_text.upper(), hero_font,
                width, hero_y,
                color=main_color, shadow_color=shadow_color
            )
        
        # === SUB TEXT (Below hero) ===
        if sub_text:
            sub_font = self._get_font("regular", int(width * 0.04))  # 4% of width
            sub_y = height - int(height * 0.15)  # 15% from bottom
            self._draw_centered_text(
                draw, sub_text, sub_font,
                width, sub_y,
                color=main_color, shadow_color=shadow_color
            )
        
        # === SIZE TEXT (Bottom Left) ===
        if size_text:
            size_font = self._get_font("regular", int(width * 0.03))
            size_y = height - padding - int(width * 0.03)
            self._draw_text_with_shadow(
                draw, size_text, size_font,
                x=padding, y=size_y,
                color=main_color, shadow_color=shadow_color,
                align="left"
            )
        
        # === PRICE TEXT (Bottom Right) ===
        if price_text:
            price_font = self._get_font("bold", int(width * 0.05))
            price_y = height - padding - int(width * 0.05)
            
            # Get text width for right alignment
            bbox = draw.textbbox((0, 0), price_text, font=price_font)
            text_width = bbox[2] - bbox[0]
            price_x = width - text_width - padding
            
            self._draw_text_with_shadow(
                draw, price_text, price_font,
                x=price_x, y=price_y,
                color=main_color, shadow_color=shadow_color,
                align="left"
            )
        
        # Composite overlay
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')
        
        # Save as high-quality PNG
        output = io.BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        return output.getvalue()
    
    def _draw_text_with_shadow(
        self, draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
        x: int, y: int, color: Tuple, shadow_color: Tuple, align: str = "left"
    ):
        """Draw text with drop shadow for visibility"""
        shadow_offset = 2
        # Shadow
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
        # Main text
        draw.text((x, y), text, font=font, fill=color)
    
    def _draw_centered_text(
        self, draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
        width: int, y: int, color: Tuple, shadow_color: Tuple
    ):
        """Draw centered text with shadow"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        
        shadow_offset = 3
        # Shadow
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
        # Main text
        draw.text((x, y), text, font=font, fill=color)
    
    # Legacy method for compatibility
    def apply_overlay(
        self,
        image_bytes: bytes,
        logo_bytes: Optional[bytes] = None,
        headline_text: str = "",
        sub_text: str = "",
        text_color: str = "white",
        text_position: str = "bottom"
    ) -> bytes:
        """Legacy method - redirects to new poster overlay"""
        return self.apply_poster_overlay(
            image_bytes=image_bytes,
            hero_text=headline_text,
            sub_text=sub_text,
            logo_bytes=logo_bytes,
            text_color=text_color
        )
