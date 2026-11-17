"""Turns an uploaded image into a prediction."""
from typing import Dict, List

from PIL import Image, ImageOps

from app.config import settings
from app.ml.model_loader import KIND_MSCBAM, LoadedModel, ModelNotReadyError, get_model

# MS-CBAM-Net preprocessing, as in the training notebook's eval_transform:
# Resize(256) -> CenterCrop(224) -> AutoContrast -> ToTensor -> Normalize(dataset mean/std)
_RESIZE = 256
_CROP = 224
_EPS = 1e-8

_transforms_cache: Dict[tuple, object] = {}


def _mscbam_transforms(loaded: LoadedModel):
    """(plain, flipped) transforms. Built once per model."""
    key = (tuple(loaded.mean), tuple(loaded.std))
    if key not in _transforms_cache:
        import torchvision.transforms as T
        import torchvision.transforms.functional as TF

        def autocontrast(img):
            return TF.autocontrast(img)

        plain = T.Compose([
            T.Resize(_RESIZE), T.CenterCrop(_CROP), T.Lambda(autocontrast),
            T.ToTensor(), T.Normalize(loaded.mean, loaded.std),
        ])
        flipped = T.Compose([
            T.Resize(_RESIZE), T.CenterCrop(_CROP), T.RandomHorizontalFlip(p=1.0), T.Lambda(autocontrast),
            T.ToTensor(), T.Normalize(loaded.mean, loaded.std),
        ])
        _transforms_cache[key] = (plain, flipped)
    return _transforms_cache[key]


def _standard_transform(loaded: LoadedModel):
    key = ("standard", tuple(loaded.mean), tuple(loaded.std), settings.IMAGE_SIZE)
    if key not in _transforms_cache:
        from torchvision import transforms

        _transforms_cache[key] = transforms.Compose([
            transforms.Resize((settings.IMAGE_SIZE, settings.IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(loaded.mean, loaded.std),
        ])
    return _transforms_cache[key]


def _top(probabilities: List[float], names: List[str]) -> int:
    return max(range(len(probabilities)), key=lambda index: probabilities[index])


def _check_class_count(probabilities: List[float], names: List[str]) -> None:
    if len(probabilities) != len(names):
        raise ModelNotReadyError(
            f"The model outputs {len(probabilities)} classes but CLASS_NAMES in .env lists "
            f"{len(names)}. Fix CLASS_NAMES so it matches the order used in training."
        )


def _predict_standard(loaded: LoadedModel, image: Image.Image) -> dict:
    import torch

    image = image.convert("RGB")
    if settings.USE_AUTOCONTRAST:
        image = ImageOps.autocontrast(image)

    batch = _standard_transform(loaded)(image).unsqueeze(0).to(loaded.device)
    with torch.no_grad():
        output = loaded.model(batch)
        if isinstance(output, (tuple, list)):
            output = output[0]
        probabilities = torch.softmax(output, dim=1)[0].cpu().tolist()

    _check_class_count(probabilities, loaded.class_names)
    best = _top(probabilities, loaded.class_names)
    return {
        "predicted_class": loaded.class_names[best],
        "confidence": float(probabilities[best]),
        "probabilities": {n: round(float(p), 6) for n, p in zip(loaded.class_names, probabilities)},
        "model_name": loaded.label,
        "rejected": False,
        "reject_reasons": [],
        "checks": None,
    }


def _predict_mscbam(loaded: LoadedModel, image: Image.Image) -> dict:
    import torch
    import torch.nn.functional as F

    plain, flipped = _mscbam_transforms(loaded)
    image = image.convert("RGB")
    x = plain(image).unsqueeze(0).to(loaded.device)
    x_flip = flipped(image).unsqueeze(0).to(loaded.device)

    with torch.no_grad():
        logits, pooled = loaded.model(x)
        logits_flip, _ = loaded.model(x_flip)

        probs_plain = F.softmax(logits, dim=1)
        # Test-time augmentation: average the original and mirrored views.
        probs_tta = 0.5 * (probs_plain + F.softmax(logits_flip, dim=1))

        # The rejection checks use the original (not mirrored) view, as in the notebook.
        max_prob = float(probs_plain.max(dim=1).values.item())
        entropy = float((-(probs_plain * torch.log(probs_plain + _EPS)).sum(dim=1)).item())
        distance = float(loaded.ood.distance(pooled.cpu()).item()) if loaded.ood is not None else None

    probabilities = probs_tta[0].cpu().tolist()
    _check_class_count(probabilities, loaded.class_names)
    best = _top(probabilities, loaded.class_names)

    # --- check A: confidence and entropy ---
    low_conf = False
    if loaded.conf_thresh is not None and max_prob < loaded.conf_thresh:
        low_conf = True
    if loaded.entropy_thresh is not None and entropy > loaded.entropy_thresh:
        low_conf = True

    # --- check B: distance in feature space ---
    far = distance is not None and distance > loaded.ood.threshold

    reasons: List[str] = []
    if far and settings.REJECT_ON_DISTANCE:
        reasons.append(
            "This image does not look like the brain MRI slices the model was trained on."
        )
    if low_conf and settings.REJECT_ON_CONFIDENCE:
        reasons.append("The model is not confident enough about this image to classify it.")

    return {
        "predicted_class": loaded.class_names[best],
        "confidence": float(probabilities[best]),
        "probabilities": {n: round(float(p), 6) for n, p in zip(loaded.class_names, probabilities)},
        "model_name": loaded.label,
        "rejected": bool(reasons),
        "reject_reasons": reasons,
        "checks": {
            "max_prob": round(max_prob, 4),
            "entropy": round(entropy, 4),
            "distance": round(distance, 3) if distance is not None else None,
            "distance_limit": round(loaded.ood.threshold, 3) if loaded.ood is not None else None,
            "confidence_limit": round(loaded.conf_thresh, 4) if loaded.conf_thresh is not None else None,
            "entropy_limit": round(loaded.entropy_thresh, 4) if loaded.entropy_thresh is not None else None,
            "distance_ok": (not far) if distance is not None else None,
            "confidence_ok": not low_conf,
        },
    }


def run_prediction(image: Image.Image) -> dict:
    """Returns the prediction, the probability of every class, and the reliability checks."""
    loaded = get_model()  # raises ModelNotReadyError with a clear reason if not ready
    if loaded.kind == KIND_MSCBAM:
        return _predict_mscbam(loaded, image)
    return _predict_standard(loaded, image)
