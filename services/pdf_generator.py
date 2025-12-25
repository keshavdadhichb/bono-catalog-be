"""
PDF Generator Service
Creates high-quality catalog PDFs from AI-generated page images
"""

import os
import io
from typing import List
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader


class PDFGenerator:
    """Generates fashion catalog PDFs from AI-generated page images"""
    
    # Page dimensions matching BOYS.pdf (864 x 1296 pts)
    PAGE_WIDTH_PT = 864
    PAGE_HEIGHT_PT = 1296
    
    def generate_from_images(
        self,
        page_images: List[bytes],
        output_path: str = "catalog.pdf"
    ) -> str:
        """
        Generate PDF from AI-generated page images
        
        Each image becomes a full-page in the PDF.
        
        Args:
            page_images: List of page image bytes (cover, pages, back cover)
            output_path: Where to save the PDF
            
        Returns:
            Path to generated PDF
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        # Create PDF with custom page size
        page_size = (self.PAGE_WIDTH_PT, self.PAGE_HEIGHT_PT)
        c = canvas.Canvas(output_path, pagesize=page_size)
        
        for page_bytes in page_images:
            # Convert bytes to PIL Image
            img = Image.open(io.BytesIO(page_bytes))
            
            # Convert to RGB if necessary (for PDF compatibility)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Calculate scaling to fit page while maintaining aspect ratio
            img_width, img_height = img.size
            page_width, page_height = self.PAGE_WIDTH_PT, self.PAGE_HEIGHT_PT
            
            # Calculate scale to fill page (cover the whole page)
            scale_w = page_width / img_width
            scale_h = page_height / img_height
            scale = max(scale_w, scale_h)  # Use max to ensure full coverage
            
            new_width = img_width * scale
            new_height = img_height * scale
            
            # Center the image
            x = (page_width - new_width) / 2
            y = (page_height - new_height) / 2
            
            # Draw image
            img_reader = ImageReader(img)
            c.drawImage(
                img_reader, 
                x, y, 
                width=new_width, 
                height=new_height,
                preserveAspectRatio=True,
                anchor='c'
            )
            
            # Next page
            c.showPage()
        
        # Save PDF
        c.save()
        
        return output_path
