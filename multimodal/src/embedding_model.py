"""Pinned pretrained shared image/text encoder. Inference only."""
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


def normalize_vectors(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or not np.isfinite(vectors).all():
        raise ValueError("Embeddings must be a finite two-dimensional matrix")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms <= 1e-12):
        raise ValueError("Zero vector cannot represent cosine similarity")
    return np.ascontiguousarray(vectors / norms)


class MultimodalEncoder(ABC):
    model_name: str
    embedding_dimension: int

    @abstractmethod
    def encode_text(self, texts):
        """Return a normalized float32 matrix in input order."""

    @abstractmethod
    def encode_images(self, paths):
        """Return a normalized float32 matrix in input order."""

    def encode_image(self, path):
        return self.encode_images([path])[0]


class SiglipEncoder(MultimodalEncoder):
    def __init__(self, config):
        import torch
        import transformers
        from transformers import AutoModel, AutoProcessor

        self.torch = torch
        self.model_name = config["model_name"]
        self.batch_size = int(config["batch_size"])
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.text_template = config["text_template"]
        self.max_text_length = config["max_text_length"]
        device = config["device"]
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        torch.manual_seed(2027)
        torch.set_num_threads(1)
        if device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.benchmark = False
        self.processor = AutoProcessor.from_pretrained(self.model_name, revision=config["revision"], use_fast=False, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(self.model_name, revision=config["revision"], trust_remote_code=False).to(device).eval()
        self.model.requires_grad_(False)
        self.embedding_dimension = self.model.config.vision_config.hidden_size
        self.metadata = {
            "model_name": self.model_name,
            "model_revision": getattr(self.model.config, "_commit_hash", None) or config["revision"],
            "embedding_dimension": self.embedding_dimension,
            "torch_version": torch.__version__, "transformers_version": transformers.__version__,
            "device": device, "dtype": "float32", "normalization": "L2",
            "batch_size": self.batch_size,
            "preprocessing": {"image_processor": self.processor.image_processor.to_dict(),
                              "exif_transpose": True, "color_mode": "RGB",
                              "text_template": self.text_template,
                              "lowercase": True, "padding": "max_length",
                              "max_length": self.max_text_length, "truncation": True},
            "training": "none; pretrained weights are frozen",
        }

    def _encode(self, values, modality):
        from PIL import Image, ImageOps

        batches = []
        for start in range(0, len(values), self.batch_size):
            batch = values[start:start + self.batch_size]
            if modality == "text":
                inputs = self.processor(text=[self.text_template.format(text=text).lower() for text in batch],
                                        padding="max_length", max_length=self.max_text_length,
                                        truncation=True, return_tensors="pt")
            else:
                images = []
                for path in batch:
                    with Image.open(Path(path)) as original:
                        images.append(ImageOps.exif_transpose(original).convert("RGB"))
                try:
                    inputs = self.processor(images=images, return_tensors="pt")
                finally:
                    for image in images:
                        image.close()
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with self.torch.inference_mode():
                features = self.model.get_text_features(**inputs) if modality == "text" else self.model.get_image_features(**inputs)
            # Transfer synchronizes MPS/CUDA before downstream timing completes.
            batches.append(normalize_vectors(features.float().cpu().numpy()))
        return np.concatenate(batches) if batches else np.empty((0, self.embedding_dimension), dtype=np.float32)

    def encode_text(self, texts):
        return self._encode(texts, "text")

    def encode_images(self, paths):
        return self._encode(paths, "image")
