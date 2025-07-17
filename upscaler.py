import torch
from torchvision import transforms
from PIL import Image
import sys
from generator import Generator
def load_image(image_path):
    image = Image.open(image_path).convert('RGB')
    transform = transforms.ToTensor()
    return transform(image).unsqueeze(0)
def save_image(tensor, output_path):
    image = tensor.squeeze().clamp(0, 1).detach().cpu()
    image = transforms.ToPILImage()(image)
    image.save(output_path)
def upscale_image(input_path, output_path, model_path = "generator.pth"):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = Generator().to(device)
    model.load_state_dict(torch.load(model_path, map_location = device))
    model.eval()
    lr_image = load_image(input_path).to(device)
    with torch.no_grad():
        sr_image = model(lr_image)
    save_image(sr_image, output_path)
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Format: python upscaler.py <input_image> <output_path>")
        sys.exit(1)
    upscale_image(sys.argv[1], sys.argv[2])