import os
import sys
import torch

# Add BIT_CD to path
sys.path.insert(0, os.path.abspath('BIT_CD'))

class Args:
    pass

args = Args()
args.n_class = 2
args.project_name = "BIT_LEVIR"
args.checkpoint_dir = os.path.abspath('BIT_CD/checkpoints/BIT_LEVIR')
args.batch_size = 1
args.img_size = 256
args.net_G = "base_transformer_pos_s4_dd8_dedim8"
args.gpu_ids = []  # Use CPU for export
args.output_folder = "output"

# We must mock 'CDEvaluator' import
from models.basic_model import CDEvaluator

print("Initializing CDEvaluator...")
evaluator = CDEvaluator(args)

print("Loading checkpoint...")
evaluator.load_checkpoint('best_ckpt.pt')

model = evaluator.net_G
model.eval()

# Dummy inputs (batch_size, channels, height, width)
print("Creating dummy inputs...")
dummy_img1 = torch.randn(1, 3, 256, 256)
dummy_img2 = torch.randn(1, 3, 256, 256)

output_onnx_path = 'BIT_LEVIR_model.onnx'

print(f"Exporting model to {output_onnx_path} ...")
torch.onnx.export(
    model, 
    (dummy_img1, dummy_img2), 
    output_onnx_path,
    export_params=True,
    opset_version=12,
    do_constant_folding=True,
    input_names=['img1', 'img2'],
    output_names=['pred'],
    dynamic_axes={
        'img1': {0: 'batch_size', 2: 'height', 3: 'width'},
        'img2': {0: 'batch_size', 2: 'height', 3: 'width'},
        'pred': {0: 'batch_size', 2: 'height', 3: 'width'}
    }
)
print("Export completed successfully!")
