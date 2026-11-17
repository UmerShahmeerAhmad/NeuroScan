import sys
from collections import Counter

import torch

ckpt = torch.load(sys.argv[1], map_location="cpu", weights_only=False)

for key in ("class_names", "architecture", "weight_source", "dataset_mean",
            "dataset_std", "conf_thresh", "entropy_thresh", "mahalanobis_thresh"):
    print(f"{key}: {ckpt.get(key)}")

for key in ("mu_c", "sigma_inv"):
    value = ckpt.get(key)
    print(f"{key}: type={type(value).__name__} shape={getattr(value, 'shape', None)}")

state = ckpt["model_state_dict"]
groups = Counter(name.split(".")[0] for name in state)
print("Module groups (name: number of tensors):")
for name, count in groups.items():
    print(f"  {name}: {count}")