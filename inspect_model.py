import sys
import torch

path = sys.argv[1]
ckpt = torch.load(path, map_location="cpu", weights_only=False)
print("Type:", type(ckpt).__name__)

if isinstance(ckpt, dict):
    print("Top-level keys:", list(ckpt.keys())[:15])
    for key in ("model_state_dict", "state_dict", "model"):
        if key in ckpt and isinstance(ckpt[key], dict):
            ckpt = ckpt[key]
            print("Using inner dict:", key)
            break

if isinstance(ckpt, dict):
    tensors = [(k, tuple(v.shape)) for k, v in ckpt.items() if hasattr(v, "shape")]
    print("Tensors:", len(tensors))
    print("First 5:", tensors[:5])
    print("Last 5:", tensors[-5:])
    last = [t for t in tensors if len(t[1]) == 2]
    if last:
        print("Probable number of classes:", last[-1][1][0])