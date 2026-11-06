"""
Loads the trained PyTorch model once and keeps it in memory.

PyTorch is imported inside the functions on purpose: if it is missing or the
weights file is not there yet, the website still starts and shows a clear
message instead of crashing.
"""
import logging
import threading
import time
from typing import Optional, Tuple

from app.config import settings

log = logging.getLogger("neuroscan.model")

RETRY_SECONDS = 10  # how often to retry loading if the first attempt failed


class ModelNotReadyError(RuntimeError):
    """Raised when a prediction is requested but the model cannot be used."""


_lock = threading.Lock()
_model = None
_device = None
_error: Optional[str] = "The model has not been loaded yet."
_last_attempt = 0.0


def _build_architecture(arch: str, num_classes: int):
    """Creates an empty network with a classification head sized for your classes.

    The weights are then loaded into it. If you trained with a custom head
    (extra layers, attention blocks, dropout) change the matching branch below
    so the layers have the same names and shapes as in your training code.
    """
    from torch import nn
    from torchvision import models

    if arch == "resnet50":
        net = models.resnet50(weights=None)
        net.fc = nn.Linear(net.fc.in_features, num_classes)
    elif arch == "vgg16":
        net = models.vgg16(weights=None)
        net.classifier[6] = nn.Linear(net.classifier[6].in_features, num_classes)
    elif arch == "densenet121":
        net = models.densenet121(weights=None)
        net.classifier = nn.Linear(net.classifier.in_features, num_classes)
    elif arch == "mobilenet_v2":
        net = models.mobilenet_v2(weights=None)
        net.classifier[1] = nn.Linear(net.classifier[1].in_features, num_classes)
    else:
        raise ValueError(
            f"MODEL_ARCH '{arch}' is not supported. Use resnet50, vgg16, densenet121 or mobilenet_v2."
        )
    return net


def _unwrap_state_dict(checkpoint):
    """Handles the common ways a checkpoint can be saved."""
    if isinstance(checkpoint, dict):
        for key in ("model_state_dict", "state_dict", "model"):
            if key in checkpoint and isinstance(checkpoint[key], dict):
                checkpoint = checkpoint[key]
                break
    # Weights saved from DataParallel have a "module." prefix on every key.
    return {
        (name[len("module."):] if name.startswith("module.") else name): tensor
        for name, tensor in checkpoint.items()
    }


def _load() -> None:
    """Tries to load the model. Never raises: it records what went wrong instead."""
    global _model, _device, _error, _last_attempt
    _last_attempt = time.time()

    path = settings.MODEL_PATH
    if not path.is_file():
        _error = (
            f"Model weights not found at '{path}'. Copy your trained .pth file there, "
            f"or point MODEL_PATH in .env to it."
        )
        log.warning(_error)
        return

    try:
        import torch
        from torch import nn
    except ImportError:
        _error = "PyTorch is not installed. Run: pip install torch torchvision"
        log.warning(_error)
        return

    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # weights_only=False is needed for checkpoints that hold more than plain
        # tensors (PyTorch 2.6 changed the default). Only load files you trained.
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)

        if isinstance(checkpoint, nn.Module):   # a whole saved model
            model = checkpoint
        else:                                   # a state_dict: rebuild the network, then load
            model = _build_architecture(settings.MODEL_ARCH, len(settings.CLASS_NAMES))
            model.load_state_dict(_unwrap_state_dict(checkpoint), strict=True)

        model.to(device).eval()
    except Exception as exc:  # noqa: BLE001 - we want to report any failure clearly
        _error = (
            f"Could not load '{path.name}' as a {settings.MODEL_ARCH} model with "
            f"{len(settings.CLASS_NAMES)} classes: {str(exc)[:400]}"
        )
        log.error(_error)
        return

    _model, _device, _error = model, device, None
    log.info("Model loaded: %s on %s", settings.MODEL_ARCH, device)


def ensure_loaded(min_interval: float = RETRY_SECONDS) -> bool:
    """Loads the model if it is not loaded yet (retrying at most every min_interval seconds)."""
    if _model is not None:
        return True
    with _lock:
        if _model is None and time.time() - _last_attempt >= min_interval:
            _load()
    return _model is not None


def get_model() -> Tuple[object, object]:
    """Returns (model, device) or raises ModelNotReadyError."""
    ensure_loaded(min_interval=2)
    if _model is None:
        raise ModelNotReadyError(_error or "The model is not loaded.")
    return _model, _device


def status() -> dict:
    """{'ready': bool, 'message': str or None} for the dashboards."""
    ready = ensure_loaded()
    return {"ready": ready, "message": None if ready else _error}
