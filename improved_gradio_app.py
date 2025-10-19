from ultralytics import YOLO
import gradio as gr
import cv2
from collections import Counter
import numpy as np
import os
from huggingface_hub import hf_hub_download

# Max upload size in megabytes
MAX_MB = 5
# Maximum dimension for processed images
MAX_PIXELS = 1024

def resize_image_for_processing(image, max_size=MAX_PIXELS):
    """
    Resize image if larger than max_size while maintaining aspect ratio
    """
    height, width = image.shape[:2]
    
    if max(width, height) <= max_size:
        return image
    
    # Calculate new dimensions
    if width > height:
        new_width = max_size
        new_height = int(height * max_size / width)
    else:
        new_height = max_size
        new_width = int(width * max_size / height)
    
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
    print(f"📏 Resized from {width}x{height} to {new_width}x{new_height}")
    return resized

def load_model():
    """Load YOLO model with fallback options."""
    try:
        # Try to download the private model securely using the token
        if "HF_TOKEN" in os.environ:
            print("Using HF_TOKEN to download private model...")
            model_path = hf_hub_download(
                repo_id="Faethon88/sar",
                filename="best.pt",
                token=os.environ["HF_TOKEN"]  # Updated parameter name
            )
            print(f"Downloaded model to: {model_path}")
        else:
            print("No HF_TOKEN found, trying without authentication...")
            # Try without token (in case repo becomes public)
            model_path = hf_hub_download(
                repo_id="Faethon88/sar",
                filename="best.pt"
            )
            print(f"Downloaded model to: {model_path}")
        
        # Load YOLO model
        model = YOLO(model_path)
        print("✅ Model loaded successfully!")
        return model
        
    except Exception as e:
        print(f"❌ Failed to load private model: {e}")
        print("🔄 Falling back to default YOLO model...")
        
        # Fallback to a public YOLO model
        try:
            model = YOLO('yolov8n.pt')  # This will auto-download
            print("✅ Fallback model loaded successfully!")
            return model
        except Exception as fallback_error:
            print(f"❌ Fallback model also failed: {fallback_error}")
            raise Exception("Could not load any YOLO model")

# Load model with error handling
try:
    model = load_model()
    MODEL_LOADED = True
    print(f"Model classes: {list(model.names.values())}")
except Exception as e:
    print(f"❌ Critical error loading model: {e}")
    MODEL_LOADED = False
    model = None

def detect(image):
    """Detect objects in the uploaded image."""
    if not MODEL_LOADED or model is None:
        return None, "❌ Model not loaded. Please contact the space owner."
    
    try:
        # Validate input
        if image is None:
            return None, "❌ No image provided."
        
        # Validate upload size
        img_bytes = cv2.imencode('.jpg', image)[1].tobytes()
        size_mb = len(img_bytes) / (1024 * 1024)
        if size_mb > MAX_MB:
            return None, f"⚠️ Image too large ({size_mb:.2f} MB). Please upload an image smaller than {MAX_MB} MB."

        # Convert PIL image to OpenCV format
        image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Resize image if needed
        image = resize_image_for_processing(image)
        
        print(f"Processing image of size: {image.shape}")
        
        # Run YOLO inference
        results = model.predict(image, verbose=False)
        result = results[0]

        # Annotate detections
        annotated_image = result.plot()

        # Extract detected class names
        class_ids = result.boxes.cls.tolist() if result.boxes is not None else []
        class_names = [model.names[int(c)] for c in class_ids] if class_ids else []
        
        print(f"Detected classes: {class_names}")

        # Count occurrences
        counts = Counter(class_names)
        if counts:
            # Create both machine-readable and human-readable summary
            summary_lines = []
            for cls, cnt in counts.items():
                # Format: "ships: 3" for parsing, then add descriptive text
                plural_cls = cls if cnt == 1 else cls  # Keep as is since model uses plural forms
                summary_lines.append(f"{cls}: {cnt}")
            
            summary_text = "\n".join(summary_lines)
            
            # Add human-readable description
            total_objects = sum(counts.values())
            if total_objects > 0:
                human_parts = []
                for cls, cnt in counts.items():
                    human_parts.append(f"{cnt} {cls}")
                human_readable = f"Detected: {', '.join(human_parts)}"
                summary_text += f"\n\n{human_readable}"
        else:
            summary_text = "No objects detected."

        # Add total count overlay
        total_objects = len(class_names)
        annotated_image = cv2.putText(
            annotated_image.copy(),
            f"Total: {total_objects}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
            cv2.LINE_AA
        )

        print(f"✅ Processing complete. Found {total_objects} objects.")
        return annotated_image, summary_text
        
    except Exception as e:
        error_msg = f"❌ Error processing image: {str(e)}"
        print(error_msg)
        return None, error_msg

# Create Gradio interface
def create_interface():
    """Create the Gradio interface."""
    
    if not MODEL_LOADED:
        # Create a simple error interface
        def error_fn(image):
            return None, "❌ YOLO model failed to load. Please contact the space owner."
        
        return gr.Interface(
            fn=error_fn,
            inputs=gr.Image(type="numpy", label="Upload Image"),
            outputs=[
                gr.Image(label="Detections"),
                gr.Textbox(label="Error Message")
            ],
            title="❌ YOLO Object Detection Demo (Error)",
            description="Model loading failed. Please contact the space owner.",
        )
    
    # Create the normal interface
    interface = gr.Interface(
        fn=detect,
        inputs=gr.Image(type="numpy", label="Upload Image"),
        outputs=[
            gr.Image(label="Detections"),
            gr.Textbox(label="Detection Summary")
        ],
        title="YOLO Object Detection Demo",
        description=f"Upload an image (max {MAX_MB} MB) to detect and count objects with YOLO. Annotated results are displayed.",
        examples=[
            # You can add example images here if you have them
        ],
        analytics_enabled=False,  # Disable analytics for privacy
    )
    
    return interface

# Launch the interface
if __name__ == "__main__":
    print("🚀 Starting Gradio interface...")
    interface = create_interface()
    interface.launch(
        share=False,  # Set to True if you want a public link
        server_name="0.0.0.0",  # Listen on all interfaces
        server_port=7860,  # Default Gradio port
        show_error=True,  # Show detailed errors
    )