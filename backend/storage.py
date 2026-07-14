"""Image uploads to a public Supabase Storage bucket via the Storage REST API.

Uses only the standard library (urllib) to keep the serverless cold start
small — no Supabase SDK. The service-role key is server-side only.
"""
import os
import urllib.request


def _cfg():
    return (
        os.environ["SUPABASE_URL"].rstrip("/"),
        os.environ["SUPABASE_SERVICE_KEY"],
        os.environ.get("SUPABASE_BUCKET", "uploads"),
    )


def upload_bytes(name, data, content_type):
    """Upload bytes to the bucket and return the file's public URL."""
    base, key, bucket = _cfg()
    req = urllib.request.Request(
        f"{base}/storage/v1/object/{bucket}/{name}", data=data, method="POST"
    )
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("apikey", key)
    req.add_header("Content-Type", content_type)
    req.add_header("x-upsert", "true")
    with urllib.request.urlopen(req) as resp:
        resp.read()
    return f"{base}/storage/v1/object/public/{bucket}/{name}"
