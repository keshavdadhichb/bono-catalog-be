"""
Image Upscaling Service
Uses high-quality LANCZOS resampling with sharpening for 2K→4K upscaling
"""

from io import BytesIO
from PIL import Image, ImageFilter, ImageEnhance


def upscale_image(
    image_bytes: bytes,
    target_width: int = 2160,  # 4K width for 9:16 aspect
    target_height: int = 3840,  # 4K height for 9:16 aspect
    sharpen_amount: float = 1.3
) -> bytes:
    """
    Upscale image using high-quality LANCZOS resampling with sharpening.
    
    Args:
        image_bytes: Input image as bytes
        target_width: Target width in pixels
        target_height: Target height in pixels
        sharpen_amount: Sharpening factor (1.0 = no change, 1.5 = moderate sharp)
    
    Returns:
        Upscaled image as PNG bytes
    """
    # Load image
    img = Image.open(BytesIO(image_bytes))
    original_size = img.size
    
    # Calculate aspect-ratio-preserving dimensions
    orig_aspect = img.width / img.height
    target_aspect = target_width / target_height
    
    if orig_aspect > target_aspect:
        # Image is wider than target - fit to width
        new_width = target_width
        new_height = int(target_width / orig_aspect)
    else:
        # Image is taller than target - fit to height
        new_height = target_height
        new_width = int(target_height * orig_aspect)
    
    # High-quality upscale using LANCZOS (best for photos)
    img_upscaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Apply subtle sharpening to recover details
    if sharpen_amount > 1.0:
        enhancer = ImageEnhance.Sharpness(img_upscaled)
        img_upscaled = enhancer.enhance(sharpen_amount)
    
    # Apply very subtle unsharp mask for edge enhancement
    img_upscaled = img_upscaled.filter(ImageFilter.UnsharpMask(
        radius=1.5,
        percent=30,
        threshold=2
    ))
    
    # Save as PNG
    output = BytesIO()
    img_upscaled.save(output, format='PNG', optimize=True)
    
    print(f"📐 Upscaled: {original_size} → {img_upscaled.size}")
    
    return output.getvalue()


def upscale_2k_to_4k(image_bytes: bytes) -> bytes:
    """
    Convenience function: Upscale 2K image to 4K for 9:16 aspect ratio.
    """
    return upscale_image(
        image_bytes,
        target_width=2160,
        target_height=3840,
        sharpen_amount=1.3
    )


def upscale_4k_to_8k(image_bytes: bytes) -> bytes:
    """
    Convenience function: Upscale 4K image to 8K for 9:16 aspect ratio.
    """
    return upscale_image(
        image_bytes,
        target_width=4320,
        target_height=7680,
        sharpen_amount=1.2  # Less sharpening for larger images
    )


def upscale_to_target(image_bytes: bytes, target: str) -> bytes:
    """
    Upscale image to target resolution.
    
    Args:
        image_bytes: Input image
        target: Target resolution ("4K" or "8K")
    
    Returns:
        Upscaled image bytes
    """
    if target == "8K":
        return upscale_4k_to_8k(image_bytes)
    else:  # Default to 4K
        return upscale_2k_to_4k(image_bytes)


def should_upscale(image_bytes: bytes, min_height: int = 2000) -> bool:
    """
    Check if image should be upscaled based on current resolution.
    """
    img = Image.open(BytesIO(image_bytes))
    return img.height < min_height

