# AI Image Upscaler

An advanced image upscaling application that uses AI to enhance image resolution while maintaining quality. Built with Python, Flask, and PyTorch.

## Features

- Real-time image upscaling
- Web-based user interface
- Support for multiple image formats
- High-quality output using AI-powered upscaling
- Automatic image processing and optimization

## Prerequisites

- Python 3.9+
- PyTorch
- Flask
- Other dependencies (listed in requirements.txt)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/bhumitschaudhry/upscaled.git
cd upscaled
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Download the model file:

- Ensure `generator.pth` is in the root directory

## Usage

1. Start the Flask server:

```bash
python app.py
```

2. Open your web browser and navigate to `http://localhost:5000`

3. Upload an image through the web interface

4. Wait for the processing to complete

5. Download your upscaled image

## Configuration

The application uses default settings optimized for most use cases. You can modify the following in the code:

- Maximum image size
- Output quality
- Scaling factor
- Processing parameters

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For any queries or suggestions, please open an issue in the GitHub repository.
