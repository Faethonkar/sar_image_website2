# YOLO Gradio API Client

A complete Python script that sends images to your deployed YOLO Gradio app, receives annotated results, and saves them locally.

## Features

- 🚀 Send images to Gradio API via POST requests
- 🖼️ Receive annotated images and detection summaries
- 💾 Automatically save results locally with timestamps
- 📂 Support for single image or batch processing
- ⚙️ Configurable confidence threshold and output directory
- 🛡️ Proper error handling and progress tracking
- 📊 Processing statistics and summaries

## Installation

1. Install required dependencies:
```bash
pip install requests pillow
```

2. Make sure your YOLO Gradio app is deployed on Hugging Face Spaces.

## Usage

### Single Image Processing

```bash
# Basic usage
python gradio_yolo_client.py image.jpg

# With custom confidence threshold
python gradio_yolo_client.py --confidence 0.5 image.jpg

# With custom output directory
python gradio_yolo_client.py --output my_results image.jpg
```

### Batch Processing

```bash
# Process all images in a directory
python gradio_yolo_client.py --batch /path/to/images/

# Batch with custom settings
python gradio_yolo_client.py --batch --confidence 0.7 --output batch_results /path/to/images/
```

### Custom Space URL

```bash
# Use a different Hugging Face Space
python gradio_yolo_client.py --space-url https://huggingface.co/spaces/youruser/yourspace image.jpg
```

## Command Line Options

- `input`: Input image file or directory
- `--batch`: Process all images in the input directory
- `--space-url`: Hugging Face Space URL (default: https://huggingface.co/spaces/Faethon88/sar_imaging)
- `--confidence`: Detection confidence threshold 0.0-1.0 (default: 0.3)
- `--output`: Output directory for results (default: src/static/processed)

## Output Structure

The script creates an organized output directory:

```
yolo_results/
├── annotated_images/
│   ├── image1_20251019_143052_annotated.jpg
│   └── image2_20251019_143053_annotated.jpg
└── summaries/
    ├── image1_20251019_143052_summary.json
    └── image2_20251019_143052_summary.json
```

## Output Files

### Annotated Images
- Original images with YOLO detection boxes and labels
- Saved as high-quality JPEG files
- Timestamped filenames for easy identification

### Summary JSON Files
- Complete detection metadata and statistics
- API response data for debugging
- Processing timestamps and configuration
- Human-readable detection summaries

## Example Summary JSON

```json
{
  "original_image": "/path/to/original/image.jpg",
  "processed_at": "2025-10-19T14:30:52.123456",
  "confidence_threshold": 0.3,
  "detection_summary": {
    "total_detections": 3,
    "summary_text": "Detected 3 ships with confidence > 0.3"
  },
  "api_response": { ... }
}
```

## Error Handling

The script includes comprehensive error handling:
- Network connectivity issues
- Invalid image formats
- API response parsing errors
- File system permissions
- Gradio API changes

## Configuration

### Environment Variables (Optional)
You can set default values via environment variables:

```bash
export HF_SPACE_URL="https://huggingface.co/spaces/Faethon88/sar_imaging"
export YOLO_CONFIDENCE="0.3"
export YOLO_OUTPUT_DIR="src/static/processed"
```

### Gradio API Compatibility
The script is designed to work with standard Gradio interfaces. If your Gradio app has a custom API structure, you may need to adjust:

1. The `send_image_to_gradio()` method for request format
2. The `save_results()` method for response parsing
3. The `extract_detection_summary()` method for your specific output format

## Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Check your internet connection
   - Verify the Hugging Face Space URL is correct
   - Ensure the Space is public and running

2. **Authentication Errors**
   - Some Spaces require authentication tokens
   - Add HF token to headers if needed

3. **Response Parsing Errors**
   - The Gradio app output format may have changed
   - Check the API response structure and adjust parsing code

4. **File Permission Errors**
   - Ensure write permissions for the output directory
   - Check disk space availability

### Debug Mode

Add verbose logging by modifying the script:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with VS Code

### Run from VS Code Terminal
1. Open VS Code in your project directory
2. Open the integrated terminal (`Ctrl+``)
3. Run the script with your desired arguments

### VS Code Tasks (Optional)

Create `.vscode/tasks.json` for quick access:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Process SAR Image",
            "type": "shell",
            "command": "python",
            "args": ["gradio_yolo_client.py", "${input:imagePath}"],
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            }
        }
    ],
    "inputs": [
        {
            "id": "imagePath",
            "description": "Path to image file",
            "default": "test_image.jpg",
            "type": "promptString"
        }
    ]
}
```

## Performance Notes

- The script includes a 0.5-second delay between batch requests to avoid overwhelming the API
- Large images are automatically handled by the Gradio API
- Network timeouts are set to 60 seconds for processing time
- Base64 encoding is used for reliable image transmission

## License

This script is provided as-is for integration with your YOLO Gradio application.