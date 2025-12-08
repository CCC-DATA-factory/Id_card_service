import numpy as np
import onnxruntime as ort
from PIL import Image
from pathlib import Path

class IdCardValidator:
    """Validates ID cards using ONNX object detection model."""
    
    INPUT_SIZE = (640, 640)
    CLASS_MAP = {0: "front", 1: "back"}
    
    def __init__(self, model_path="best.onnx", confidence_threshold=0.8, iou_threshold=0.45, session=None):
        """
        Initialize the ID card validator.
        
        Args:
            model_path: Path to ONNX model file
            confidence_threshold: Minimum confidence score for detections
            iou_threshold: IoU threshold for NMS
            session: Pre-initialized ONNX runtime session (optional)
        """
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        
        if session is None:
            self.session = ort.InferenceSession(model_path)
        else:
            self.session = session
            
        self.input_name = self.session.get_inputs()[0].name
    
    def validate(self, image: Image.Image):
        """
        Validate an ID card image.
        
        Args:
            image: PIL Image object
            
        Returns:
            tuple: (class_id, confidence, bbox) where bbox is [x0, y0, x1, y1]
                   Returns (None, 0.0, []) if no detection above threshold
        """
        # Preprocess
        input_tensor, scale, pad = self._preprocess(image)
        
        # Inference
        outputs = self.session.run(None, {self.input_name: input_tensor})
        
        # Postprocess
        boxes, scores, class_ids = self._postprocess(
            outputs, scale, pad, image.size, 
            self.confidence_threshold, self.iou_threshold
        )
        
        # Return highest confidence detection
        if len(scores) == 0:
            return None, 0.0, []
        
        max_idx = np.argmax(scores)
        return int(class_ids[max_idx]), float(scores[max_idx]), boxes[max_idx].tolist()
    
    def _preprocess(self, image: Image.Image):
        """Preprocess PIL image for model input."""
        img_array = np.array(image.convert('RGB'))
        resized, scale, pad = self._resize_with_padding(img_array, self.INPUT_SIZE)
        tensor = resized.transpose(2, 0, 1)[None, ...].astype(np.float32) / 255.0
        return tensor, scale, pad
    
    def _resize_with_padding(self, image, target_size):
        """Resize image with letterbox padding."""
        h, w = image.shape[:2]
        scale = min(target_size[0] / h, target_size[1] / w)
        nh, nw = int(h * scale), int(w * scale)
        
        # Resize
        from PIL import Image as PILImage
        img_pil = PILImage.fromarray(image)
        img_resized = img_pil.resize((nw, nh), PILImage.BILINEAR)
        
        # Pad
        new_image = np.full((target_size[0], target_size[1], 3), 114, dtype=np.uint8)
        top = (target_size[0] - nh) // 2
        left = (target_size[1] - nw) // 2
        new_image[top:top + nh, left:left + nw] = np.array(img_resized)
        
        return new_image, scale, (left, top)
    
    def _postprocess(self, outputs, scale, pad, orig_size, conf_thresh, iou_thresh):
        """Postprocess model outputs to get final detections."""
        detections = outputs[0][0].T
        boxes, scores, class_ids = [], [], []
        
        # orig_size is (width, height) from PIL Image.size
        orig_width, orig_height = orig_size
        
        for det in detections:
            x, y, w, h, *cls_scores = det
            cls_id = np.argmax(cls_scores)
            conf = cls_scores[cls_id]
            
            if conf < conf_thresh:
                continue
            
            # Convert to original image coordinates
            x0 = (x - w / 2 - pad[0]) / scale
            y0 = (y - h / 2 - pad[1]) / scale
            x1 = (x + w / 2 - pad[0]) / scale
            y1 = (y + h / 2 - pad[1]) / scale
            
            # Clamp to image boundaries
            x0 = max(0, min(x0, orig_width))
            y0 = max(0, min(y0, orig_height))
            x1 = max(0, min(x1, orig_width))
            y1 = max(0, min(y1, orig_height))
            
            boxes.append([x0, y0, x1, y1])
            scores.append(conf)
            class_ids.append(cls_id)
        
        if len(boxes) == 0:
            return np.array([]), np.array([]), np.array([])
        
        boxes = np.array(boxes)
        scores = np.array(scores)
        class_ids = np.array(class_ids)
        
        # Apply NMS
        keep = self._nms(boxes, scores, iou_thresh)
        return boxes[keep], scores[keep], class_ids[keep]
    
    def _nms(self, boxes, scores, iou_threshold):
        """Non-maximum suppression."""
        idxs = np.argsort(scores)[::-1]
        keep = []
        
        while len(idxs) > 0:
            i = idxs[0]
            keep.append(i)
            
            if len(idxs) == 1:
                break
            
            # Compute IoU
            x1 = np.maximum(boxes[i][0], boxes[idxs[1:], 0])
            y1 = np.maximum(boxes[i][1], boxes[idxs[1:], 1])
            x2 = np.minimum(boxes[i][2], boxes[idxs[1:], 2])
            y2 = np.minimum(boxes[i][3], boxes[idxs[1:], 3])
            
            inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
            area_i = (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1])
            area_j = (boxes[idxs[1:], 2] - boxes[idxs[1:], 0]) * (boxes[idxs[1:], 3] - boxes[idxs[1:], 1])
            union = area_i + area_j - inter
            
            ious = inter / np.maximum(union, 1e-6)
            idxs = idxs[1:][ious < iou_threshold]
        
        return keep


    def check_centred(self, image: Image.Image, bbox, margin_percent=0.001):
        """
        Check if the bounding box is centered in the image with adequate margins.
        
        Args:
            image: PIL Image object
            bbox: Bounding box [x0, y0, x1, y1]
            margin_percent: Minimum margin as percentage of image dimension (default 5%)
            
        Returns:
            bool: True if bbox is centered with proper margins
        """
        if not bbox or len(bbox) != 4:
            return False
        
        img_width, img_height = image.size  # PIL: (width, height)
        x0, y0, x1, y1 = bbox
        
        # Clamp bbox to image boundaries (in case of slight coordinate errors)
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(img_width, x1)
        y1 = min(img_height, y1)
        
        # Calculate margins
        margin_left = x0
        margin_top = y0
        margin_right = img_width - x1
        margin_bottom = img_height - y1
        
        # Required margins
        min_margin_x = img_width * margin_percent
        min_margin_y = img_height * margin_percent
        
        # Check if all margins are sufficient
        is_centered = (
            margin_left >= min_margin_x and
            margin_right >= min_margin_x and
            margin_top >= min_margin_y and
            margin_bottom >= min_margin_y
        )
        
        return is_centered
    
    def validate_card_pair(self, front_img: Image.Image, back_img: Image.Image):
        """
        Validate both front and back ID card images.
        
        Args:
            front_img: PIL Image of front side
            back_img: PIL Image of back side
            
        Returns:
            dict: Validation result with status, data, audit messages, and duration
        """
        import time
        
        start_time = time.time()
        
        # Validate front
        class_front_id, confidence_front, bbox_front = self.validate(front_img)
        
        # Validate back
        class_back_id, confidence_back, bbox_back = self.validate(back_img)
        
        # Check if cards are centered
        front_centred = self.check_centred(front_img, bbox_front)
        back_centred = self.check_centred(back_img, bbox_back)
        
        end_time = time.time()
        time_of_validation = end_time - start_time
        
        # Build audit messages
        messages = []
        
        # Front card validation
        if class_front_id == 0 and front_centred:
            messages.append("Front card detected and properly centered")
        elif class_front_id == 0 and not front_centred:
            messages.append("Front card detected but not centered - please adjust positioning")
        elif class_front_id == 1:
            messages.append("Back card detected in front image - wrong side provided")
        else:
            messages.append("No valid front card detected")
        
        # Back card validation
        if class_back_id == 1 and back_centred:
            messages.append("Back card detected and properly centered")
        elif class_back_id == 1 and not back_centred:
            messages.append("Back card detected but not centered - please adjust positioning")
        elif class_back_id == 0:
            messages.append("Front card detected in back image - wrong side provided")
        else:
            messages.append("No valid back card detected")
        
        return {
            "data": {
                "front": {
                    "status": "valid" if class_front_id == 0 and front_centred else "invalid",
                    "data": {
                        "confidence": confidence_front,
                        "bbox": bbox_front,
                        "centered": front_centred
                    }
                },
                "back": {
                    "status": "valid" if class_back_id == 1 and back_centred else "invalid",
                    "data": {
                        "confidence": confidence_back,
                        "bbox": bbox_back,
                        "centered": back_centred
                    }
                }
            },
            "audit": messages,
            "duration": round(time_of_validation, 3)
        }



# Usage example
if __name__ == "__main__":
    from PIL import Image
    MODEL_PATH = Path(__file__).resolve().parent.parent / "assets" / "best.onnx"

    # Initialize validator
    validator = IdCardValidator(
        model_path=MODEL_PATH,
        confidence_threshold=0.8
    )
    
    # Validate an image
    front_img = Image.open(r"D:\CCC-datafactory\OCR-v6\validator\recto08292728.jpg")
    back_img = Image.open(r"C:\Users\Asus\Desktop\test_ocr\WhatsApp Image 2025-10-28 à 17.49.41_ca0fdc47.jpg")

    result = validator.validate_card_pair(front_img, back_img)
    print("Validation Result:")
    print(result)