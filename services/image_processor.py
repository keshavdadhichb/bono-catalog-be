"""
Image Processor Service
Handles image preprocessing for virtual try-on (simplified for Vercel)
"""

import io
from PIL import Image


class ImageProcessor:
    """Handles image preprocessing for virtual try-on"""
    
    SUPPORTED_FORMATS = {'PNG', 'JPEG', 'JPG', 'WEBP'}
    MAX_DIMENSION = 4096
    
    @staticmethod
    def validate_image(image_bytes: bytes) -> tuple[bool, str]:
        """Validate image format and dimensions"""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            if img.format and img.format.upper() not in ImageProcessor.SUPPORTED_FORMATS:
                return False, f"Unsupported format: {img.format}. Use PNG, JPEG, or WEBP."
            
            width, height = img.size
            if width < 100 or height < 100:
                return False, "Image too small. Minimum 100x100 pixels required."
            
            if width > ImageProcessor.MAX_DIMENSION or height > ImageProcessor.MAX_DIMENSION:
                return False, f"Image too large. Maximum {ImageProcessor.MAX_DIMENSION}px per side."
            
            return True, ""
            
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"
    
    @staticmethod
    def resize_for_api(image_bytes: bytes, max_size: int = 2048) -> bytes:
        """Resize image for API submission while maintaining aspect ratio"""
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed (but keep RGBA for transparency)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        
        width, height = img.size
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        format = 'PNG' if img.mode == 'RGBA' else 'JPEG'
        img.save(output, format=format, quality=95)
        output.seek(0)
        return output.getvalue()
    
    @staticmethod
    def prepare_garment(image_bytes: bytes, remove_bg: bool = False) -> bytes:
        """
        Preprocessing pipeline for garment images
        Note: Background removal disabled for Vercel compatibility
        """
        is_valid, error = ImageProcessor.validate_image(image_bytes)
        if not is_valid:
            raise ValueError(error)
        
        # Resize for API
        image_bytes = ImageProcessor.resize_for_api(image_bytes)
        
        return image_bytes
    
    @staticmethod
    def prepare_logo(image_bytes: bytes) -> bytes:
        """Prepare logo image for API - lenient validation"""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            width, height = img.size
            target_size = 512
            
            if width > target_size or height > target_size:
                if width > height:
                    new_width = target_size
                    new_height = int(height * (target_size / width))
                else:
                    new_height = target_size
                    new_width = int(width * (target_size / height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            elif width < 64 or height < 64:
                scale = max(64 / width, 64 / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format='PNG', quality=95)
            output.seek(0)
            return output.getvalue()
            
        except Exception:
            return image_bytes
