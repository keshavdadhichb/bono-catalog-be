"""
Image Processor Service
Handles image preprocessing, background removal, and validation
"""

import io
from PIL import Image
from rembg import remove


class ImageProcessor:
    """Handles image preprocessing for virtual try-on"""
    
    # Supported image formats
    SUPPORTED_FORMATS = {'PNG', 'JPEG', 'JPG', 'WEBP'}
    
    # Maximum dimensions
    MAX_DIMENSION = 4096
    TARGET_DIMENSION = 2048  # For 2K output
    
    @staticmethod
    def validate_image(image_bytes: bytes) -> tuple[bool, str]:
        """
        Validate image format and dimensions
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            # Check format
            if img.format and img.format.upper() not in ImageProcessor.SUPPORTED_FORMATS:
                return False, f"Unsupported format: {img.format}. Use PNG, JPEG, or WEBP."
            
            # Check dimensions
            width, height = img.size
            if width < 256 or height < 256:
                return False, "Image too small. Minimum 256x256 pixels required."
            
            if width > ImageProcessor.MAX_DIMENSION or height > ImageProcessor.MAX_DIMENSION:
                return False, f"Image too large. Maximum {ImageProcessor.MAX_DIMENSION}px per side."
            
            return True, ""
            
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"
    
    @staticmethod
    def remove_background(image_bytes: bytes) -> bytes:
        """
        Remove background from garment image
        
        Args:
            image_bytes: Original image bytes
            
        Returns:
            Image bytes with transparent background
        """
        # Use rembg for background removal
        output = remove(image_bytes)
        return output
    
    @staticmethod
    def resize_for_api(image_bytes: bytes, max_size: int = 2048) -> bytes:
        """
        Resize image for API submission while maintaining aspect ratio
        
        Args:
            image_bytes: Original image bytes
            max_size: Maximum dimension (width or height)
            
        Returns:
            Resized image bytes
        """
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary (for JPEG compatibility)
        if img.mode in ('RGBA', 'P'):
            # Keep alpha for PNG
            pass
        
        # Calculate new dimensions
        width, height = img.size
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = io.BytesIO()
        format = 'PNG' if img.mode == 'RGBA' else 'JPEG'
        img.save(output, format=format, quality=95)
        output.seek(0)
        return output.getvalue()
    
    @staticmethod
    def prepare_garment(image_bytes: bytes, remove_bg: bool = True) -> bytes:
        """
        Full preprocessing pipeline for garment images
        
        Args:
            image_bytes: Raw uploaded image
            remove_bg: Whether to remove background
            
        Returns:
            Processed image bytes ready for API
        """
        # Validate first
        is_valid, error = ImageProcessor.validate_image(image_bytes)
        if not is_valid:
            raise ValueError(error)
        
        # Remove background if requested
        if remove_bg:
            image_bytes = ImageProcessor.remove_background(image_bytes)
        
        # Resize for API
        image_bytes = ImageProcessor.resize_for_api(image_bytes)
        
        return image_bytes
    
    @staticmethod
    def prepare_logo(image_bytes: bytes) -> bytes:
        """
        Prepare logo image for API - lenient validation, any size allowed
        
        Args:
            image_bytes: Logo image bytes
            
        Returns:
            Processed logo bytes
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize to reasonable size (upscale if too small, downscale if too large)
            width, height = img.size
            target_size = 512
            
            if width > target_size or height > target_size:
                # Downscale
                if width > height:
                    new_width = target_size
                    new_height = int(height * (target_size / width))
                else:
                    new_height = target_size
                    new_width = int(width * (target_size / height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            elif width < 128 or height < 128:
                # Upscale very small logos
                scale = max(128 / width, 128 / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = io.BytesIO()
            img.save(output, format='PNG', quality=95)
            output.seek(0)
            return output.getvalue()
            
        except Exception as e:
            # If logo processing fails, just return original
            return image_bytes
