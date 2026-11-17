"""
Checks the model inside the app, using your own images.

Run from the project folder, with (venv) active:

    python tools\\check_model.py "C:\\path\\to\\test_split"  "C:\\path\\to\\non_mri_images"

First argument : real MRI images. Either a flat folder, or a folder with one sub-folder
                 per class (glioma, meningioma, ...), which also gives you accuracy.
Second argument: optional folder of images that are NOT brain MRIs (photos, screenshots...).
Options        : --max 100   images used per folder / per class (default 100)

What it does
  1. Runs a few images through the app AND through a separate re-implementation of the
     notebook's predict_image (preprocessing, flip averaging, distance check) and compares them.
  2. Prints each image in the same format as the notebook's predict_image, so you can also
     compare by eye with the notebook run in Colab.
  3. Reports accuracy and how many real MRIs were rejected / flagged, and how many
     non-MRI images were rejected.
"""
import argparse
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from app.config import settings  # noqa: E402
from app.ml import model_loader  # noqa: E402
from app.ml.predict import run_prediction  # noqa: E402

EXTENSIONS = {".jpg", ".jpeg", ".png"}


def find_images(folder: Path):
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in EXTENSIONS)


def sample(items, limit):
    items = list(items)
    if len(items) <= limit:
        return items
    return random.Random(0).sample(items, limit)


def reference_prediction(loaded, ckpt, path):
    """The notebook's predict_image, written out again from the checkpoint's own numbers."""
    import torch
    import torch.nn.functional as F
    import torchvision.transforms as T
    import torchvision.transforms.functional as TF

    mean, std = ckpt["dataset_mean"], ckpt["dataset_std"]
    base = [T.Resize(256), T.CenterCrop(224)]
    tail = [T.Lambda(TF.autocontrast), T.ToTensor(), T.Normalize(mean, std)]
    tfm = T.Compose(base + tail)
    tfm_flip = T.Compose(base + [T.RandomHorizontalFlip(p=1.0)] + tail)

    img = Image.open(path).convert("RGB")
    x, xf = tfm(img).unsqueeze(0), tfm_flip(img).unsqueeze(0)
    with torch.no_grad():
        logits, pooled = loaded.model(x.to(loaded.device))
        logits_f, _ = loaded.model(xf.to(loaded.device))
    probs = 0.5 * (F.softmax(logits, 1) + F.softmax(logits_f, 1))[0].cpu()

    sigma_inv = torch.tensor(ckpt["sigma_inv"])
    pooled = pooled.cpu()
    dists = []
    for mu in ckpt["mu_c"].values():           # one distance per real class, like the notebook's scorer
        diff = pooled - torch.tensor(mu).unsqueeze(0)
        dists.append(torch.sqrt(torch.clamp(torch.einsum("bi,ij,bj->b", diff, sigma_inv, diff), min=0.0)))
    distance = float(torch.stack(dists).min())
    return probs.tolist(), distance


def show(path, result):
    c = result["checks"] or {}
    status = "REJECTED" if result["rejected"] else "accepted"
    line = f"  {path.name[:38]:38s} {result['predicted_class']:11s} {result['confidence'] * 100:6.2f}%  {status}"
    if c.get("distance") is not None:
        line += f"  distance={c['distance']:.3f} (limit {c['distance_limit']:.3f})"
    if c and not c["confidence_ok"]:
        line += "  [low confidence]"
    print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mri", help="folder of real MRI images")
    ap.add_argument("other", nargs="?", help="folder of non-MRI images")
    ap.add_argument("--max", type=int, default=100)
    args = ap.parse_args()

    state = model_loader.status()
    if not state["ready"]:
        print("MODEL NOT LOADED:", state["message"])
        sys.exit(1)
    loaded = model_loader.get_model()
    print(f"Model: {loaded.label} | classes: {', '.join(loaded.class_names)}")
    print(f"Distance limit: {loaded.ood.threshold:.3f}" if loaded.ood is not None else "No distance check in this checkpoint")
    print(f"Reject on distance: {settings.REJECT_ON_DISTANCE} | reject on confidence: {settings.REJECT_ON_CONFIDENCE}\n")

    # ---------- gather images ----------
    mri_root = Path(args.mri)
    if not mri_root.is_dir():
        sys.exit(f"Folder not found: {mri_root}")
    by_class = defaultdict(list)
    subdirs = [d for d in mri_root.iterdir() if d.is_dir() and d.name in loaded.class_names]
    if subdirs:
        for d in subdirs:
            by_class[d.name] = sample(find_images(d), args.max)
    else:
        by_class["(unlabelled)"] = sample(find_images(mri_root), args.max)
    total = sum(len(v) for v in by_class.values())
    if total == 0:
        sys.exit("No .jpg / .jpeg / .png images found.")

    # ---------- 1. app vs reference ----------
    if loaded.kind == "mscbam" and loaded.ood is not None:
        import torch
        print("1) App versus an independent re-implementation of the notebook's predict_image")
        ckpt = torch.load(settings.MODEL_PATH, map_location="cpu", weights_only=False)
        picks = sample([p for v in by_class.values() for p in v], 8)
        worst_p = worst_d = 0.0
        same = True
        for path in picks:
            mine = run_prediction(Image.open(path))
            ref_probs, ref_dist = reference_prediction(loaded, ckpt, path)
            my_probs = [mine["probabilities"][n] for n in loaded.class_names]
            worst_p = max(worst_p, max(abs(a - b) for a, b in zip(ref_probs, my_probs)))
            worst_d = max(worst_d, abs(ref_dist - mine["checks"]["distance"]))
            ref_cls = loaded.class_names[max(range(len(ref_probs)), key=ref_probs.__getitem__)]
            same &= ref_cls == mine["predicted_class"]
            same &= (ref_dist > loaded.ood.threshold) == (not mine["checks"]["distance_ok"])
        verdict = same and worst_p < 1e-4 and worst_d < 0.05
        print(f"   images compared: {len(picks)} | largest probability difference: {worst_p:.2e} | "
              f"largest distance difference: {worst_d:.4f}")
        print("   RESULT:", "PASS" if verdict else "FAIL: the app and the reference disagree", "\n")
    else:
        print("1) Skipped: the app-versus-reference comparison is only for MS-CBAM-Net checkpoints.\n")

    # ---------- 2 and 3. real MRIs ----------
    print(f"2) Real MRI images ({total} used)")
    stats = defaultdict(Counter)
    shown = 0
    for label, paths in by_class.items():
        for path in paths:
            try:
                r = run_prediction(Image.open(path))
            except Exception as exc:  # noqa: BLE001
                print(f"  could not read {path.name}: {exc}")
                stats[label]["error"] += 1
                continue
            s = stats[label]
            s["n"] += 1
            if r["rejected"]:
                s["rejected"] += 1
            else:
                s["accepted"] += 1
                if label != "(unlabelled)" and r["predicted_class"] == label:
                    s["correct"] += 1
            if r["checks"] and not r["checks"]["confidence_ok"]:
                s["flagged"] += 1
            s["pred_" + r["predicted_class"]] += 1
            if shown < 12:
                show(path, r)
                shown += 1
    if total > 12:
        print(f"  ... ({total - 12} more not shown)")

    print("\n   Class         images  accepted  rejected  flagged  accuracy (of accepted)")
    for label, s in stats.items():
        acc = f"{s['correct'] / s['accepted'] * 100:6.2f}%" if s["accepted"] and label != "(unlabelled)" else "     -"
        print(f"   {label:12s}  {s['n']:6d}  {s['accepted']:8d}  {s['rejected']:8d}  {s['flagged']:7d}  {acc}")
    n_all = sum(s["n"] for s in stats.values())
    rej_all = sum(s["rejected"] for s in stats.values())
    print(f"\n   Rejected overall: {rej_all}/{n_all} = {rej_all / max(n_all, 1) * 100:.1f}%"
          "   (the notebook measured 5.5% on real MRIs; 'other' images should be rejected, ~100%)")
    real = [s for k, s in stats.items() if k != "other"]
    if real and subdirs:
        r_n = sum(s["n"] for s in real)
        r_rej = sum(s["rejected"] for s in real)
        r_cor = sum(s["correct"] for s in real)
        print(f"   Tumor / no-tumor classes only: {r_rej}/{r_n} rejected = {r_rej / max(r_n, 1) * 100:.1f}%; "
              f"{r_cor}/{r_n - r_rej} correct among the accepted = {r_cor / max(r_n - r_rej, 1) * 100:.2f}%")

    # ---------- 4. non-MRI images ----------
    if args.other:
        other_root = Path(args.other)
        if not other_root.is_dir():
            sys.exit(f"Folder not found: {other_root}")
        paths = sample(find_images(other_root), args.max)
        print(f"\n3) Images that are NOT brain MRIs ({len(paths)} used). They should be rejected.")
        missed = []
        rejected = 0
        for path in paths:
            try:
                r = run_prediction(Image.open(path))
            except Exception as exc:  # noqa: BLE001
                print(f"  could not read {path.name}: {exc}")
                continue
            rejected += int(r["rejected"])
            if not r["rejected"]:
                missed.append((path, r))
        print(f"   Rejected: {rejected}/{len(paths)} = {rejected / max(len(paths), 1) * 100:.1f}%")
        for path, r in missed[:10]:
            print("   NOT rejected:")
            show(path, r)
    else:
        print("\n3) No non-MRI folder given, so rejection of other images was not tested.")
        print("   Add a folder of photos or screenshots as the second argument.")


if __name__ == "__main__":
    main()
