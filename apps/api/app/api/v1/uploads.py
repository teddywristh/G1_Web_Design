import hashlib
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import APIError


async def receive_pdf(request, store, repo, bucket, doc_id, actor, version, **options):
    """Stream a bounded raw PDF to disk, then call store(...) in a worker thread."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/pdf":
        raise APIError(415, "unsupported_media_type", "Send a raw application/pdf body")
    maximum = get_settings().max_upload_size_bytes
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) < 0:
                raise ValueError()
            if int(length) > maximum:
                raise APIError(413, "file_too_large", "PDF exceeds upload limit")
        except ValueError as exc:
            raise APIError(422, "invalid_length", "Invalid Content-Length") from exc
    # Bound RAM and disk even when Content-Length is absent or false.
    size, prefix = 0, b""
    digest = hashlib.sha256()
    with TemporaryDirectory(prefix="legal-upload-") as directory:
        path = Path(directory) / "source.pdf"
        with path.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > maximum:
                    raise APIError(413, "file_too_large", "PDF exceeds upload limit")
                if len(prefix) < 5:
                    prefix = (prefix + chunk)[:5]
                digest.update(chunk)
                await run_in_threadpool(handle.write, chunk)
        if prefix != b"%PDF-":
            raise APIError(415, "invalid_pdf", "PDF signature is required")
        return await run_in_threadpool(
            store,
            repo,
            bucket,
            doc_id,
            str(path),
            size,
            digest.hexdigest(),
            actor,
            request.state.request_id,
            version,
            **options,
        )


def send_pdf(bucket, storage_path, filename):
    """Download a stored PDF to a temp file and stream it back without public URLs."""
    handle = NamedTemporaryFile(delete=False, suffix=".pdf")
    path = handle.name
    handle.close()
    try:
        blob = bucket.blob(storage_path)
        blob.reload(timeout=10, retry=None)
        if blob.size is None or blob.size > get_settings().max_upload_size_bytes:
            raise APIError(503, "file_unavailable", "Stored file exceeds the download limit")
        blob.download_to_filename(
            path,
            if_generation_match=blob.generation,
            timeout=get_settings().storage_timeout_seconds,
            retry=None,
        )
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        background=BackgroundTask(Path(path).unlink, missing_ok=True),
    )
