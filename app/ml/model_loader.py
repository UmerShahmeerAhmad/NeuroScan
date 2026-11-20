"""
Loads the trained PyTorch model once and keeps it in memory.

Two kinds of files are understood:
  1. The MS-CBAM-Net checkpoint saved by the training notebook. It carries its own
     class names, normalisation numbers and out-of-distribution (OOD) data, so
     nothing else needs configuring.
  2. A plain state_dict or a whole saved model of a standard network
     (resnet50, vgg16, densenet121, mobilenet_v2), configured through .env.

PyTorch is imported inside the functions on purpose: if it is missing or the
weights file is not there yet, the website still starts and shows a clear
message instead of crashing.
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.config import settings

log = logging.getLogger("neuroscan.model")

RETRY_SECONDS = 10  # how often to retry loading if the first attempt failed

KIND_MSCBAM = "mscbam"
KIND_STANDARD = "standard"


class ModelNotReadyError(RuntimeError):
    """Raised when a prediction is requested but the model cannot be used."""


@dataclass
class LoadedModel:
    kind: str                      # KIND_MSCBAM or KIND_STANDARD
    model: object
    device: object
    label: str                     # shown to people, e.g. "MS-CBAM-Net"
    class_names: List[str]
    mean: List[float]
    std: List[float]
    conf_thresh: Optional[float] = None
    entropy_thresh: Optional[float] = None
    ood: Optional[object] = None   # MahalanobisOOD, when the checkpoint has one
    notes: List[str] = field(default_factory=list)


_lock = threading.Lock()
_loaded: Optional[LoadedModel] = None
_error: Optional[str] = "The model has not been loaded yet."
_last_attempt = 0.0


def _build_standard(arch: str, num_classes: int):
    """Creates an empty standard network with a classification head sized for your classes."""
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
    elif arch == "auto":
        raise ValueError(
            "This file holds plain weights and does not say which network they belong to. "
            "Set MODEL_ARCH in .env to resnet50, vgg16, densenet121 or mobilenet_v2."
        )
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


def _is_mscbam(checkpoint) -> bool:
    if settings.MODEL_ARCH.replace("-", "").replace("_", "") in ("mscbam", "mscbamnet", "mscbamnetsgm"):
        return True
    if isinstance(checkpoint, dict):
        tag = str(checkpoint.get("architecture", "")).lower().replace("-", "").replace("_", "")
        return "mscbam" in tag
    return False


def _load_mscbam(checkpoint, device) -> LoadedModel:
    from app.ml.mscbam_net import MahalanobisOOD, MSCBAMNetSGM

    notes: List[str] = []

    class_names = [str(name) for name in (checkpoint.get("class_names") or settings.CLASS_NAMES)]
    if checkpoint.get("class_names") and list(checkpoint["class_names"]) != list(settings.CLASS_NAMES):
        notes.append("Class names come from the checkpoint, not from CLASS_NAMES in .env.")

    model = MSCBAMNetSGM(num_classes=len(class_names))
    # strict=True: any missing or extra layer stops the load with a clear message.
    model.load_state_dict(_unwrap_state_dict(checkpoint), strict=True)
    model.to(device).eval()

    mean = [float(v) for v in (checkpoint.get("dataset_mean") or settings.NORM_MEAN)]
    std = [float(v) for v in (checkpoint.get("dataset_std") or settings.NORM_STD)]

    ood = None
    if checkpoint.get("mu_c") and checkpoint.get("sigma_inv") is not None \
            and checkpoint.get("mahalanobis_thresh") is not None:
        ood = MahalanobisOOD(checkpoint["mu_c"], checkpoint["sigma_inv"], checkpoint["mahalanobis_thresh"])
    else:
        notes.append("The checkpoint has no distance-check data, so only the confidence check is used.")

    conf = checkpoint.get("conf_thresh")
    entropy = checkpoint.get("entropy_thresh")
    return LoadedModel(
        kind=KIND_MSCBAM,
        model=model,
        device=device,
        label="MS-CBAM-Net",
        class_names=class_names,
        mean=mean,
        std=std,
        conf_thresh=float(conf) if conf is not None else None,
        entropy_thresh=float(entropy) if entropy is not None else None,
        ood=ood,
        notes=notes,
    )


def _load_standard(checkpoint, device) -> LoadedModel:
    from torch import nn

    if isinstance(checkpoint, nn.Module):   # a whole saved model
        model = checkpoint
    else:                                   # a state_dict: rebuild the network, then load
        model = _build_standard(settings.MODEL_ARCH, len(settings.CLASS_NAMES))
        model.load_state_dict(_unwrap_state_dict(checkpoint), strict=True)
    model.to(device).eval()

    return LoadedModel(
        kind=KIND_STANDARD,
        model=model,
        device=device,
        label=settings.MODEL_ARCH,
        class_names=list(settings.CLASS_NAMES),
        mean=list(settings.NORM_MEAN),
        std=list(settings.NORM_STD),
    )


def _load() -> None:
    """Tries to load the model. Never raises: it records what went wrong instead."""
    global _loaded, _error, _last_attempt
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
    except ImportError:
        _error = "PyTorch is not installed. Run: python -m pip install torch torchvision"
        log.warning(_error)
        return

    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # weights_only=False is needed for checkpoints that hold more than plain
        # tensors (PyTorch 2.6 changed the default). Only load files you trained.
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)

        if isinstance(checkpoint, dict) and _is_mscbam(checkpoint):
            loaded = _load_mscbam(checkpoint, device)
        else:
            loaded = _load_standard(checkpoint, device)
    except Exception as exc:  # noqa: BLE001 - we want to report any failure clearly
        _error = f"Could not load '{path.name}': {str(exc)[:500]}"
        log.error(_error)
        return

    _loaded, _error = loaded, None
    log.info(
        "Model loaded: %s on %s (%d classes: %s)%s",
        loaded.label, device, len(loaded.class_names), ", ".join(loaded.class_names),
        " with distance check" if loaded.ood is not None else "",
    )
    for note in loaded.notes:
        log.info("Model note: %s", note)


def ensure_loaded(min_interval: float = RETRY_SECONDS) -> bool:
    """Loads the model if it is not loaded yet (retrying at most every min_interval seconds)."""
    if _loaded is not None:
        return True
    with _lock:
        if _loaded is None and time.time() - _last_attempt >= min_interval:
            _load()
    return _loaded is not None


def get_model() -> LoadedModel:
    """Returns the loaded model or raises ModelNotReadyError."""
    ensure_loaded(min_interval=2)
    if _loaded is None:
        raise ModelNotReadyError(_error or "The model is not loaded.")
    return _loaded


def class_names() -> List[str]:
    """The classes of the loaded model, or the ones from .env while it is not loaded."""
    return list(_loaded.class_names) if _loaded is not None else list(settings.CLASS_NAMES)


def review_threshold() -> float:
    """Results with a confidence below this are flagged for manual review."""
    if _loaded is not None and _loaded.conf_thresh is not None:
        return _loaded.conf_thresh
    return settings.CONFIDENCE_THRESHOLD


def status() -> dict:
    """{'ready', 'message', 'label'} for the dashboards."""
    ready = ensure_loaded()
    label = _loaded.label if _loaded is not None else settings.MODEL_ARCH
    return {"ready": ready, "message": None if ready else _error, "label": label}
