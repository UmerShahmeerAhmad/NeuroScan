"""Grad-CAM: shows which parts of the MRI pushed the model towards its answer.

The heatmap is a visual aid only. It is computed on request, so nothing extra is stored.
"""
import io
from typing import Optional, Tuple

import numpy as np
from PIL import Image

from app.ml.model_loader import KIND_MSCBAM, LoadedModel, get_model


def _target_layer(loaded: LoadedModel):
    """The last convolutional feature map of the network."""
    model = loaded.model
    if loaded.kind == KIND_MSCBAM:
        return model.stage4
    for name in ("layer4", "features"):            # resnet50, densenet121 / vgg16 / mobilenet_v2
        if hasattr(model, name):
            return getattr(model, name)
    raise RuntimeError("Heatmaps are not available for this network.")


def _colormap(values: np.ndarray) -> np.ndarray:
    """0..1 -> RGB (blue, cyan, green, yellow, red). Small replacement for matplotlib's 'jet'."""
    v = np.clip(values, 0.0, 1.0)
    r = np.clip(1.5 - np.abs(4.0 * v - 3.0), 0, 1)
    g = np.clip(1.5 - np.abs(4.0 * v - 2.0), 0, 1)
    b = np.clip(1.5 - np.abs(4.0 * v - 1.0), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def _input_and_view(loaded: LoadedModel, image: Image.Image):
    """Model input tensor, plus the 224-pixel picture the model actually looked at."""
    from app.ml import predict as p

    image = image.convert("RGB")
    if loaded.kind == KIND_MSCBAM:
        plain, _ = p._mscbam_transforms(loaded)
        import torchvision.transforms as T
        import torchvision.transforms.functional as TF

        view = T.Compose([T.Resize(p._RESIZE), T.CenterCrop(p._CROP)])(image)
        tensor = plain(image).unsqueeze(0)
        return tensor, TF.autocontrast(view)
    from PIL import ImageOps
    from app.config import settings

    if settings.USE_AUTOCONTRAST:
        image = ImageOps.autocontrast(image)
    view = image.resize((settings.IMAGE_SIZE, settings.IMAGE_SIZE))
    return p._standard_transform(loaded)(image).unsqueeze(0), view


def make_heatmap(image: Image.Image, class_index: Optional[int] = None) -> Tuple[bytes, str]:
    """Returns (PNG bytes of the overlay, name of the class the map explains).

    class_index None explains the model's own top choice."""
    import torch
    import torch.nn.functional as F

    loaded = get_model()
    tensor, view = _input_and_view(loaded, image)
    tensor = tensor.to(loaded.device)
    layer = _target_layer(loaded)

    store = {}

    def on_forward(_module, _inputs, output):
        store["act"] = output
        output.register_hook(lambda grad: store.__setitem__("grad", grad))

    handle = layer.register_forward_hook(on_forward)
    try:
        loaded.model.eval()
        with torch.enable_grad():
            tensor.requires_grad_(True)
            out = loaded.model(tensor)
            logits = out[0] if isinstance(out, (tuple, list)) else out
            idx = int(logits.argmax(dim=1).item()) if class_index is None else class_index
            loaded.model.zero_grad(set_to_none=True)
            logits[0, idx].backward()
    finally:
        handle.remove()

    act, grad = store["act"].detach(), store["grad"].detach()
    weights = grad.mean(dim=(2, 3), keepdim=True)
    cam = F.relu((weights * act).sum(dim=1, keepdim=True))
    cam = F.interpolate(cam, size=(view.height, view.width), mode="bilinear", align_corners=False)[0, 0]
    cam = cam.cpu().numpy()
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

    base = np.asarray(view.convert("RGB"), dtype=np.float32)
    heat = _colormap(cam).astype(np.float32)
    alpha = (0.15 + 0.55 * cam)[..., None]              # strong areas show more colour
    blended = (base * (1 - alpha) + heat * alpha).astype(np.uint8)

    buffer = io.BytesIO()
    Image.fromarray(blended).save(buffer, format="PNG")
    return buffer.getvalue(), loaded.class_names[idx]
