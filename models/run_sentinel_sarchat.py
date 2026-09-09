import os
import json
import glob
import torch
import rasterio
import numpy as np
from PIL import Image
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoTokenizer, AutoModel

MODEL_PATH = "/Users/dhanyahariya/.cache/modelscope/models/JimmyMa99--SARChat-InternVL2.5-2B/snapshots/master"
DATASET_DIR = "/Users/dhanyahariya/Downloads/satnav/sentinel_dataset 6.01.03 PM"

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(input_size=448):
    return T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
    best_ratio_diff = float('inf')
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio


def dynamic_preprocess(image, min_num=1, max_num=6, image_size=448, use_thumbnail=True):
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    target_ratios = set(
        (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
        i * j <= max_num and i * j >= min_num)
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size)

    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    resized_img = image.resize((target_width, target_height))
    processed_images = []
    for i in range(blocks):
        box = (
            (i % target_aspect_ratio[0]) * image_size,
            (i // target_aspect_ratio[0]) * image_size,
            ((i % target_aspect_ratio[0]) + 1) * image_size,
            ((i // target_aspect_ratio[0]) + 1) * image_size
        )
        split_img = resized_img.crop(box)
        processed_images.append(split_img)
    assert len(processed_images) == blocks
    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)
    return processed_images


def load_sar_image(tif_path, input_size=448, max_num=4):
    """
    Converts Sentinel-1 SAR GeoTIFF (VV, VH bands) to calibrated RGB representation
    and preprocesses it into pixel_values tensor.
    """
    with rasterio.open(tif_path) as src:
        arr = src.read()

    if arr.shape[0] >= 2:
        vv = arr[0]
        vh = arr[1]
        # Convert to dB scale
        vv_db = 10 * np.log10(np.clip(vv, 1e-5, None))
        vh_db = 10 * np.log10(np.clip(vh, 1e-5, None))

        vv_min, vv_max = np.percentile(vv_db, 2), np.percentile(vv_db, 98)
        vh_min, vh_max = np.percentile(vh_db, 2), np.percentile(vh_db, 98)

        r = np.clip((vv_db - vv_min) / (vv_max - vv_min + 1e-6), 0, 1)
        g = np.clip((vh_db - vh_min) / (vh_max - vh_min + 1e-6), 0, 1)
        b = np.clip(r / (g + 0.1), 0, 1)
        rgb = np.stack([r, g, b], axis=-1)
    else:
        v = arr[0]
        v_min, v_max = np.percentile(v, 2), np.percentile(v, 98)
        norm = np.clip((v - v_min) / (v_max - v_min + 1e-6), 0, 1)
        rgb = np.stack([norm, norm, norm], axis=-1)

    rgb = (rgb * 255).astype(np.uint8)
    image = Image.fromarray(rgb)

    transform = build_transform(input_size=input_size)
    images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = [transform(patch) for patch in images]
    pixel_values = torch.stack(pixel_values)
    return image, pixel_values


def load_optical_image(tif_path, input_size=448, max_num=4):
    """
    Converts Sentinel-2 Optical GeoTIFF (B2, B3, B4, B8) to true-color RGB.
    """
    with rasterio.open(tif_path) as src:
        arr = src.read()

    if arr.shape[0] >= 3:
        # B04 (Red), B03 (Green), B02 (Blue) -> bands 3, 2, 1
        r = arr[2].astype(np.float32)
        g = arr[1].astype(np.float32)
        b = arr[0].astype(np.float32)

        # Normalize 0-3000 reflectance to 0-1
        r_norm = np.clip(r / 3000.0, 0, 1)
        g_norm = np.clip(g / 3000.0, 0, 1)
        b_norm = np.clip(b / 3000.0, 0, 1)
        rgb = np.stack([r_norm, g_norm, b_norm], axis=-1)
    else:
        v = arr[0].astype(np.float32)
        norm = np.clip(v / np.percentile(v, 98), 0, 1)
        rgb = np.stack([norm, norm, norm], axis=-1)

    rgb = (rgb * 255).astype(np.uint8)
    image = Image.fromarray(rgb)

    transform = build_transform(input_size=input_size)
    images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = [transform(patch) for patch in images]
    pixel_values = torch.stack(pixel_values)
    return image, pixel_values


def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"🚀 Initializing SARChat on device: {device}")
    
    print(f"📦 Loading tokenizer from {MODEL_PATH}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    
    print(f"🧠 Loading SARChat model weights...")
    model = AutoModel.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.float32,
        trust_remote_code=True
    ).to(device)
    model.eval()
    print("✅ Model loaded successfully!\n")

    # Define test samples and questions
    test_cases = [
        {
            "sample_id": "B1_001",
            "city": "Mumbai",
            "tif": os.path.join(DATASET_DIR, "B1/B1_001/S1_T1.tif"),
            "questions": [
                "Describe the detailed features and objects visible in this SAR satellite image.",
                "Are there any bridges, water bodies, or dense urban structures in this SAR image?",
                "Analyze the radar backscatter intensity and identify the primary land cover types present in this area."
            ]
        },
        {
            "sample_id": "B1_003",
            "city": "Delhi",
            "tif": os.path.join(DATASET_DIR, "B1/B1_003/S1_T1.tif"),
            "questions": [
                "What kind of terrain and urban layout is visible in this SAR radar image?",
                "Identify any prominent linear features, infrastructure, or industrial zones in this SAR image."
            ]
        },
        {
            "sample_id": "B1_004",
            "city": "Bengaluru",
            "tif": os.path.join(DATASET_DIR, "B1/B1_004/S1_T1.tif"),
            "questions": [
                "Provide a comprehensive scene description of this Sentinel-1 SAR image.",
                "Is there evidence of built-up areas, vegetation, or open water bodies?"
            ]
        },
        {
            "sample_id": "B2_010",
            "city": "Kochi",
            "tif": os.path.join(DATASET_DIR, "B2/B2_010/S1_T1.tif"),
            "questions": [
                "Describe the coastal or water features and surrounding terrain in this SAR image.",
                "Can you detect any shipping channels, port infrastructure, or water-land boundaries?"
            ]
        }
    ]

    gen_config = dict(max_new_tokens=300, do_sample=False)

    print("=" * 70)
    print("🛰️  RUNNING SARCHAT INFERENCE ON SENTINEL DATASET")
    print("=" * 70)

    for case in test_cases:
        sample_id = case["sample_id"]
        city = case["city"]
        tif_path = case["tif"]

        if not os.path.exists(tif_path):
            print(f"⚠️ File not found: {tif_path}")
            continue

        print(f"\n📍 [SAMPLE: {sample_id} - {city}]")
        print(f"📁 Image Path: {tif_path}")

        # Load and preprocess
        img, pixel_values = load_sar_image(tif_path, input_size=448, max_num=4)
        pixel_values = pixel_values.to(device)
        num_patches = pixel_values.shape[0]

        for i, q in enumerate(case["questions"], 1):
            formatted_question = f"<image>\n{q}"
            print(f"\n❓ Question {i}: \"{q}\"")
            
            with torch.no_grad():
                response = model.chat(
                    tokenizer=tokenizer,
                    pixel_values=pixel_values,
                    question=formatted_question,
                    generation_config=gen_config,
                    num_patches_list=[num_patches]
                )
            
            print(f"🤖 SARChat Output:\n{response}")
            print("-" * 50)


if __name__ == "__main__":
    main()
