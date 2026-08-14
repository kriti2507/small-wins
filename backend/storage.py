"""Image uploads to a public Supabase Storage bucket via the Storage REST API.

Uses only the standard library (urllib) to keep the serverless cold start
small — no Supabase SDK. The service-role key is server-side only.

Browser uploads go straight to Supabase via signed_upload_url: a Vercel
function's request body is capped at 4.5 MB, which an ordinary phone photo
exceeds, so image bytes must never pass through our own server.
"""
import json
import os
import urllib.request


def _cfg():
    return (
        os.environ["SUPABASE_URL"].rstrip("/"),
        os.environ["SUPABASE_SERVICE_KEY"],
        os.environ.get("SUPABASE_BUCKET", "uploads"),
    )


def _public_url_prefix():
    base, _key, bucket = _cfg()
    return f"{base}/storage/v1/object/public/{bucket}/"


def public_url_for(name):
    """The URL an uploaded object will be readable at, known before it exists."""
    return f"{_public_url_prefix()}{name}"


def signed_upload_url(name, expires_in=600):
    """Mint a single-use URL the browser can upload `name` to directly.

    The caller picks the key, so the public URL is knowable up front and stays
    within the bucket — object_name_for can still recognise it later.
    """
    base, key, bucket = _cfg()
    req = urllib.request.Request(
        f"{base}/storage/v1/object/upload/sign/{bucket}/{name}",
        data=json.dumps({"expiresIn": expires_in}).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("apikey", key)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    # Supabase answers with a path relative to /storage/v1; the browser needs
    # the whole thing. A missing "url" means the sign failed — let it raise.
    return f"{base}/storage/v1{payload['url']}"


def upload_bytes(name, data, content_type):
    """Upload bytes to the bucket and return the file's public URL.

    Server-side path, used by the one-off migration script. Browser uploads
    use signed_upload_url instead.
    """
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
    return public_url_for(name)


def object_name_for(url):
    """Return the object key for url if it points at our public bucket, else None.

    Never let a URL we didn't mint become a delete against our bucket.
    """
    if not url:
        return None
    prefix = _public_url_prefix()
    if not url.startswith(prefix):
        return None
    name = url[len(prefix):]
    # The prefix check only proves where the URL came from; this proves the key
    # can't climb out of the bucket. urllib sends ".." unnormalized and Supabase's
    # edge collapses it. Our own keys are uuid4().hex + ext, so this rejects
    # nothing we mint.
    if not name or ".." in name or any(c in name for c in "%?#"):
        return None
    return name


def delete_object(name):
    """Delete an object from the bucket. Exceptions propagate to the caller."""
    base, key, bucket = _cfg()
    req = urllib.request.Request(
        f"{base}/storage/v1/object/{bucket}/{name}", method="DELETE"
    )
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("apikey", key)
    with urllib.request.urlopen(req) as resp:
        resp.read()
