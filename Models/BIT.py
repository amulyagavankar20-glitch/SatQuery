import torch

print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

!git clone https://github.com/likyoo/open-cd.git

%cd /content/open-cd

!ls

!ls configs/bit

!cat configs/bit/bit_r18_256x256_40k_levircd.py

!pip install -U openmim

import sys
print(sys.version)

!pip install -q uv

!uv venv --python 3.10 /content/opencd_env

!/content/opencd_env/bin/python --version

!/content/opencd_env/bin/python -m pip install -U pip setuptools wheel

!/content/opencd_env/bin/python -m pip install \
    torch==1.13.1+cu117 \
    torchvision==0.14.1+cu117 \
    torchaudio==0.13.1 \
    --extra-index-url https://download.pytorch.org/whl/cu117

!uv pip install --python /content/opencd_env/bin/python \
    torch==1.13.1+cu117 \
    torchvision==0.14.1+cu117 \
    torchaudio==0.13.1 \
    --extra-index-url https://download.pytorch.org/whl/cu117

!/content/opencd_env/bin/python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

!uv pip install --python /content/opencd_env/bin/python openmim

!/content/opencd_env/bin/python -c "import mim; print('OpenMIM installed successfully')"

!/content/opencd_env/bin/mim install mmengine==0.10.4

!/content/opencd_env/bin/mim install mmcv==2.1.0

!/content/opencd_env/bin/mim install mmpretrain==1.2.0

!uv pip install --python /content/opencd_env/bin/python mmsegmentation==1.2.2

!uv pip install --python /content/opencd_env/bin/python mmdet==3.3.0

%cd /content/open-cd
!uv pip install --python /content/opencd_env/bin/python -e .

!uv pip install --python /content/opencd_env/bin/python ftfy regex

%%writefile /tmp/check_opencd.py
import torch
import mmengine
import mmcv
import mmseg
import mmpretrain
import mmdet
import opencd

print("PyTorch:", torch.__version__)
print("CUDA:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name(0))
print("MMEngine:", mmengine.__version__)
print("MMCV:", mmcv.__version__)
print("MMSeg:", mmseg.__version__)
print("MMPretrain:", mmpretrain.__version__)
print("MMDetection:", mmdet.__version__)
print("Open-CD:", opencd.__version__)

%%writefile /tmp/test_opencd.py

from opencd.apis import OpenCDInferencer

print("OpenCDInferencer imported successfully!")

!uv pip install --python /content/opencd_env/bin/python "numpy<2"

!uv pip install --python /content/opencd_env/bin/python numpy==1.26.4

!/content/opencd_env/bin/python -c "import numpy; print('NumPy:', numpy.__version__)"

%%writefile /tmp/test_opencd.py

from opencd.apis import OpenCDInferencer

print("OpenCDInferencer imported successfully!")

%%writefile /tmp/test_opencd.py

import os
os.environ["MPLBACKEND"] = "Agg"

from opencd.apis import OpenCDInferencer

print("OpenCDInferencer imported successfully!")

!/content/opencd_env/bin/python /tmp/test_opencd.py

!uv pip install --python /content/opencd_env/bin/python gdown

!mkdir -p /content/open-cd/checkpoints/BIT_LEVIR

!/content/opencd_env/bin/gdown \
    https://drive.google.com/uc?id=1IVdF5a3e1_7DiSndtMkhpZuCSgDLLFcg \
    -O /content/open-cd/checkpoints/BIT_LEVIR/best_ckpt.pt

!ls -lh /content/open-cd/checkpoints/BIT_LEVIR/

%%writefile /tmp/inspect_bit_checkpoint.py

import torch

ckpt_path = "/content/open-cd/checkpoints/BIT_LEVIR/best_ckpt.pt"

print("Loading checkpoint...")
ckpt = torch.load(
    ckpt_path,
    map_location="cpu",
    weights_only=False
)

print("\nCheckpoint type:")
print(type(ckpt))

if isinstance(ckpt, dict):
    print("\nCheckpoint keys:")
    for key in ckpt.keys():
        print(" -", key)

    print("\nDetails:")
    for key, value in ckpt.items():
        if isinstance(value, dict):
            print(f"{key}: dictionary with {len(value)} entries")
        else:
            print(f"{key}: {type(value)}")

else:
    print("\nCheckpoint is not a dictionary.")

!/content/opencd_env/bin/python /tmp/inspect_bit_checkpoint.py

%%writefile /tmp/inspect_bit_weights.py

import torch

ckpt_path = "/content/open-cd/checkpoints/BIT_LEVIR/best_ckpt.pt"

ckpt = torch.load(
    ckpt_path,
    map_location="cpu",
    weights_only=False
)

state_dict = ckpt["model_G_state_dict"]

print("Number of parameters:", len(state_dict))
print("\nFirst 40 parameter names:\n")

for i, (name, tensor) in enumerate(state_dict.items()):
    if i >= 40:
        break
    print(f"{i+1:02d}. {name:60s} {tuple(tensor.shape)}")

!/content/opencd_env/bin/python /tmp/inspect_bit_weights.py

!git clone https://github.com/justchenhao/BIT_CD.git /content/BIT_CD

!ls /content/BIT_CD

!mkdir -p /content/BIT_CD/checkpoints/BIT_LEVIR

!cp /content/open-cd/checkpoints/BIT_LEVIR/best_ckpt.pt \
    /content/BIT_CD/checkpoints/BIT_LEVIR/best_ckpt.pt

!ls -lh /content/BIT_CD/checkpoints/BIT_LEVIR/

!find /content/BIT_CD/samples -maxdepth 2 -type f | head -30

!find /content/BIT_CD/samples/A -type f
!find /content/BIT_CD/samples/B -type f

from PIL import Image
import matplotlib.pyplot as plt
import glob
import os

A_files = sorted(glob.glob("/content/BIT_CD/samples/A/*"))
B_files = sorted(glob.glob("/content/BIT_CD/samples/B/*"))

print("T1 images:", len(A_files))
print("T2 images:", len(B_files))

print("First T1:", A_files[0])
print("First T2:", B_files[0])

imgA = Image.open(A_files[0])
imgB = Image.open(B_files[0])

print("T1 size:", imgA.size)
print("T2 size:", imgB.size)

fig, ax = plt.subplots(1, 2, figsize=(12, 5))

ax[0].imshow(imgA)
ax[0].set_title("T1")
ax[0].axis("off")

ax[1].imshow(imgB)
ax[1].set_title("T2")
ax[1].axis("off")

plt.show()

!sed -n '1,240p' /content/BIT_CD/demo.py

# Fix 1: make sure Python recognizes BIT's datasets package
!touch /content/BIT_CD/datasets/__init__.py

# Fix 2: torchvision moved this function
!sed -i 's/from torchvision.models.utils import load_state_dict_from_url/from torch.hub import load_state_dict_from_url/' /content/BIT_CD/models/resnet.py

# Fix 3: np.str was removed in NumPy 1.24+
!sed -i 's/dtype=np.str/dtype=str/' /content/BIT_CD/datasets/CD_dataset.py

print("BIT compatibility fixes applied.")

%%writefile /tmp/test_bit_import.py

import sys

sys.path.insert(0, "/content/BIT_CD")

from models.basic_model import CDEvaluator

print("BIT CDEvaluator imported successfully!")

!uv pip install --python /content/opencd_env/bin/python tifffile==2023.7.10

!/content/opencd_env/bin/python /tmp/test_bit_import.py

from pathlib import Path

path = Path("/content/BIT_CD/models/basic_model.py")

text = path.read_text()

old = 'torch.load(load_path, map_location=self.device)'
new = 'torch.load(load_path, map_location=self.device, weights_only=False)'

if old in text:
    text = text.replace(old, new)
    path.write_text(text)
    print("Checkpoint loading patched.")
else:
    print("The expected torch.load line was not found.")

%cd /content/BIT_CD

!/content/opencd_env/bin/python demo.py \
    --project_name BIT_LEVIR \
    --checkpoint_root checkpoints \
    --output_folder samples/predict \
    --data_name quick_start \
    --split demo \
    --img_size 256 \
    --net_G base_transformer_pos_s4_dd8_dedim8 \
    --checkpoint_name best_ckpt.pt \
    --gpu_ids 0 \
    --batch_size 1 \
    --num_workers 0

!find /content/BIT_CD/samples/predict -maxdepth 1 -type f -print

!ls -lh /content/BIT_CD/samples/predict

from PIL import Image
import matplotlib.pyplot as plt
import glob
import os

A_files = sorted(glob.glob("/content/BIT_CD/samples/A/*.png"))
B_files = sorted(glob.glob("/content/BIT_CD/samples/B/*.png"))
L_files = sorted(glob.glob("/content/BIT_CD/samples/label/*.png"))
P_files = sorted(glob.glob("/content/BIT_CD/samples/predict/*.png"))

print("T1 images:", len(A_files))
print("T2 images:", len(B_files))
print("Ground truth:", len(L_files))
print("Predictions:", len(P_files))

print("\nPredictions:")
for f in P_files:
    print(os.path.basename(f))

from PIL import Image
import matplotlib.pyplot as plt

pred_path = "/content/BIT_CD/samples/predict/test_121_0768_0256.png"

pred = Image.open(pred_path)

print("Prediction size:", pred.size)
print("Prediction mode:", pred.mode)

plt.figure(figsize=(7, 7))
plt.imshow(pred, cmap="gray")
plt.title("BiT Change Detection Output")
plt.axis("off")
plt.show()

from PIL import Image
import matplotlib.pyplot as plt
import os

name = "test_121_0768_0256.png"

A = Image.open(f"/content/BIT_CD/samples/A/{name}")
B = Image.open(f"/content/BIT_CD/samples/B/{name}")
GT = Image.open(f"/content/BIT_CD/samples/label/{name}")
P = Image.open(f"/content/BIT_CD/samples/predict/{name}")

fig, ax = plt.subplots(1, 4, figsize=(20, 5))

ax[0].imshow(A)
ax[0].set_title("T1 — Before")
ax[0].axis("off")

ax[1].imshow(B)
ax[1].set_title("T2 — After")
ax[1].axis("off")

ax[2].imshow(GT, cmap="gray")
ax[2].set_title("Ground Truth")
ax[2].axis("off")

ax[3].imshow(P, cmap="gray")
ax[3].set_title("BiT Prediction")
ax[3].axis("off")

plt.tight_layout()
plt.show()

import glob
import os

pred_files = sorted(
    glob.glob("/content/BIT_CD/samples/predict/*.png")
)

for i, f in enumerate(pred_files):
    print(i, os.path.basename(f))

!sed -n '1,240p' /content/BIT_CD/datasets/CD_dataset.py

%%writefile /tmp/inspect_bit_input.py

import sys
import torch
import numpy as np
from PIL import Image

sys.path.insert(0, "/content/BIT_CD")

from datasets.CD_dataset import CDDataAugmentation

name = "test_121_0768_0256.png"

A_path = f"/content/BIT_CD/samples/A/{name}"
B_path = f"/content/BIT_CD/samples/B/{name}"

# Load original images
img_A = Image.open(A_path).convert("RGB")
img_B = Image.open(B_path).convert("RGB")

print("Original A:")
print("  size:", img_A.size)
print("  mode:", img_A.mode)

print("Original B:")
print("  size:", img_B.size)
print("  mode:", img_B.mode)

# Convert PIL -> NumPy
img_A = np.asarray(img_A)
img_B = np.asarray(img_B)

print("\nBefore preprocessing:")
print("  A shape:", img_A.shape)
print("  B shape:", img_B.shape)
print("  A dtype:", img_A.dtype)
print("  B dtype:", img_B.dtype)

# BIT preprocessing
aug = CDDataAugmentation(img_size=256)

[img_A, img_B], _ = aug.transform(
    [img_A, img_B],
    [],
    to_tensor=True
)

print("\nAfter preprocessing:")
print("  A shape:", img_A.shape)
print("  B shape:", img_B.shape)
print("  A dtype:", img_A.dtype)
print("  B dtype:", img_B.dtype)
print("  A min/max:", img_A.min().item(), img_A.max().item())
print("  B min/max:", img_B.min().item(), img_B.max().item())

# Add batch dimension
A_batch = img_A.unsqueeze(0)
B_batch = img_B.unsqueeze(0)

print("\nActual model input:")
print("  A batch shape:", A_batch.shape)
print("  B batch shape:", B_batch.shape)

!/content/opencd_env/bin/python /tmp/inspect_bit_input.py

from PIL import Image
import numpy as np
import os

name = "test_121_0768_0256.png"

pred_path = f"/content/BIT_CD/samples/predict/{name}"
gt_path = f"/content/BIT_CD/samples/label/{name}"

pred = np.array(Image.open(pred_path))
gt = np.array(Image.open(gt_path))

print("Prediction")
print("-----------")
print("Shape:", pred.shape)
print("Dtype:", pred.dtype)
print("Unique values:", np.unique(pred))

print("\nGround Truth")
print("------------")
print("Shape:", gt.shape)
print("Dtype:", gt.dtype)
print("Unique values:", np.unique(gt))

# Convert to binary masks
pred_mask = pred > 0
gt_mask = gt > 0

print("\nPrediction statistics")
print("---------------------")
print("Total pixels:", pred_mask.size)
print("Changed pixels:", pred_mask.sum())
print("Unchanged pixels:", (~pred_mask).sum())
print("Changed percentage:", round(pred_mask.mean() * 100, 2), "%")

print("\nGround Truth statistics")
print("-----------------------")
print("Changed pixels:", gt_mask.sum())
print("Changed percentage:", round(gt_mask.mean() * 100, 2), "%")

from PIL import Image
import numpy as np
import os

name = "test_121_0768_0256.png"

A_path = f"/content/BIT_CD/samples/A/{name}"
B_path = f"/content/BIT_CD/samples/B/{name}"
pred_path = f"/content/BIT_CD/samples/predict/{name}"

# Load images
A = Image.open(A_path).convert("RGB")
B = Image.open(B_path).convert("RGB")

# Prediction mask
pred = np.array(Image.open(pred_path))
mask = pred > 0

# Convert B to numpy
B_np = np.array(B).copy()

# Create red overlay
overlay = B_np.copy()

# Red color for detected changes
overlay[mask] = [255, 0, 0]

# Blend original + red mask
blended = (
    0.55 * B_np +
    0.45 * overlay
).astype(np.uint8)

# Save
output_dir = "/content/BIT_CD/samples/satquery_output"
os.makedirs(output_dir, exist_ok=True)

overlay_path = f"{output_dir}/{name.replace('.png', '_overlay.png')}"
Image.fromarray(blended).save(overlay_path)

print("Saved:", overlay_path)

from IPython.display import display

display(Image.open(overlay_path))

import numpy as np
import cv2

# Binary mask
binary = (pred > 0).astype(np.uint8)

# Find connected regions
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
    binary,
    connectivity=8
)

# Ignore background
regions = []

for i in range(1, num_labels):
    area = stats[i, cv2.CC_STAT_AREA]

    # Ignore extremely tiny noise
    if area >= 20:
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]

        regions.append({
            "area": int(area),
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h)
        })

changed_pixels = binary.sum()
total_pixels = binary.size
change_percent = changed_pixels / total_pixels * 100

print("SATQUERY CHANGE ANALYSIS")
print("========================")
print("Image:", name)
print("Changed pixels:", changed_pixels)
print("Total pixels:", total_pixels)
print("Changed area:", round(change_percent, 2), "%")
print("Significant change regions:", len(regions))

print("\nRegions:")

for i, r in enumerate(regions, 1):
    print(
        f"Region {i}: "
        f"area={r['area']} pixels, "
        f"location=({r['x']},{r['y']}), "
        f"size={r['width']}x{r['height']}"
    )

# Basic natural-language inference
if change_percent < 1:
    magnitude = "very little"
elif change_percent < 5:
    magnitude = "a small amount of"
elif change_percent < 15:
    magnitude = "a moderate amount of"
else:
    magnitude = "a substantial amount of"

if len(regions) == 0:
    sentence = (
        "BIT detected no significant areas of change "
        "between the two images."
    )
else:
    sentence = (
        f"BIT detected {magnitude} change between the two images. "
        f"Approximately {change_percent:.1f}% of the image area "
        f"is classified as changed, concentrated in "
        f"{len(regions)} significant region"
        f"{'' if len(regions) == 1 else 's'}."
    )

print("\nTEXT INFERENCE")
print("--------------")
print(sentence)

import cv2
import numpy as np
from PIL import Image
from IPython.display import display

name = "test_121_0768_0256.png"

B_path = f"/content/BIT_CD/samples/B/{name}"
pred_path = f"/content/BIT_CD/samples/predict/{name}"

# Load AFTER image
B = np.array(Image.open(B_path).convert("RGB"))

# Load BIT prediction
pred = np.array(Image.open(pred_path))

# Binary change mask
mask = (pred > 0).astype(np.uint8)

# Find connected components
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
    mask,
    connectivity=8
)

# Create visualization
visual = B.copy()

# Find regions
regions = []

for i in range(1, num_labels):

    x = stats[i, cv2.CC_STAT_LEFT]
    y = stats[i, cv2.CC_STAT_TOP]
    w = stats[i, cv2.CC_STAT_WIDTH]
    h = stats[i, cv2.CC_STAT_HEIGHT]
    area = stats[i, cv2.CC_STAT_AREA]

    # Ignore tiny noise
    if area < 100:
        continue

    regions.append((x, y, w, h, area))

    # Draw rectangle
    cv2.rectangle(
        visual,
        (x, y),
        (x + w, y + h),
        (255, 0, 0),
        2
    )

    # Region number
    cv2.putText(
        visual,
        f"R{len(regions)}",
        (x, max(y - 5, 15)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 0, 0),
        1,
        cv2.LINE_AA
    )

print("SIGNIFICANT CHANGE REGIONS")
print("==========================")

for i, (x, y, w, h, area) in enumerate(regions, 1):
    print(
        f"Region {i}: "
        f"x={x}, y={y}, "
        f"width={w}, height={h}, "
        f"area={area}"
    )

print("\nTotal significant regions:", len(regions))

# Display
display(Image.fromarray(visual))

%%writefile /content/BIT_CD/satquery_detector.py

import os
import sys
import cv2
import torch
import numpy as np

from PIL import Image

# --------------------------------------------------
# BIT PATH
# --------------------------------------------------

BIT_ROOT = "/content/BIT_CD"

if BIT_ROOT not in sys.path:
    sys.path.insert(0, BIT_ROOT)

from datasets.CD_dataset import CDDataAugmentation
from models.basic_model import CDEvaluator


class SatQueryBIT:

    def __init__(
        self,
        checkpoint_name="best_ckpt.pt",
        gpu_id=0,
        img_size=256
    ):

        self.img_size = img_size

        # ------------------------------------------
        # Device
        # ------------------------------------------

        if torch.cuda.is_available():
            self.device = torch.device(f"cuda:{gpu_id}")
        else:
            self.device = torch.device("cpu")

        print("Device:", self.device)

        # ------------------------------------------
        # Create BIT arguments
        # ------------------------------------------

        class Args:
            pass

        args = Args()

        args.gpu_ids = [gpu_id] if torch.cuda.is_available() else []
        args.checkpoint_root = os.path.join(
            BIT_ROOT,
            "checkpoints"
        )

        args.project_name = "BIT_LEVIR"

        args.checkpoint_dir = os.path.join(
            args.checkpoint_root,
            args.project_name
        )

        args.net_G = "base_transformer_pos_s4_dd8_dedim8"

        args.n_class = 2
        args.embed_dim = 256
        args.img_size = img_size

        # ------------------------------------------
        # Load evaluator
        # ------------------------------------------

        self.model = CDEvaluator(args)

        self.model.load_checkpoint(checkpoint_name)

        self.model.eval()

        print("BIT model loaded successfully.")

    # ==================================================
    # LOAD + PREPROCESS IMAGE
    # ==================================================

    def preprocess(self, image_path):

        image = Image.open(image_path).convert("RGB")

        original_size = image.size

        image = np.asarray(image)

        aug = CDDataAugmentation(
            img_size=self.img_size
        )

        [image], _ = aug.transform(
            [image],
            [],
            to_tensor=True
        )

        image = image.unsqueeze(0)

        return image, original_size

    # ==================================================
    # RUN BIT
    # ==================================================

    def predict(self, before_path, after_path):

        print("\nRunning BIT...")
        print("Before:", before_path)
        print("After :", after_path)

        # ------------------------------------------
        # Load images
        # ------------------------------------------

        before, before_size = self.preprocess(
            before_path
        )

        after, after_size = self.preprocess(
            after_path
        )

        # ------------------------------------------
        # Move to GPU/CPU
        # ------------------------------------------

        before = before.to(self.device)
        after = after.to(self.device)

        # ------------------------------------------
        # Create BIT batch
        # ------------------------------------------

        batch = {
            "A": before,
            "B": after
        }

        # ------------------------------------------
        # Run model
        # ------------------------------------------

        with torch.no_grad():

            self.model._forward_pass(batch)

            # BIT internally produces prediction
            prediction = self.model.G_pred

        # ------------------------------------------
        # Convert prediction to numpy
        # ------------------------------------------

        prediction = prediction.detach().cpu().numpy()

        # ------------------------------------------
        # Handle output shape
        # ------------------------------------------

        if prediction.ndim == 4:

            prediction = prediction[0]

            if prediction.shape[0] == 2:
                prediction = np.argmax(
                    prediction,
                    axis=0
                )

            else:
                prediction = prediction[0]

        elif prediction.ndim == 3:

            prediction = prediction[0]

        # ------------------------------------------
        # Binary mask
        # ------------------------------------------

        mask = (
            prediction > 0
        ).astype(np.uint8)

        return {
            "mask": mask,
            "before_size": before_size,
            "after_size": after_size
        }

    # ==================================================
    # ANALYZE MASK
    # ==================================================

    def analyze_mask(self, mask):

        total_pixels = mask.size

        changed_pixels = int(
            mask.sum()
        )

        unchanged_pixels = (
            total_pixels -
            changed_pixels
        )

        change_percentage = (
            changed_pixels /
            total_pixels *
            100
        )

        # ------------------------------------------
        # Connected regions
        # ------------------------------------------

        num_labels, labels, stats, centroids = (
            cv2.connectedComponentsWithStats(
                mask,
                connectivity=8
            )
        )

        regions = []

        for i in range(1, num_labels):

            x = stats[
                i,
                cv2.CC_STAT_LEFT
            ]

            y = stats[
                i,
                cv2.CC_STAT_TOP
            ]

            width = stats[
                i,
                cv2.CC_STAT_WIDTH
            ]

            height = stats[
                i,
                cv2.CC_STAT_HEIGHT
            ]

            area = stats[
                i,
                cv2.CC_STAT_AREA
            ]

            # Ignore tiny noise
            if area < 100:
                continue

            regions.append({
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
                "area": int(area)
            })

        return {
            "total_pixels": int(total_pixels),
            "changed_pixels": changed_pixels,
            "unchanged_pixels": int(unchanged_pixels),
            "change_percentage": float(
                change_percentage
            ),
            "regions": regions
        }

    # ==================================================
    # CREATE OVERLAY
    # ==================================================

    def create_overlay(
        self,
        after_path,
        mask,
        output_path
    ):

        after = np.array(
            Image.open(after_path).convert("RGB")
        )

        # Resize mask if necessary
        if (
            mask.shape[1],
            mask.shape[0]
        ) != (
            after.shape[1],
            after.shape[0]
        ):

            mask = cv2.resize(
                mask,
                (
                    after.shape[1],
                    after.shape[0]
                ),
                interpolation=cv2.INTER_NEAREST
            )

        overlay = after.copy()

        # Red change regions
        overlay[mask > 0] = [
            255,
            0,
            0
        ]

        # Blend
        result = cv2.addWeighted(
            after,
            0.55,
            overlay,
            0.45,
            0
        )

        Image.fromarray(result).save(
            output_path
        )

        return output_path

    # ==================================================
    # GENERATE TEXT
    # ==================================================

    def generate_text(
        self,
        analysis
    ):

        percentage = analysis[
            "change_percentage"
        ]

        region_count = len(
            analysis["regions"]
        )

        if percentage < 1:
            magnitude = "very little"

        elif percentage < 5:
            magnitude = "a small amount of"

        elif percentage < 15:
            magnitude = "a moderate amount of"

        else:
            magnitude = "a substantial amount of"

        if region_count == 0:

            return (
                "No significant change "
                "was detected between "
                "the two images."
            )

        region_word = (
            "region"
            if region_count == 1
            else "regions"
        )

        return (
            f"BIT detected {magnitude} "
            f"change between the two images. "
            f"Approximately "
            f"{percentage:.1f}% of the image "
            f"area is classified as changed, "
            f"concentrated in "
            f"{region_count} significant "
            f"{region_word}."
        )

    # ==================================================
    # COMPLETE PIPELINE
    # ==================================================

    def analyze(
        self,
        before_path,
        after_path,
        output_dir="/content/BIT_CD/samples/satquery_output"
    ):

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        # ------------------------------------------
        # BIT prediction
        # ------------------------------------------

        result = self.predict(
            before_path,
            after_path
        )

        mask = result["mask"]

        # ------------------------------------------
        # Statistics
        # ------------------------------------------

        analysis = self.analyze_mask(
            mask
        )

        # ------------------------------------------
        # Overlay
        # ------------------------------------------

        overlay_path = os.path.join(
            output_dir,
            "change_overlay.png"
        )

        self.create_overlay(
            after_path,
            mask,
            overlay_path
        )

        # ------------------------------------------
        # Text
        # ------------------------------------------

        text = self.generate_text(
            analysis
        )

        return {
            "mask": mask,
            "overlay_path": overlay_path,
            "statistics": analysis,
            "text": text
        }

# Add the missing output_folder argument to our SatQuery BIT engine

path = "/content/BIT_CD/satquery_detector.py"

with open(path, "r") as f:
    code = f.read()

old = '''        args.checkpoint_dir = os.path.join(
            args.checkpoint_root,
            args.project_name
        )

        args.net_G = "base_transformer_pos_s4_dd8_dedim8"
'''

new = '''        args.checkpoint_dir = os.path.join(
            args.checkpoint_root,
            args.project_name
        )

        # BIT's CDEvaluator expects an output_folder
        args.output_folder = os.path.join(
            BIT_ROOT,
            "samples",
            "satquery_output"
        )

        os.makedirs(args.output_folder, exist_ok=True)

        args.net_G = "base_transformer_pos_s4_dd8_dedim8"
'''

if old not in code:
    print("Expected code section not found.")
else:
    code = code.replace(old, new)

    with open(path, "w") as f:
        f.write(code)

    print("Fixed: args.output_folder added.")

!grep -n "torch.load" /content/BIT_CD/models/basic_model.py

path = "/content/BIT_CD/models/basic_model.py"

with open(path, "r") as f:
    code = f.read()

code = code.replace(
    "torch.load(self.checkpoint_dir + '/' + name)",
    "torch.load(self.checkpoint_dir + '/' + name, weights_only=False)"
)

with open(path, "w") as f:
    f.write(code)

print("Patched torch.load for the trusted BIT checkpoint.")

path = "/content/BIT_CD/models/basic_model.py"

with open(path, "r") as f:
    code = f.read()

old = """checkpoint = torch.load(os.path.join(self.checkpoint_dir, checkpoint_name),"""

new = """checkpoint = torch.load(
            os.path.join(self.checkpoint_dir, checkpoint_name),
            weights_only=False
        )"""

if old in code:
    code = code.replace(old, new)

    with open(path, "w") as f:
        f.write(code)

    print("SUCCESS: torch.load patched with weights_only=False")
else:
    print("Could not find the expected line.")
    print("Current torch.load line:")
    for line in code.splitlines():
        if "torch.load" in line:
            print(line)

from pathlib import Path
import re

path = Path("/content/BIT_CD/models/basic_model.py")

text = path.read_text()

# Find the entire load_checkpoint() function
pattern = r"    def load_checkpoint\(.*?(?=\n    def |\Z)"

replacement = """    def load_checkpoint(self, checkpoint_name='best_ckpt.pt'):
        if os.path.exists(os.path.join(self.checkpoint_dir, checkpoint_name)):
            # load the entire checkpoint
            checkpoint = torch.load(
                os.path.join(self.checkpoint_dir, checkpoint_name),
                map_location=self.device,
                weights_only=False
            )

            self.net_G.load_state_dict(
                checkpoint['model_G_state_dict']
            )
            self.net_G.to(self.device)

            # update some other states
            if 'optimizer_G_state_dict' in checkpoint:
                self.optimizer_G.load_state_dict(
                    checkpoint['optimizer_G_state_dict']
                )

            if 'exp_lr_scheduler_G_state_dict' in checkpoint:
                self.exp_lr_scheduler_G.load_state_dict(
                    checkpoint['exp_lr_scheduler_G_state_dict']
                )

            print('Checkpoint loaded:', checkpoint_name)
        else:
            raise FileNotFoundError(
                f'Checkpoint not found: '
                f'{os.path.join(self.checkpoint_dir, checkpoint_name)}'
            )
"""

new_text, count = re.subn(
    pattern,
    replacement,
    text,
    count=1,
    flags=re.DOTALL
)

if count == 1:
    path.write_text(new_text)
    print("SUCCESS: load_checkpoint() completely replaced.")
else:
    print("ERROR: load_checkpoint() was not found.")

!sed -n '25,65p' /content/BIT_CD/models/basic_model.py

from pathlib import Path
import re

path = Path("/content/BIT_CD/models/basic_model.py")
text = path.read_text()

pattern = r"    def load_checkpoint\(.*?(?=\n    def |\Z)"

replacement = """    def load_checkpoint(self, checkpoint_name='best_ckpt.pt'):
        if os.path.exists(os.path.join(self.checkpoint_dir, checkpoint_name)):
            checkpoint = torch.load(
                os.path.join(self.checkpoint_dir, checkpoint_name),
                map_location=self.device,
                weights_only=False
            )

            self.net_G.load_state_dict(
                checkpoint['model_G_state_dict']
            )

            self.net_G.to(self.device)

            self.best_val_acc = checkpoint.get(
                'best_val_acc', 0.0
            )

            self.best_epoch_id = checkpoint.get(
                'best_epoch_id', 0
            )

            print('Checkpoint loaded:', checkpoint_name)

        else:
            raise FileNotFoundError(
                'no such checkpoint %s' % checkpoint_name
            )

        return self.net_G
"""

new_text, count = re.subn(
    pattern,
    replacement,
    text,
    count=1,
    flags=re.DOTALL
)

if count == 1:
    path.write_text(new_text)
    print("SUCCESS: CDEvaluator checkpoint loader restored.")
else:
    print("ERROR: Could not find load_checkpoint().")

import importlib
import models.basic_model

importlib.reload(models.basic_model)

print("basic_model reloaded.")

import satquery_detector

importlib.reload(satquery_detector)

from satquery_detector import SatQueryBIT

detector = SatQueryBIT()

from pathlib import Path

path = Path("/content/BIT_CD/satquery_detector.py")
text = path.read_text()

# Fix the broken print statement
bad = 'print("\nRunning BIT...")'
good = 'print("\\nRunning BIT...")'

if bad in text:
    text = text.replace(bad, good)
    path.write_text(text)
    print("Fixed the broken print statement.")
else:
    print("Broken print statement not found.")

%cd /content/BIT_CD

!nl -ba satquery_detector.py | sed -n '123,130p'

!/content/opencd_env/bin/python -m py_compile satquery_detector.py

import importlib
import satquery_detector

importlib.reload(satquery_detector)

from satquery_detector import SatQueryBIT

print("satquery_detector reloaded successfully")

before = "/content/BIT_CD/samples/A/test_121_0768_0256.png"
after = "/content/BIT_CD/samples/B/test_121_0768_0256.png"

detector = SatQueryBIT()

result = detector.predict(before, after)

import os
from google.colab import files

# Create a dedicated input folder
input_dir = "/content/satquery_inputs"
os.makedirs(input_dir, exist_ok=True)

# Make sure uploads happen from /content
%cd /content

print("Upload BEFORE / T1 image")
before_upload = files.upload()

print("\nUpload AFTER / T2 image")
after_upload = files.upload()

# Get filenames
before_name = next(iter(before_upload))
after_name = next(iter(after_upload))

# Full paths
before_path = os.path.join(input_dir, before_name)
after_path = os.path.join(input_dir, after_name)

# Move uploaded files into SatQuery input folder
os.rename(
    os.path.join("/content", before_name),
    before_path
)

os.rename(
    os.path.join("/content", after_name),
    after_path
)

print("\n==============================")
print("SATQUERY INPUTS")
print("==============================")
print("Before:", before_path)
print("After :", after_path)

print("\nFiles exist?")
print("Before:", os.path.isfile(before_path))
print("After :", os.path.isfile(after_path))

result = detector.predict(
    before_path,
    after_path
)

print("\nPrediction completed!")

import numpy as np

mask = result["mask"]

print("========== BIT OUTPUT ==========")
print("Mask shape:", mask.shape)
print("Mask dtype:", mask.dtype)
print("Unique values:", np.unique(mask))
print("Changed pixels:", int(mask.sum()))
print("Total pixels:", mask.size)

change_percentage = (mask.sum() / mask.size) * 100
print("Changed area:", round(change_percentage, 2), "%")

analysis_result = detector.analyze(
    before_path,
    after_path
)

print("========== SATQUERY ANALYSIS ==========")

print("\nTEXT:")
print(analysis_result["text"])

print("\nSTATISTICS:")
print(analysis_result["statistics"])

print("\nOVERLAY:")
print(analysis_result["overlay_path"])

from PIL import Image
from IPython.display import display

display(Image.open(analysis_result["overlay_path"]))

import cv2
import numpy as np

mask = result["mask"].astype(np.uint8)

# Find connected changed regions
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
    mask,
    connectivity=8
)

regions = []

# Ignore label 0 because it represents the background
for i in range(1, num_labels):

    x = int(stats[i, cv2.CC_STAT_LEFT])
    y = int(stats[i, cv2.CC_STAT_TOP])
    w = int(stats[i, cv2.CC_STAT_WIDTH])
    h = int(stats[i, cv2.CC_STAT_HEIGHT])
    area = int(stats[i, cv2.CC_STAT_AREA])

    regions.append({
        "id": len(regions) + 1,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "area": area
    })

# Sort largest regions first
regions = sorted(
    regions,
    key=lambda r: r["area"],
    reverse=True
)

print("========== CHANGED REGIONS ==========")
print("Total regions:", len(regions))

for region in regions:
    print(
        f"Region {region['id']}: "
        f"x={region['x']}, "
        f"y={region['y']}, "
        f"w={region['width']}, "
        f"h={region['height']}, "
        f"area={region['area']}"
    )

import cv2
from PIL import Image
from IPython.display import display

# Load AFTER image
after_img = cv2.imread(after_path)

# Draw boxes
for region in regions:

    x = region["x"]
    y = region["y"]
    w = region["width"]
    h = region["height"]

    cv2.rectangle(
        after_img,
        (x, y),
        (x + w, y + h),
        (0, 0, 255),
        2
    )

    cv2.putText(
        after_img,
        f"R{region['id']}",
        (x, max(y - 5, 15)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 255),
        1
    )

# Convert BGR → RGB
after_img = cv2.cvtColor(after_img, cv2.COLOR_BGR2RGB)

display(Image.fromarray(after_img))

import cv2
import numpy as np

mask = result["mask"].astype(np.uint8)

num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
    mask,
    connectivity=8
)

MIN_AREA = 100

regions = []

for i in range(1, num_labels):

    x = int(stats[i, cv2.CC_STAT_LEFT])
    y = int(stats[i, cv2.CC_STAT_TOP])
    w = int(stats[i, cv2.CC_STAT_WIDTH])
    h = int(stats[i, cv2.CC_STAT_HEIGHT])
    area = int(stats[i, cv2.CC_STAT_AREA])

    if area < MIN_AREA:
        continue

    regions.append({
        "id": len(regions) + 1,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "area": area
    })

regions = sorted(
    regions,
    key=lambda r: r["area"],
    reverse=True
)

print("========== FILTERED REGIONS ==========")
print("Minimum area:", MIN_AREA)
print("Significant regions:", len(regions))

for region in regions:
    print(
        f"R{region['id']}: "
        f"x={region['x']}, "
        f"y={region['y']}, "
        f"width={region['width']}, "
        f"height={region['height']}, "
        f"area={region['area']}"
    )

import cv2
from PIL import Image
from IPython.display import display

after_img = cv2.imread(after_path)

for region in regions:

    x = region["x"]
    y = region["y"]
    w = region["width"]
    h = region["height"]

    cv2.rectangle(
        after_img,
        (x, y),
        (x + w, y + h),
        (0, 0, 255),
        2
    )

    cv2.putText(
        after_img,
        f"R{region['id']}",
        (x, max(y - 5, 15)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 255),
        1
    )

after_img = cv2.cvtColor(
    after_img,
    cv2.COLOR_BGR2RGB
)

display(Image.fromarray(after_img))

import cv2
import numpy as np

mask = result["mask"].astype(np.uint8)

# Convert binary mask to 0-255
mask_uint8 = mask * 255

# Connect nearby changed pixels
kernel = np.ones((7, 7), np.uint8)

clean_mask = cv2.morphologyEx(
    mask_uint8,
    cv2.MORPH_CLOSE,
    kernel
)

# Remove small isolated noise
clean_mask = cv2.morphologyEx(
    clean_mask,
    cv2.MORPH_OPEN,
    np.ones((3, 3), np.uint8)
)

# Convert back to binary
clean_mask = (clean_mask > 0).astype(np.uint8)

# Find regions again
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
    clean_mask,
    connectivity=8
)

MIN_AREA = 200

clean_regions = []

for i in range(1, num_labels):

    x = int(stats[i, cv2.CC_STAT_LEFT])
    y = int(stats[i, cv2.CC_STAT_TOP])
    w = int(stats[i, cv2.CC_STAT_WIDTH])
    h = int(stats[i, cv2.CC_STAT_HEIGHT])
    area = int(stats[i, cv2.CC_STAT_AREA])

    if area < MIN_AREA:
        continue

    clean_regions.append({
        "id": len(clean_regions) + 1,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "area": area
    })

clean_regions = sorted(
    clean_regions,
    key=lambda r: r["area"],
    reverse=True
)

print("========== CLEAN REGIONS ==========")
print("Regions:", len(clean_regions))

for r in clean_regions:
    print(
        f"R{r['id']}: "
        f"x={r['x']}, "
        f"y={r['y']}, "
        f"w={r['width']}, "
        f"h={r['height']}, "
        f"area={r['area']}"
    )

from PIL import Image
from IPython.display import display

after_img = cv2.imread(after_path)

for r in clean_regions:

    x = r["x"]
    y = r["y"]
    w = r["width"]
    h = r["height"]

    cv2.rectangle(
        after_img,
        (x, y),
        (x + w, y + h),
        (0, 0, 255),
        2
    )

    cv2.putText(
        after_img,
        f"R{r['id']}",
        (x, max(y - 5, 15)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 255),
        1
    )

after_img = cv2.cvtColor(
    after_img,
    cv2.COLOR_BGR2RGB
)

display(Image.fromarray(after_img))

from PIL import Image
from pathlib import Path

before_img = Image.open(before_path).convert("RGB")
after_img = Image.open(after_path).convert("RGB")

crop_dir = Path("/content/satquery_inputs/regions")
crop_dir.mkdir(parents=True, exist_ok=True)

padding = 10

region_crops = []

for r in clean_regions:

    x = r["x"]
    y = r["y"]
    w = r["width"]
    h = r["height"]

    # Add context around the detected region
    left = max(0, x - padding)
    top = max(0, y - padding)
    right = min(256, x + w + padding)
    bottom = min(256, y + h + padding)

    before_crop = before_img.crop(
        (left, top, right, bottom)
    )

    after_crop = after_img.crop(
        (left, top, right, bottom)
    )

    region_id = r["id"]

    before_crop_path = crop_dir / f"R{region_id}_before.png"
    after_crop_path = crop_dir / f"R{region_id}_after.png"

    before_crop.save(before_crop_path)
    after_crop.save(after_crop_path)

    region_crops.append({
        "region_id": region_id,
        "before": str(before_crop_path),
        "after": str(after_crop_path),
        "bbox": (left, top, right, bottom)
    })

print("========== REGION CROPS ==========")
print("Created:", len(region_crops), "paired crops")

for crop in region_crops:
    print(
        f"R{crop['region_id']}: "
        f"{crop['before']}  +  {crop['after']}"
    )

from IPython.display import display

for crop in region_crops:

    print(f"\n========== REGION R{crop['region_id']} ==========")

    print("BEFORE")
    display(Image.open(crop["before"]))

    print("AFTER")
    display(Image.open(crop["after"]))

from PIL import Image, ImageDraw
from pathlib import Path

comparison_dir = Path("/content/satquery_inputs/comparisons")
comparison_dir.mkdir(parents=True, exist_ok=True)

comparison_images = []

for crop in region_crops:

    region_id = crop["region_id"]

    before = Image.open(crop["before"]).convert("RGB")
    after = Image.open(crop["after"]).convert("RGB")

    # Make both images the same size
    width = max(before.width, after.width)
    height = max(before.height, after.height)

    before = before.resize((width, height))
    after = after.resize((width, height))

    # Side-by-side canvas
    comparison = Image.new(
        "RGB",
        (width * 2, height + 35),
        "white"
    )

    comparison.paste(before, (0, 35))
    comparison.paste(after, (width, 35))

    draw = ImageDraw.Draw(comparison)

    draw.text((10, 10), "BEFORE / T1", fill="black")
    draw.text((width + 10, 10), "AFTER / T2", fill="black")

    comparison_path = (
        comparison_dir / f"R{region_id}_comparison.png"
    )

    comparison.save(comparison_path)

    comparison_images.append({
        "region_id": region_id,
        "path": str(comparison_path)
    })

print("Created", len(comparison_images), "comparison images.")

for item in comparison_images:
    print(
        f"R{item['region_id']}: {item['path']}"
    )

from IPython.display import display

for item in comparison_images:

    print(f"\n========== REGION R{item['region_id']} ==========")

    display(
        Image.open(item["path"])
    )

!nvidia-smi

!uv venv --python 3.10 /content/vlm_env

!uv pip install \
    --python /content/vlm_env/bin/python \
    torch torchvision \
    --index-url https://download.pytorch.org/whl/cu124

!uv pip install \
    --python /content/vlm_env/bin/python \
    accelerate \
    qwen-vl-utils \
    regex \
    ftfy

!uv pip install \
    --python /content/vlm_env/bin/python \
    git+https://github.com/huggingface/transformers.git

!/content/vlm_env/bin/python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"

%%writefile /content/test_qwen.py

import torch
import transformers

print("PyTorch:", torch.__version__)
print("Transformers:", transformers.__version__)
print("CUDA:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

from transformers import (
    Qwen2_5_VLForConditionalGeneration,
    AutoProcessor
)

print("Qwen2.5-VL import: SUCCESS")

!/content/vlm_env/bin/python /content/test_qwen.py

%%writefile /content/run_vlm.py

import torch
from transformers import AutoProcessor, AutoModelForMultimodalLM

MODEL_NAME = "Qwen/Qwen2.5-VL-3B-Instruct"

print("Loading processor...")
processor = AutoProcessor.from_pretrained(MODEL_NAME)

print("Loading Qwen2.5-VL-3B...")
model = AutoModelForMultimodalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",
    dtype=torch.bfloat16
)

print("================================")
print("Qwen2.5-VL loaded successfully!")
print("================================")
print("Device:", model.device)

!/content/vlm_env/bin/python /content/run_vlm.py

%%writefile /content/test_region_vlm.py

import torch
from transformers import AutoProcessor, AutoModelForMultimodalLM

MODEL_NAME = "Qwen/Qwen2.5-VL-3B-Instruct"

BEFORE_IMAGE = "/content/satquery_inputs/regions/R3_before.png"
AFTER_IMAGE = "/content/satquery_inputs/regions/R3_after.png"

print("Loading processor...")
processor = AutoProcessor.from_pretrained(MODEL_NAME)

print("Loading model...")
model = AutoModelForMultimodalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",
    dtype=torch.float16
)

print("Model loaded.")
print("Analyzing region R3...")

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": BEFORE_IMAGE
            },
            {
                "type": "image",
                "image": AFTER_IMAGE
            },
            {
                "type": "text",
                "text": """
You are analyzing two satellite image crops of the same geographic location.

The first image is BEFORE (T1).
The second image is AFTER (T2).

Compare the two images carefully.

Identify:
1. What changed?
2. Where did the change occur?
3. What type of object or land feature appears to have changed?

Do not invent details that cannot be visually confirmed.
If uncertain, use words such as "appears to", "likely", or "possibly".

Give a concise answer in 2-4 sentences.
"""
            }
        ]
    }
]

inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt"
)

inputs = inputs.to(model.device)

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=150
    )

generated = outputs[0][inputs["input_ids"].shape[-1]:]

answer = processor.decode(
    generated,
    skip_special_tokens=True
)

print("\n==============================")
print("SATQUERY VLM RESULT")
print("==============================")
print(answer)

!/content/vlm_env/bin/python /content/test_region_vlm.py