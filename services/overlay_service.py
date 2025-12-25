"""
Overlay Service
PIL-based text and logo overlay for perfect typography

This service applies text and logos AFTER AI generation to ensure
100% accurate spelling and crisp logo rendering.
"""

import io
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple
import os


class OverlayService:
    """Apply text and logo overlays to generated images"""
    
    # Default fonts (will use system fonts if custom not available)
    DEFAULT_HEADLINE_FONT = "Arial Bold"
    DEFAULT_SUBTEXT_FONT = "Arial"
    
    def __init__(self):
        self.fonts_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
    
    def _get_font(self, font_name: str, size: int) -> ImageFont.FreeTypeFont:
        """Get font with fallback to system fonts"""
        # Try custom fonts first
        custom_fonts = {
            "headline": ["BebasNeue-Regular.ttf", "Inter-Bold.ttf", "Montserrat-Bold.ttf"],
            "subtext": ["Inter-Regular.ttf", "Montserrat-Regular.ttf"]
        }
        
        # Try to load custom font
        for font_file in custom_fonts.get(font_name, []):
            font_path = os.path.join(self.fonts_dir, font_file)
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except:
                    pass
        
        # Fallback to system fonts
        try:
            if font_name == "headline":
                return ImageFont.truetype("Arial Bold", size)
            else:
                return ImageFont.truetype("Arial", size)
        except:
            # Ultimate fallback
            return ImageFont.load_default()
    
    def apply_overlay(
        self,
        image_bytes: bytes,
        logo_bytes: Optional[bytes] = None,
        headline_text: str = "",
        sub_text: str = "",
        text_color: str = "white",
        text_position: str = "bottom"  # "bottom", "center", "top"
    ) -> bytes:
        """
        Apply logo and text overlay to an image
        
        Args:
            image_bytes: The base image
            logo_bytes: Optional logo image
            headline_text: Main headline text
            sub_text: Subtitle/tagline text
            text_color: "white" or "black"
            text_position: Where to place text
            
        Returns:
            Processed image bytes
        """
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGBA for transparency support
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        width, height = img.size
        
        # Create overlay layer
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Set text color
        if text_color == "white":
            fill_color = (255, 255, 255, 255)
            shadow_color = (0, 0, 0, 100)
        else:
            fill_color = (30, 30, 30, 255)
            shadow_color = (255, 255, 255, 50)
        
        # Apply logo (top right corner, small)
        if logo_bytes:
            self._apply_logo(img, logo_bytes, width, height)
        
        # Apply headline text
        if headline_text:
            headline_font = self._get_font("headline", int(width * 0.12))  # 12% of width
            self._draw_text_with_shadow(
                draw, headline_text, headline_font, 
                width, height, fill_color, shadow_color,
                position=text_position, is_headline=True
            )
        
        # Apply subtext
        if sub_text:
            subtext_font = self._get_font("subtext", int(width * 0.04))  # 4% of width
            self._draw_text_with_shadow(
                draw, sub_text, subtext_font,
                width, height, fill_color, shadow_color,
                position=text_position, is_headline=False,
                headline_height=int(width * 0.15) if headline_text else 0
            )
        
        # Composite overlay onto image
        img = Image.alpha_composite(img, overlay)
        
        # Convert back to RGB for output
        img = img.convert('RGB')
        
        # Save to bytes
        output = io.BytesIO()
        img.save(output, format='PNG', quality=100)
        output.seek(0)
        return output.getvalue()
    
    def _apply_logo(self, img: Image.Image, logo_bytes: bytes, width: int, height: int):
        """Apply logo to top right corner"""
        try:
            logo = Image.open(io.BytesIO(logo_bytes))
            
            # Convert to RGBA
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            
            # Resize logo to ~8% of image width
            logo_width = int(width * 0.08)
            logo_ratio = logo.width / logo.height
            logo_height = int(logo_width / logo_ratio)
            logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            
            # Position: top right with padding
            padding = int(width * 0.03)  # 3% padding
            x = width - logo_width - padding
            y = padding
            
            # Paste logo with transparency
            img.paste(logo, (x, y), logo)
        except Exception as e:
            print(f"Error applying logo: {e}")
    
    def _draw_text_with_shadow(
        self,
        draw: ImageDraw.Draw,
        text: str,
        font: ImageFont.FreeTypeFont,
        width: int,
        height: int,
        fill_color: Tuple[int, int, int, int],
        shadow_color: Tuple[int, int, int, int],
        position: str = "bottom",
        is_headline: bool = True,
        headline_height: int = 0
    ):
        """Draw text with shadow for better visibility"""
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Calculate position
        x = (width - text_width) // 2  # Center horizontally
        
        if position == "bottom":
            if is_headline:
                y = height - int(height * 0.18) - text_height
            else:
                y = height - int(height * 0.08) - text_height
        elif position == "center":
            y = (height - text_height) // 2
            if not is_headline:
                y += headline_height
        else:  # top
            y = int(height * 0.15)
            if not is_headline:
                y += headline_height + int(height * 0.05)
        
        # Draw shadow
        shadow_offset = max(2, int(width * 0.003))
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
        
        # Draw main text
        draw.text((x, y), text, font=font, fill=fill_color)
    
    def add_watermark(
        self,
        image_bytes: bytes,
        watermark_text: str = "SAMPLE",
        opacity: int = 30
    ) -> bytes:
        """Add a diagonal watermark across the image"""
        img = Image.open(io.BytesIO(image_bytes))
        
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        width, height = img.size
        
        # Create watermark layer
        watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)
        
        font = self._get_font("headline", int(width * 0.15))
        
        # Draw diagonal watermark
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, opacity))
        
        # Rotate watermark layer
        watermark = watermark.rotate(45, expand=False, center=(width//2, height//2))
        
        img = Image.alpha_composite(img, watermark)
        img = img.convert('RGB')
        
        output = io.BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        return output.getvalue()
