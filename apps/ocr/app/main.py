"""Private, single-worker Vietnamese PaddleOCR service."""

import io
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

os.environ.setdefault("FLAGS_allocator_strategy", "auto_growth")
os.environ.setdefault("FLAGS_fraction_of_gpu_memory_to_use", "0.15")
os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from PIL import Image, ImageOps

logger = logging.getLogger("uvicorn.error")
MAX_BYTES = 20 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 25_000_000


class Runtime:
    def __init__(self):
        self.model = None
        self.lock = threading.Lock()
        self.error = None

    def load(self):
        try:
            import paddle
            from paddleocr import PaddleOCR

            if (
                not paddle.device.is_compiled_with_cuda()
                or paddle.device.cuda.device_count() < 1
            ):
                raise RuntimeError("CUDA unavailable")
            self.model = PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
                device="gpu:0",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_recognition_batch_size=1,
                text_det_limit_side_len=2560,
                text_det_limit_type="max",
            )
        except Exception as exc:
            self.error = type(exc).__name__
            logger.exception("OCR model startup failed (%s)", self.error)

    def recognize(self, content):
        if self.model is None:
            raise HTTPException(503, "OCR model unavailable")
        if not self.lock.acquire(blocking=False):
            raise HTTPException(429, "OCR busy", headers={"Retry-After": "2"})
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                    raise HTTPException(413, "Image dimensions too large")
                image = ImageOps.exif_transpose(image).convert("RGB")
                values = np.asarray(image)
            start = time.monotonic()
            predictions = self.model.predict(values)
            lines = []
            for result in predictions:
                for text, box in zip(
                    result.get("rec_texts", []), result.get("rec_boxes", [])
                ):
                    if str(text).strip():
                        lines.append(
                            {"text": str(text).strip(), "box": [int(x) for x in box]}
                        )
            # Paddle returns detected lines in reading order; retain line breaks for legal headings.
            logger.info(
                "ocr page lines=%s duration_ms=%s",
                len(lines),
                round((time.monotonic() - start) * 1000),
            )
            return {"text": "\n".join(line["text"] for line in lines), "lines": lines}
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("OCR inference failed (%s)", type(exc).__name__)
            raise HTTPException(503, "OCR inference failed") from None
        finally:
            self.lock.release()


runtime = Runtime()


@asynccontextmanager
async def lifespan(app):
    runtime.load()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if runtime.model is None:
        raise HTTPException(503, "OCR model unavailable")
    return {"status": "ready", "device": "gpu:0", "language": "vi"}


@app.post("/v1/ocr")
async def recognize(request: Request):
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_BYTES):
        raise HTTPException(413, "Image too large")
    parts = []
    size = 0
    async for part in request.stream():
        size += len(part)
        if size > MAX_BYTES:
            raise HTTPException(413, "Image too large")
        parts.append(part)
    if not size:
        raise HTTPException(422, "Image required")
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(runtime.recognize, b"".join(parts))
