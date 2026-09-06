"""Isolate PyTorch's OpenMP runtime from native FAISS (not a distributed service)."""
import atexit
import base64
import json
import subprocess
import sys

import numpy as np

from .config import ROOT
from .embedding_model import MultimodalEncoder, SiglipEncoder


class EncoderWorker(MultimodalEncoder):
    """One local process, one loaded model, synchronous requests over private pipes."""
    def __init__(self, config):
        self.process = subprocess.Popen([sys.executable, "-m", "multimodal.src.encoder_worker"],
            cwd=ROOT.parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        atexit.register(self.close)
        response = self._request({"config": config})
        self.metadata = response["metadata"]
        self.model_name = self.metadata["model_name"]
        self.embedding_dimension = self.metadata["embedding_dimension"]
        self.batch_size = self.metadata["batch_size"]

    def _request(self, message):
        if self.process.poll() is not None:
            raise RuntimeError("Encoder worker exited; see its stderr for the inference failure")
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Encoder worker produced no response")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result

    def _encode(self, values, modality):
        response = self._request({"modality": modality, "values": [str(v) for v in values]})
        return np.frombuffer(base64.b64decode(response["vectors"]), dtype=np.float32).reshape(response["shape"]).copy()

    def encode_text(self, texts):
        return self._encode(texts, "text")

    def encode_images(self, paths):
        return self._encode(paths, "image")

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        self.process.stdout.close()


def main():
    config = json.loads(sys.stdin.readline())["config"]
    encoder = SiglipEncoder(config)
    print(json.dumps({"metadata": encoder.metadata}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            vectors = encoder.encode_text(request["values"]) if request["modality"] == "text" else encoder.encode_images(request["values"])
            print(json.dumps({"vectors": base64.b64encode(vectors.tobytes()).decode("ascii"), "shape": list(vectors.shape)}), flush=True)
        except Exception as error:
            print(json.dumps({"error": f"{type(error).__name__}: {error}"}), flush=True)


if __name__ == "__main__":
    main()
