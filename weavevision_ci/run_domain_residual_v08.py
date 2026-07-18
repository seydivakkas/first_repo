from __future__ import annotations

from pathlib import Path

import numpy as np
from huggingface_hub import snapshot_download
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "weavevision_ci" / "work_v12"
D = W / "datasets"
DL = W / "downloads"
EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def log(message):
    print(message, flush=True)


def imgs(path):
    return sorted(p for p in Path(path).rglob("*") if p.is_file() and p.suffix.lower() in EXT)


def rgb_image(path):
    with Image.open(path) as image:
        return image.convert("RGB").copy()


def rgb_array(image, size=128):
    return np.asarray(image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR), np.float32) / 255.0


def gray(array):
    return 0.299 * array[..., 0] + 0.587 * array[..., 1] + 0.114 * array[..., 2]


def blur(array, radius):
    if radius <= 0:
        return array.astype(np.float32, copy=True)
    kernel = 2 * radius + 1
    padded = np.pad(array.astype(np.float32), ((radius, radius), (radius, radius)), mode="edge")
    integral = np.pad(padded, ((1, 0), (1, 0)), mode="constant").cumsum(0).cumsum(1)
    return (
        integral[kernel:, kernel:]
        - integral[:-kernel, kernel:]
        - integral[kernel:, :-kernel]
        + integral[:-kernel, :-kernel]
    ) / float(kernel * kernel)


def hist(values, bins, lo, hi, weights=None):
    result = np.histogram(values, bins=bins, range=(lo, hi), weights=weights)[0].astype(np.float32)
    return result / max(float(result.sum()), 1e-6)


def image_desc(image, size=96):
    array = rgb_array(image, size)
    g = gray(array)
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, 1:-1] = 0.5 * (g[:, 2:] - g[:, :-2])
    gy[1:-1, :] = 0.5 * (g[2:, :] - g[:-2, :])
    magnitude = np.sqrt(gx * gx + gy * gy)
    orientation = (np.arctan2(gy, gx) + np.pi) / (2.0 * np.pi)
    parts = [hist(array[..., channel], 8, 0.0, 1.0) for channel in range(3)]
    parts += [hist(g, 12, 0.0, 1.0), hist(magnitude, 10, 0.0, 0.5), hist(orientation, 12, 0.0, 1.0, magnitude + 1e-5)]
    centered = g - float(g.mean())
    spectrum = np.abs(np.fft.rfft2(centered)) ** 2
    yy = np.fft.fftfreq(size)[:, None]
    xx = np.fft.rfftfreq(size)[None, :]
    radius = np.sqrt(xx * xx + yy * yy)
    total = max(float(spectrum.sum()), 1e-6)
    edges = np.linspace(0.0, 0.72, 9)
    parts.append(np.asarray([spectrum[(radius >= lo) & (radius < hi)].sum() / total for lo, hi in zip(edges[:-1], edges[1:])], np.float32))
    low = np.asarray(Image.fromarray(np.uint8(np.clip(g * 255.0, 0, 255))).resize((8, 8), Image.Resampling.BILINEAR), np.float32)
    low = (low - low.mean()) / max(float(low.std()), 1.0)
    parts.append(low.ravel())
    return np.concatenate(parts).astype(np.float32)


def nearest(query, memory):
    squared = np.maximum(np.sum(query * query) + np.sum(memory * memory, axis=1) - 2.0 * memory @ query, 0.0)
    return np.sqrt(squared).astype(np.float32)


def phase(reference_gray, query_gray, max_shift=10):
    reference = reference_gray - float(reference_gray.mean())
    query = query_gray - float(query_gray.mean())
    cross = np.fft.fft2(query) * np.conj(np.fft.fft2(reference))
    cross /= np.maximum(np.abs(cross), 1e-7)
    y, x = np.unravel_index(int(np.argmax(np.fft.ifft2(cross).real)), reference.shape)
    y = y - reference.shape[0] if y > reference.shape[0] // 2 else y
    x = x - reference.shape[1] if x > reference.shape[1] // 2 else x
    return int(np.clip(y, -max_shift, max_shift)), int(np.clip(x, -max_shift, max_shift))


def conformal(scores, alpha=0.10):
    values = np.sort(np.asarray(scores, np.float32))
    rank = int(np.ceil((len(values) + 1) * (1.0 - alpha)))
    return float(values[min(max(rank - 1, 0), len(values) - 1)])


def acquire_itd():
    return None, {"dataset": "not_used_by_metal_observability_audit"}


def acquire_mvtec():
    snapshot = Path(snapshot_download(
        repo_id="jiang-cc/MMAD",
        repo_type="dataset",
        revision="74db7cacf256eb62b5ce87094f83e9201fb7ac0a",
        allow_patterns=["MVTec-AD/carpet/**"],
        local_dir=DL / "mvtec",
    ))
    root = snapshot / "MVTec-AD" / "carpet"
    return root, {
        "dataset": "MVTec-AD carpet",
        "license_policy": "RESEARCH_ONLY_CC_BY_NC_SA_4_0",
        "revision": "74db7cacf256eb62b5ce87094f83e9201fb7ac0a",
    }
