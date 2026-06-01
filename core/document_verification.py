"""
Document verification and fraud detection service using Tesseract OCR
"""

import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
from io import BytesIO
from django.core.files.uploadedfile import UploadedFile


class DocumentVerificationService:
    """Service for verifying documents and detecting potential fraud"""
    
    # Ghana Card format: GHA-XXXXXXXXX-X (11 digits + 1 check digit)
    GHANA_CARD_PATTERN = r'GHA-\d{9}-\d'
    
    # Reference number format: UAXXXXXXX (7 digits)
    REFERENCE_NUMBER_PATTERN = r'UA\d{7}'
    
    # Index number format: UEBXXXXXXX (7 digits)
    INDEX_NUMBER_PATTERN = r'UEB\d{7}'
    
    # Common fraud indicators
    FRAUD_KEYWORDS = [
        'copy', 'duplicate', 'fake', 'forged', 'invalid', 'expired',
        'counterfeit', 'unauthorized', 'revoked'
    ]
    
    def __init__(self):
        """Initialize the verification service"""
        pass
    
    def extract_text_from_image(self, image_file: UploadedFile) -> dict:
        """
        Extract text from an uploaded document image using Tesseract OCR
        
        Args:
            image_file: Django UploadedFile object
            
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # Read image file
            img = Image.open(image_file)
            
            # Preprocess image for better OCR accuracy
            processed_img = self._preprocess_image(img)
            
            # Extract text using Tesseract
            extracted_text = pytesseract.image_to_string(processed_img)
            
            # Extract confidence data
            data = pytesseract.image_to_data(processed_img, output_type=pytesseract.Output.DICT)
            confidence = np.mean([int(conf) for conf in data['conf'] if int(conf) > 0])
            
            return {
                'success': True,
                'extracted_text': extracted_text,
                'confidence_score': round(confidence, 2),
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'extracted_text': None,
                'confidence_score': 0,
                'error': str(e)
            }
    
    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """
        Preprocess image to improve OCR accuracy
        
        Args:
            img: PIL Image object
            
        Returns:
            Preprocessed PIL Image
        """
        try:
            # Convert PIL image to numpy array
            img_array = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            
            # Apply thresholding
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(thresh, h=10)
            
            # Convert back to PIL Image
            result = Image.fromarray(denoised)
            return result
        except Exception:
            # If preprocessing fails, return original image
            return img
    
    def validate_ghana_card(self, text: str) -> dict:
        """
        Validate Ghana Card format and extract details
        
        Args:
            text: Extracted text from document
            
        Returns:
            Dictionary with validation results
        """
        # Search for Ghana Card number in text
        ghana_card_match = re.search(self.GHANA_CARD_PATTERN, text)
        
        if not ghana_card_match:
            return {
                'valid': False,
                'ghana_card_number': None,
                'issues': ['Ghana Card number not found in document']
            }
        
        ghana_card = ghana_card_match.group(0)
        issues = []
        
        # Validate checksum (simple validation - can be enhanced)
        if not self._validate_ghana_card_checksum(ghana_card):
            issues.append('Ghana Card checksum validation failed')
        
        return {
            'valid': len(issues) == 0,
            'ghana_card_number': ghana_card,
            'issues': issues
        }
    
    def _validate_ghana_card_checksum(self, ghana_card: str) -> bool:
        """
        Validate Ghana Card checksum
        
        Args:
            ghana_card: Ghana Card number string (GHA-XXXXXXXXX-X)
            
        Returns:
            Boolean indicating if checksum is valid
        """
        try:
            # Remove formatting
            clean_card = ghana_card.replace('-', '')
            
            # Extract digits and check digit
            digits = clean_card[3:-1]  # GHA + 9 digits
            check_digit = int(clean_card[-1])
            
            # Simple checksum validation (Luhn-like algorithm)
            total = sum(int(d) * (10 - i) for i, d in enumerate(digits))
            calculated_check = (10 - (total % 10)) % 10
            
            return calculated_check == check_digit
        except Exception:
            return False
    
    def detect_fraud_indicators(self, text: str, confidence_score: float) -> dict:
        """
        Detect potential fraud indicators in document text
        
        Args:
            text: Extracted text from document
            confidence_score: OCR confidence score (0-100)
            
        Returns:
            Dictionary with fraud risk assessment
        """
        risk_score = 0
        indicators = []
        
        text_lower = text.lower()
        
        # Check for fraud keywords
        found_fraud_keywords = [kw for kw in self.FRAUD_KEYWORDS if kw in text_lower]
        if found_fraud_keywords:
            risk_score += 30
            indicators.append(f'Fraud keywords detected: {", ".join(found_fraud_keywords)}')
        
        # Check OCR confidence
        if confidence_score < 60:
            risk_score += 20
            indicators.append(f'Low OCR confidence score ({confidence_score}%). Document may be unclear or tampered.')
        
        # Check for image manipulation signs (high variation in character spacing)
        if self._detect_text_irregularities(text):
            risk_score += 15
            indicators.append('Irregular text spacing or font detected. Possible tampering.')
        
        # Check for incomplete or missing standard fields
        if not re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
            risk_score += 10
            indicators.append('No date detected in document.')
        
        return {
            'risk_level': 'HIGH' if risk_score >= 60 else 'MEDIUM' if risk_score >= 30 else 'LOW',
            'risk_score': min(risk_score, 100),  # Cap at 100
            'indicators': indicators,
            'requires_manual_review': risk_score >= 60
        }
    
    def _detect_text_irregularities(self, text: str) -> bool:
        """
        Detect irregularities in text that may indicate tampering
        
        Args:
            text: Extracted text
            
        Returns:
            Boolean indicating if irregularities detected
        """
        # Check for unusual spacing patterns
        multiple_spaces = len(re.findall(r'\s{2,}', text))
        return multiple_spaces > 5
    
    def extract_Ghana_card_fields(self, text: str) -> dict:
        """
        Extract common fields from Ghana Card document
        
        Args:
            text: Extracted text from document
            
        Returns:
            Dictionary with extracted fields
        """
        fields = {
            'ghana_card_number': None,
            'date_of_birth': None,
            'date_of_issue': None,
            'date_of_expiry': None,
            'names': None,
        }
        
        # Extract Ghana Card number
        ghana_card_match = re.search(self.GHANA_CARD_PATTERN, text)
        if ghana_card_match:
            fields['ghana_card_number'] = ghana_card_match.group(0)
        
        # Extract dates (DD/MM/YYYY or DD-MM-YYYY format)
        date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
        date_matches = re.findall(date_pattern, text)
        if len(date_matches) >= 1:
            fields['date_of_birth'] = date_matches[0]
        if len(date_matches) >= 2:
            fields['date_of_issue'] = date_matches[1]
        if len(date_matches) >= 3:
            fields['date_of_expiry'] = date_matches[2]
        
        # Extract names (usually in uppercase)
        name_pattern = r'[A-Z][A-Z\s]{2,}'
        name_match = re.search(name_pattern, text)
        if name_match:
            fields['names'] = name_match.group(0).strip()
        
        return fields
    
    def verify_document_complete(self, image_file: UploadedFile, expected_ghana_card: str = None) -> dict:
        """
        Complete document verification workflow
        
        Args:
            image_file: Document image file
            expected_ghana_card: Expected Ghana Card number (optional, for cross-validation)
            
        Returns:
            Comprehensive verification result
        """
        # Step 1: Extract text
        extraction_result = self.extract_text_from_image(image_file)
        
        if not extraction_result['success']:
            return {
                'verification_status': 'FAILED',
                'reason': extraction_result['error'],
                'details': {}
            }
        
        extracted_text = extraction_result['extracted_text']
        confidence_score = extraction_result['confidence_score']
        
        # Step 2: Validate Ghana Card format
        ghana_card_validation = self.validate_ghana_card(extracted_text)
        
        # Step 3: Detect fraud indicators
        fraud_detection = self.detect_fraud_indicators(extracted_text, confidence_score)
        
        # Step 4: Extract fields
        extracted_fields = self.extract_Ghana_card_fields(extracted_text)
        
        # Step 5: Cross-validate with expected Ghana Card if provided
        cross_validation = True
        if expected_ghana_card and ghana_card_validation['ghana_card_number']:
            cross_validation = ghana_card_validation['ghana_card_number'] == expected_ghana_card
        
        return {
            'verification_status': 'PASS' if (ghana_card_validation['valid'] and 
                                              fraud_detection['risk_level'] == 'LOW' and 
                                              cross_validation) else 'FAIL',
            'ocr_confidence': confidence_score,
            'ghana_card_validation': ghana_card_validation,
            'fraud_detection': fraud_detection,
            'extracted_fields': extracted_fields,
            'cross_validation_passed': cross_validation,
            'requires_manual_review': fraud_detection['requires_manual_review'],
        }
