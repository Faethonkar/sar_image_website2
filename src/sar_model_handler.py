"""
Direct YOLO model handler for Railway deployment
This runs the SAR YOLO model directly without requiring a separate Gradio server
"""

import os
import logging
from pathlib import Path
from PIL import Image
import numpy as np

# Set up logging
logger = logging.getLogger(__name__)

class SARModelHandler:
    """Direct SAR YOLO model handler"""
    
    def __init__(self):
        self.model = None
        self.model_classes = ['ships', 'aircrafts']
        self.model_loaded = False
        self.error_message = None
        
    def load_model(self):
        """Load the YOLO model directly"""
        try:
            # Try to import ultralytics
            from ultralytics import YOLO
            
            # Check if we have HF_TOKEN
            hf_token = os.getenv('HF_TOKEN')
            
            if hf_token:
                logger.info("🔑 Using HF_TOKEN for private model access")
                # Try to load the private model
                model_path = "Faethon88/sar"
            else:
                logger.info("⚠️ No HF_TOKEN found, using fallback approach")
                # Try to download and cache the model
                model_path = self._download_model()
            
            logger.info(f"📦 Loading YOLO model from: {model_path}")
            self.model = YOLO(model_path)
            self.model_loaded = True
            logger.info("✅ YOLO model loaded successfully")
            
            return True
            
        except ImportError as e:
            self.error_message = f"ultralytics not installed: {e}"
            logger.error(f"❌ {self.error_message}")
            return False
        except Exception as e:
            self.error_message = f"Failed to load model: {e}"
            logger.error(f"❌ {self.error_message}")
            return False
    
    def _download_model(self):
        """Download model using huggingface_hub"""
        try:
            from huggingface_hub import hf_hub_download
            
            # Download the model file
            model_file = hf_hub_download(
                repo_id="Faethon88/sar",
                filename="best.pt",
                cache_dir=os.path.expanduser("~/.cache/huggingface/hub")
            )
            
            logger.info(f"📥 Downloaded model to: {model_file}")
            return model_file
            
        except Exception as e:
            logger.error(f"❌ Failed to download model: {e}")
            # Fallback to a public YOLO model
            logger.info("🔄 Falling back to public YOLOv8 model")
            return "yolov8n.pt"  # This will auto-download from Ultralytics
    
    def resize_image(self, image_path, max_size=1024):
        """Resize image to maximum dimensions while preserving aspect ratio"""
        try:
            with Image.open(image_path) as img:
                # Get original dimensions
                width, height = img.size
                
                # Calculate new dimensions
                if width > max_size or height > max_size:
                    # Calculate scaling factor
                    scale = min(max_size / width, max_size / height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    
                    # Resize image
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"📏 Resized image from {width}x{height} to {new_width}x{new_height}")
                
                # Save resized image
                resized_path = image_path.replace('.jpg', '_resized.jpg').replace('.png', '_resized.png')
                img.save(resized_path, quality=95)
                return resized_path
                
        except Exception as e:
            logger.error(f"❌ Failed to resize image: {e}")
            return image_path  # Return original path if resize fails
    
    def predict(self, image_path):
        """Run SAR analysis on image"""
        try:
            if not self.model_loaded:
                if not self.load_model():
                    return {
                        'error': f'Model not available: {self.error_message}',
                        'detection_summary': 'Model loading failed',
                        'machine_readable': {'ships': 0, 'aircrafts': 0, 'total': 0}
                    }
            
            # Resize image if needed
            processed_image_path = self.resize_image(image_path)
            
            # Run inference
            logger.info(f"🔍 Running inference on: {processed_image_path}")
            results = self.model(processed_image_path)
            
            # Process results
            detections = {'ships': 0, 'aircrafts': 0}
            
            for result in results:
                if hasattr(result, 'boxes') and result.boxes is not None:
                    for box in result.boxes:
                        if hasattr(box, 'cls'):
                            class_id = int(box.cls.cpu().numpy()[0])
                            if class_id < len(self.model_classes):
                                class_name = self.model_classes[class_id]
                                detections[class_name] += 1
            
            total_detections = sum(detections.values())
            
            # Format summary
            summary_parts = []
            if detections['ships'] > 0:
                summary_parts.append(f"ships: {detections['ships']}")
            if detections['aircrafts'] > 0:
                summary_parts.append(f"aircrafts: {detections['aircrafts']}")
            
            if summary_parts:
                detection_summary = f"Detection Summary: {', '.join(summary_parts)}"
            else:
                detection_summary = "Detection Summary: No objects detected"
            
            logger.info(f"✅ Analysis complete: {detection_summary}")
            
            return {
                'detection_summary': detection_summary,
                'machine_readable': {
                    'ships': detections['ships'],
                    'aircrafts': detections['aircrafts'],
                    'total': total_detections
                },
                'processed_image_path': processed_image_path
            }
            
        except Exception as e:
            error_msg = f"Prediction failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'error': error_msg,
                'detection_summary': 'Analysis failed',
                'machine_readable': {'ships': 0, 'aircrafts': 0, 'total': 0}
            }

# Global model handler instance
sar_model_handler = SARModelHandler()