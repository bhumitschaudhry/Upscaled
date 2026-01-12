from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
import torch
import os
import io
import base64
from PIL import Image
import uuid
import threading
import time
from generator import Generator
from upscaler import load_image, save_image

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("UPSCALED_DATA_DIR") or BASE_DIR
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(DATA_DIR, "outputs")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

model = None
model_loaded = False
processing_status = {}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_model():
    global model, model_loaded
    try:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = Generator(scale_factor=4).to(device)
        model_path = os.path.join(BASE_DIR, "generator.pth")
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        model_loaded = True
        print(f"Model loaded successfully on {device}!")
    except Exception as e:
        print(f"Error loading model: {e}")
        model_loaded = False


def process_image_async(task_id, input_path, output_path):
    global processing_status

    try:
        processing_status[task_id] = {"status": "processing", "progress": 0}

        processing_status[task_id]["progress"] = 25
        img_tensor = load_image(input_path).to(next(model.parameters()).device)

        processing_status[task_id]["progress"] = 50
        with torch.no_grad():
            sr_tensor = model(img_tensor)

        processing_status[task_id]["progress"] = 75
        save_image(sr_tensor, output_path)

        processing_status[task_id] = {
            "status": "completed",
            "progress": 100,
            "output_path": output_path,
        }

    except Exception as e:
        processing_status[task_id] = {"status": "error", "progress": 0, "error": str(e)}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upscaled - AI Image Upscaler</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            padding: 40px;
            width: 100%;
            max-width: 600px;
            position: relative;
            overflow: hidden;
        }

        .container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
            border-radius: 24px 24px 0 0;
        }

        h1 {
            text-align: center;
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
        }

        .subtitle {
            text-align: center;
            color: #6b7280;
            font-size: 1.1rem;
            margin-bottom: 40px;
        }

        .upload-area {
            border: 2px dashed #d1d5db;
            border-radius: 16px;
            padding: 60px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f9fafb;
            position: relative;
            overflow: hidden;
        }

        .upload-area:hover {
            border-color: #667eea;
            background: #f0f4ff;
            transform: translateY(-2px);
        }

        .upload-area.dragover {
            border-color: #667eea;
            background: #f0f4ff;
            transform: scale(1.02);
        }

        .upload-icon {
            width: 64px;
            height: 64px;
            margin: 0 auto 16px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 24px;
        }

        .upload-text {
            font-size: 1.2rem;
            font-weight: 600;
            color: #374151;
            margin-bottom: 8px;
        }

        .upload-subtext {
            color: #6b7280;
            font-size: 0.9rem;
        }

        .image-preview {
            display: none;
            margin-top: 24px;
            text-align: center;
        }

        .preview-img {
            max-width: 100%;
            max-height: 300px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }

        .preview-img:hover {
            transform: scale(1.05);
        }

        .file-info {
            margin-top: 12px;
            color: #6b7280;
            font-size: 0.9rem;
        }

        .actions {
            display: flex;
            gap: 16px;
            margin-top: 32px;
        }

        .btn {
            flex: 1;
            padding: 16px 24px;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }

        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
        }

        .btn-secondary {
            background: #f3f4f6;
            color: #374151;
            border: 2px solid #e5e7eb;
        }

        .btn-secondary:hover:not(:disabled) {
            background: #e5e7eb;
            transform: translateY(-2px);
        }

        .status {
            margin-top: 24px;
            padding: 16px;
            border-radius: 12px;
            font-weight: 500;
            text-align: center;
            opacity: 0;
            transform: translateY(10px);
            transition: all 0.3s ease;
        }

        .status.show {
            opacity: 1;
            transform: translateY(0);
        }

        .status.success {
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }

        .status.error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }

        .status.info {
            background: #dbeafe;
            color: #1e40af;
            border: 1px solid #93c5fd;
        }

        .loading {
            display: none;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 24px;
        }

        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid #f3f4f6;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .progress-bar {
            width: 100%;
            height: 4px;
            background: #e5e7eb;
            border-radius: 2px;
            overflow: hidden;
            margin-top: 16px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            width: 0%;
            transition: width 0.3s ease;
        }

        @media (max-width: 640px) {
            .container {
                padding: 24px;
                margin: 10px;
            }
            
            h1 {
                font-size: 2rem;
            }
            
            .actions {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Upscaled</h1>
        <p class="subtitle">AI-powered image upscaling with 4x enhancement</p>
        
        <div class="upload-area" id="uploadArea">
            <div class="upload-icon">📷</div>
            <div class="upload-text">Drop your image here or click to browse</div>
            <div class="upload-subtext">Supports JPG, PNG, and JPEG files</div>
            <input type="file" id="fileInput" accept="image/*" style="display: none;">
        </div>
        
        <div class="image-preview" id="imagePreview">
            <img id="previewImg" class="preview-img" alt="Preview">
            <div class="file-info" id="fileInfo"></div>
        </div>
        
        <div class="actions">
            <button class="btn btn-secondary" id="clearBtn" disabled>Clear Image</button>
            <button class="btn btn-primary" id="upscaleBtn" disabled>Upscale Image</button>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <span>Processing your image...</span>
        </div>
        
        <div class="progress-bar" id="progressBar" style="display: none;">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        
        <div class="status" id="status"></div>
    </div>

    <script>
        class ModernUpscaler {
            constructor() {
                this.initElements();
                this.initEventListeners();
                this.selectedFile = null;
                this.modelLoaded = false;
                this.currentTaskId = null;
                this.checkModelStatus();
            }

            initElements() {
                this.uploadArea = document.getElementById('uploadArea');
                this.fileInput = document.getElementById('fileInput');
                this.imagePreview = document.getElementById('imagePreview');
                this.previewImg = document.getElementById('previewImg');
                this.fileInfo = document.getElementById('fileInfo');
                this.clearBtn = document.getElementById('clearBtn');
                this.upscaleBtn = document.getElementById('upscaleBtn');
                this.loading = document.getElementById('loading');
                this.progressBar = document.getElementById('progressBar');
                this.progressFill = document.getElementById('progressFill');
                this.status = document.getElementById('status');
            }

            initEventListeners() {
                this.uploadArea.addEventListener('click', () => this.fileInput.click());
                this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files[0]));

                this.uploadArea.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    this.uploadArea.classList.add('dragover');
                });

                this.uploadArea.addEventListener('dragleave', () => {
                    this.uploadArea.classList.remove('dragover');
                });

                this.uploadArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    this.uploadArea.classList.remove('dragover');
                    const file = e.dataTransfer.files[0];
                    if (file && file.type.startsWith('image/')) {
                        this.handleFileSelect(file);
                    }
                });

                this.clearBtn.addEventListener('click', () => this.clearImage());
                this.upscaleBtn.addEventListener('click', () => this.upscaleImage());
            }

            async checkModelStatus() {
                try {
                    const response = await fetch('/api/model-status');
                    const data = await response.json();
                    this.modelLoaded = data.loaded;
                    
                    if (this.modelLoaded) {
                        this.showStatus('Model loaded successfully! Ready to upscale images.', 'success');
                        this.updateButtonStates();
                    } else {
                        this.showStatus('Model loading failed. Please refresh the page.', 'error');
                    }
                } catch (error) {
                    this.showStatus('Error connecting to server. Please refresh the page.', 'error');
                }
            }

            handleFileSelect(file) {
                if (!file) return;

                if (!file.type.startsWith('image/')) {
                    this.showStatus('Please select a valid image file.', 'error');
                    return;
                }

                this.selectedFile = file;
                this.displayImagePreview(file);
                this.updateButtonStates();
                
                const fileName = file.name;
                const fileSize = (file.size / 1024 / 1024).toFixed(2);
                this.fileInfo.textContent = `${fileName} (${fileSize} MB)`;
                this.showStatus(`Image selected: ${fileName}`, 'info');
            }

            displayImagePreview(file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    this.previewImg.src = e.target.result;
                    this.imagePreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }

            clearImage() {
                this.selectedFile = null;
                this.imagePreview.style.display = 'none';
                this.fileInput.value = '';
                this.updateButtonStates();
                this.showStatus('Image cleared. Select a new image to upscale.', 'info');
            }

            updateButtonStates() {
                this.clearBtn.disabled = !this.selectedFile;
                this.upscaleBtn.disabled = !this.selectedFile || !this.modelLoaded;
            }

            async upscaleImage() {
                if (!this.selectedFile || !this.modelLoaded) return;

                const formData = new FormData();
                formData.append('image', this.selectedFile);

                this.upscaleBtn.disabled = true;
                this.clearBtn.disabled = true;
                this.loading.style.display = 'flex';
                this.progressBar.style.display = 'block';
                
                try {
                    const response = await fetch('/api/upscale', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        this.currentTaskId = data.task_id;
                        this.pollProgress();
                    } else {
                        throw new Error(data.error || 'Upload failed');
                    }
                } catch (error) {
                    this.showStatus(`Error: ${error.message}`, 'error');
                    this.resetUI();
                }
            }

            async pollProgress() {
                if (!this.currentTaskId) return;

                try {
                    const response = await fetch(`/api/progress/${this.currentTaskId}`);
                    const data = await response.json();
                    
                    this.progressFill.style.width = `${data.progress}%`;
                    
                    if (data.status === 'completed') {
                        this.showStatus('Image upscaled successfully! Download starting...', 'success');
                        this.downloadResult();
                        this.resetUI();
                    } else if (data.status === 'error') {
                        this.showStatus(`Error: ${data.error}`, 'error');
                        this.resetUI();
                    } else {
                        setTimeout(() => this.pollProgress(), 1000);
                    }
                } catch (error) {
                    this.showStatus('Error checking progress. Please try again.', 'error');
                    this.resetUI();
                }
            }

            async downloadResult() {
                if (!this.currentTaskId) return;

                try {
                    const response = await fetch(`/api/download/${this.currentTaskId}`);
                    const blob = await response.blob();
                    
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `upscaled_${this.selectedFile.name}`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                } catch (error) {
                    this.showStatus('Error downloading file. Please try again.', 'error');
                }
            }

            resetUI() {
                this.loading.style.display = 'none';
                this.progressBar.style.display = 'none';
                this.progressFill.style.width = '0%';
                this.upscaleBtn.disabled = false;
                this.clearBtn.disabled = false;
                this.currentTaskId = null;
            }

            showStatus(message, type) {
                this.status.textContent = message;
                this.status.className = `status ${type} show`;
                
                setTimeout(() => {
                    this.status.classList.remove('show');
                }, 4000);
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            new ModernUpscaler();
        });
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/model-status")
def model_status():
    return jsonify({"loaded": model_loaded})


@app.route("/api/upscale", methods=["POST"])
def upscale():
    if not model_loaded:
        return jsonify({"error": "Model not loaded"}), 500

    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    task_id = str(uuid.uuid4())

    filename = secure_filename(file.filename)
    input_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{task_id}_{filename}")
    file.save(input_path)

    output_filename = f"upscaled_{filename}"
    output_path = os.path.join(
        app.config["OUTPUT_FOLDER"], f"{task_id}_{output_filename}"
    )

    thread = threading.Thread(
        target=process_image_async, args=(task_id, input_path, output_path)
    )
    thread.start()

    return jsonify({"task_id": task_id, "message": "Processing started"})


@app.route("/api/progress/<task_id>")
def progress(task_id):
    if task_id not in processing_status:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(processing_status[task_id])


@app.route("/api/download/<task_id>")
def download(task_id):
    if task_id not in processing_status:
        return jsonify({"error": "Task not found"}), 404

    task_status = processing_status[task_id]
    if task_status["status"] != "completed":
        return jsonify({"error": "Task not completed"}), 400

    output_path = task_status["output_path"]
    if not os.path.exists(output_path):
        return jsonify({"error": "Output file not found"}), 404

    return send_file(output_path, as_attachment=True)


@app.route("/api/cleanup/<task_id>", methods=["DELETE"])
def cleanup(task_id):
    if task_id in processing_status:
        for folder in [app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]]:
            for file in os.listdir(folder):
                if file.startswith(task_id):
                    os.remove(os.path.join(folder, file))

        del processing_status[task_id]
        return jsonify({"message": "Files cleaned up"})

    return jsonify({"error": "Task not found"}), 404


if __name__ == "__main__":
    load_model()

    host = os.environ.get("UPSCALED_HOST", "127.0.0.1")
    port = int(os.environ.get("UPSCALED_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").strip() in {"1", "true", "True", "yes", "on"}
    app.run(debug=debug, host=host, port=port)
