"""Turns an uploaded image into a prediction."""
from PIL import Image, ImageOps

from app.config import settings
from app.ml.model_loader import ModelNotReadyError, get_model

_transform = None


def _get_transform():
    """Builds the preprocessing pipeline once. It must match your training pipeline."""
    global _transform
    if _transform is None:
        from torchvision import transforms

        _transform = transforms.Compose(
            [
                transforms.Resize((settings.IMAGE_SIZE, settings.IMAGE_SIZE)),
                transforms.ToTensor(),
                transforms.Normalize(settings.NORM_MEAN, settings.NORM_STD),
            ]
        )
    return _transform


def run_prediction(image: Image.Image) -> dict:
    """Returns the predicted class, its confidence and the full probability list."""
    model, device = get_model()  # raises ModelNotReadyError with a clear reason if not ready
    import torch

    image = image.convert("RGB")
    if settings.USE_AUTOCONTRAST:
        image = ImageOps.autocontrast(image)

    batch = _get_transform()(image).unsqueeze(0).to(device)
    with torch.no_grad():
        probabilities = torch.softmax(model(batch), dim=1)[0].cpu().tolist()

    names = settings.CLASS_NAMES
    if len(probabilities) != len(names):
        raise ModelNotReadyError(
            f"The model outputs {len(probabilities)} classes but CLASS_NAMES in .env lists "
            f"{len(names)}. Fix CLASS_NAMES so it matches the order used in training."
        )

    best = max(range(len(probabilities)), key=lambda index: probabilities[index])
    return {
        "predicted_class": names[best],
        "confidence": float(probabilities[best]),
        "probabilities": {name: round(float(p), 6) for name, p in zip(names, probabilities)},
        "model_name": settings.MODEL_ARCH,
    }
