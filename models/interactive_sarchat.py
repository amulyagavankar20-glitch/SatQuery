import os
import sys
import glob
import json
import torch
import rasterio
import numpy as np
from PIL import Image
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from pathlib import Path
from transformers import AutoTokenizer, AutoModel

MODEL_PATH = os.getenv("SARCHAT_MODEL_PATH", str(Path.home() / ".cache" / "modelscope" / "models" / "JimmyMa99--SARChat-InternVL2.5-2B" / "snapshots" / "master"))
DATASET_DIR = os.getenv("DATASET_DIR", str(Path(__file__).resolve().parent.parent / "data" / "sentinel_dataset"))

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(input_size=448):
    return T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def sar_tif_to_rgb(tif_path):
    with rasterio.open(tif_path) as src:
        arr = src.read()

    if arr.shape[0] >= 2:
        vv = arr[0]
        vh = arr[1]
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
    return Image.fromarray(rgb)


def ask_sarchat(model, tokenizer, image, question, device="mps"):
    transform = build_transform(input_size=448)
    pixel_values = transform(image).unsqueeze(0).to(device)
    formatted_question = f"<image>\n{question}"
    gen_config = dict(max_new_tokens=300, do_sample=False)

    with torch.no_grad():
        response = model.chat(
            tokenizer=tokenizer,
            pixel_values=pixel_values,
            question=formatted_question,
            generation_config=gen_config
        )
    return response


def list_available_samples():
    samples = sorted(glob.glob(os.path.join(DATASET_DIR, "*/*")))
    sample_info = []
    for s in samples:
        meta_path = os.path.join(s, "metadata.json")
        city = os.path.basename(s)
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                    city = f"{meta.get('city', city)} ({meta.get('sample_id', '')})"
            except Exception:
                pass
        tifs = [f for f in os.listdir(s) if f.endswith(".tif")]
        sample_info.append({"path": s, "city": city, "tifs": tifs})
    return sample_info


def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading SARChat Model on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = AutoModel.from_pretrained(MODEL_PATH, torch_dtype=torch.float32, trust_remote_code=True).to(device)
    model.eval()
    print("✅ SARChat Ready!")

    samples = list_available_samples()

    if len(sys.argv) > 1:
        # Command-line mode: python interactive_sarchat.py <tif_path> "<question>"
        tif_path = sys.argv[1]
        question = sys.argv[2] if len(sys.argv) > 2 else "Describe the features in this SAR satellite image."
        print(f"\n📂 Image: {tif_path}")
        print(f"❓ Question: {question}")
        img = sar_tif_to_rgb(tif_path)
        ans = ask_sarchat(model, tokenizer, img, question, device=device)
        print(f"\n🤖 Answer:\n{ans}\n")
    else:
        print("\nAvailable Sentinel Samples:")
        for idx, s in enumerate(samples, 1):
            print(f"[{idx}] {s['city']} - Files: {', '.join(s['tifs'])}")

        print("\nUsage example:")
        print("python models/interactive_sarchat.py \"sentinel_dataset 6.01.03 PM/B1/B1_001/S1_T1.tif\" \"What objects are in this SAR image?\"")


if __name__ == "__main__":
    main()
