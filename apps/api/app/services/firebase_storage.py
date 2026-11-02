"""Compatibility helpers using the same Firebase bootstrap as the API."""

from app.core.firebase import initialize_firebase


def get_storage_bucket():
    return initialize_firebase()["storage"]


def upload_file(local_file_path, destination_path, content_type="application/octet-stream"):
    bucket = get_storage_bucket()
    blob = bucket.blob(destination_path)
    blob.upload_from_filename(local_file_path, content_type=content_type, timeout=30, retry=None)
    return {"file_name": blob.name.split("/")[-1], "storage_path": blob.name, "bucket": bucket.name}


def download_file(storage_path, destination_path):
    get_storage_bucket().blob(storage_path).download_to_filename(
        destination_path, timeout=30, retry=None
    )
    return destination_path


def delete_file(storage_path):
    get_storage_bucket().blob(storage_path).delete(timeout=30, retry=None)
    return {"deleted": True, "storage_path": storage_path}
