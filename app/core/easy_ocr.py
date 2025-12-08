import easyocr
import re
from typing import Optional
from PIL import Image
import numpy as np


class EasyOCR:
    def __init__(self, languages: list = ['en', 'fr'], gpu: bool = False):
        """
        Initialize EasyOCR reader
        
        Args:
            languages: List of languages to detect (default: ['en', 'fr'] for Tunisian IDs)
            gpu: Whether to use GPU acceleration
        """
        self.reader = easyocr.Reader(languages, gpu=gpu)
    
    def extract_id_number(
        self, 
        image: Image.Image, 
        min_confidence: float = 0.5
    ) -> Optional[str]:
        """
        Extract 8 consecutive digits (CIN) from an image with high confidence
        
        Args:
            image: PIL Image object
            min_confidence: Minimum confidence threshold (0.0 to 1.0)
        
        Returns:
            CIN string (8 digits) if found, None otherwise
        """
        # Convert PIL Image to numpy array
        img_array = np.array(image)
        
        # Perform OCR
        results = self.reader.readtext(img_array)
        
        # Pattern to match exactly 8 consecutive digits
        pattern = r'\b\d{8}\b'
        
        best_match = None
        best_confidence = 0.0
        
        # Search through all detected text
        for detection in results:
            bbox, text, confidence = detection
            
            # Clean the text (remove spaces and special characters)
            cleaned_text = re.sub(r'[^\d]', '', text)
            
            # Check if we have exactly 8 digits
            if len(cleaned_text) == 8 and cleaned_text.isdigit():
                if confidence >= min_confidence and confidence > best_confidence:
                    best_match = cleaned_text
                    best_confidence = confidence
            
            # Also check for 8 consecutive digits within the text
            matches = re.findall(pattern, text)
            for match in matches:
                if confidence >= min_confidence and confidence > best_confidence:
                    best_match = match
                    best_confidence = confidence
        
        return best_match
    
    def extract_all_text(self, image: Image.Image) -> list:
        """
        Extract all text from image with bounding boxes and confidence
        
        Args:
            image: PIL Image object
        
        Returns:
            List of tuples: (bbox, text, confidence)
        """
        img_array = np.array(image)
        results = self.reader.readtext(img_array)
        return results
    
    def extract_id_number_detailed(
        self, 
        image: Image.Image, 
        min_confidence: float = 0.5
    ) -> dict:
        """
        Extract ID number with detailed information
        
        Args:
            image: PIL Image object
            min_confidence: Minimum confidence threshold
        
        Returns:
            Dictionary with all 8-digit candidates and their details
        """
        img_array = np.array(image)
        results = self.reader.readtext(img_array)
        
        pattern = r'\b\d{8}\b'
        candidates = []
        
        for detection in results:
            bbox, text, confidence = detection
            
            # Clean the text
            cleaned_text = re.sub(r'[^\d]', '', text)
            
            # Check for exactly 8 digits
            if len(cleaned_text) == 8 and cleaned_text.isdigit():
                candidates.append({
                    'id_number': cleaned_text,
                    'confidence': confidence,
                    'bbox': bbox,
                    'original_text': text,
                    'meets_threshold': confidence >= min_confidence
                })
            
            # Check for pattern matches
            matches = re.findall(pattern, text)
            for match in matches:
                if match not in [c['id_number'] for c in candidates]:
                    candidates.append({
                        'id_number': match,
                        'confidence': confidence,
                        'bbox': bbox,
                        'original_text': text,
                        'meets_threshold': confidence >= min_confidence
                    })
        
        # Sort by confidence
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'best_match': candidates[0] if candidates else None,
            'all_candidates': candidates
        }


