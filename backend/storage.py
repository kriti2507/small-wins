"""Image storage in a private Supabase Storage bucket via the Storage REST API.

Uses only the standard library (urllib) to keep the serverless cold start
small — no Supabase SDK. The service-role key is server-side only.

Browser uploads go straight to Supabase via signed_upload_url: a Vercel
function's request body is capped at 4.5 MB, which an ordinary phone photo
exceeds, so image bytes must never pass through our own server.
"""
import json
import os
import re
import urllib.error
import urllib.request


def _cfg():
    return (
        os.environ["SUPABASE_URL"].rstrip("/"),
        os.environ["SUPABASE_SERVICE_KEY"],
        os.environ.get("SUPABASE_BUCKET", "uploads"),
    )


IMAGE_PATH_PREFIX = "/api/images/"
# Uploads are never overwritten (keys are random), so browsers may keep them
# for a year.
IMMUTABLE_CACHE = "max-age=31536000"


class NotFound(Exception):
    """Supabase has no object under that key."""


def safe_name(name):
    """An allowlisted single path segment. Our own keys are uuid4().hex plus
    an extension (or ".thumb"); anything else - spaces, control characters,
    backslashes, non-ASCII, a lone "." - is refused here so it 404s instead of
    turning into a urllib error. user_key is the sole ownership gate, so this
    has to be strict."""
    return bool(name) and ".." not in name and re.fullmatch(
        r"[A-Za-z0-9_-][A-Za-z0-9._-]*", name
    ) is not None


def user_key(key, user_id):
    """`key` if it is one of user_id's objects (users/<id>/<name>), else None.

    The one place that decides which objects a user may read or delete.
    """
    if not isinstance(key, str) or user_id is None:
        return None
    prefix = f"users/{user_id}/"
    if not key.startswith(prefix) or not safe_name(key[len(prefix):]):
        return None
    return key


def image_path_for(name):
    """The app path the DB stores for an object; GET it to see the image."""
    return f"{IMAGE_PATH_PREFIX}{name}"


def thumb_name_for(name):
    """The thumbnail's key: same stem, `.thumb` instead of the extension.
    No real extension because it may be WebP or JPEG; its stored content
    type says which."""
    head, _, last = name.rpartition("/")
    stem = last.rsplit(".", 1)[0] if "." in last else last
    return f"{head}/{stem}.thumb" if head else f"{stem}.thumb"


def _is_not_found(err):
    """Supabase Storage answers a missing object with 404, or with 400 and a
    JSON body whose statusCode is "404". A missing bucket answers the same
    way, so a misconfigured bucket also reads as NotFound here."""
    if err.code == 404:
        return True
    if err.code != 400:
        return False
    try:
        body = json.loads(err.read() or b"{}")
    except ValueError:
        return False
    if not isinstance(body, dict):
        return False
    return str(body.get("statusCode")) == "404" or body.get("error") == "not_found"


def _open(req):
    """urlopen, turning Supabase's "no such object" into NotFound."""
    try:
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as err:
        if _is_not_found(err):
            err.close()
            raise NotFound(req.full_url) from err
        raise


def _authed(req):
    """Add the service-role credentials Supabase Storage requires."""
    _base, key, _bucket = _cfg()
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("apikey", key)
    return req


def signed_read_url(name, expires_in):
    """A time-limited URL the browser can GET `name` from. Raises NotFound
    when there is no such object."""
    base, _key, bucket = _cfg()
    req = _authed(urllib.request.Request(
        f"{base}/storage/v1/object/sign/{bucket}/{name}",
        data=json.dumps({"expiresIn": expires_in}).encode(),
        method="POST",
    ))
    req.add_header("Content-Type", "application/json")
    with _open(req) as resp:
        payload = json.loads(resp.read())
    # Relative to /storage/v1, like signed_upload_url's answer.
    return f"{base}/storage/v1{payload['signedURL']}"


def download(name):
    """(bytes, content type) of an object. Used by the migration script."""
    base, _key, bucket = _cfg()
    req = _authed(urllib.request.Request(f"{base}/storage/v1/object/{bucket}/{name}"))
    with _open(req) as resp:
        return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")


def signed_upload_url(name, expires_in=600):
    """Mint a single-use URL the browser can upload `name` to directly.

    The caller picks the key, so the image's app path is knowable up front.
    """
    base, _key, bucket = _cfg()
    req = _authed(urllib.request.Request(
        f"{base}/storage/v1/object/upload/sign/{bucket}/{name}",
        data=json.dumps({"expiresIn": expires_in}).encode(),
        method="POST",
    ))
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    # Supabase answers with a path relative to /storage/v1; the browser needs
    # the whole thing. A missing "url" means the sign failed — let it raise.
    return f"{base}/storage/v1{payload['url']}"


def upload_bytes(name, data, content_type, cache_control=None):
    """Upload bytes to the bucket under `name`, replacing any object there.

    Server-side path, used by the migration scripts. Browser uploads use
    signed_upload_url instead.
    """
    base, _key, bucket = _cfg()
    req = _authed(urllib.request.Request(
        f"{base}/storage/v1/object/{bucket}/{name}", data=data, method="POST"
    ))
    req.add_header("Content-Type", content_type)
    req.add_header("x-upsert", "true")
    if cache_control:
        req.add_header("Cache-Control", cache_control)
    with urllib.request.urlopen(req) as resp:
        resp.read()


def object_name_for(url, user_id):
    """The object key behind an image path the DB stores, if it is one of
    user_id's own objects; else None.

    Never let a URL we didn't mint for this user become a delete against our
    bucket. Old public-bucket URLs are deliberately not recognised: those
    objects are swept by migrate_storage_003.py --delete-old.
    """
    if not isinstance(url, str) or not url.startswith(IMAGE_PATH_PREFIX):
        return None
    return user_key(url[len(IMAGE_PATH_PREFIX):], user_id)


def _list_pages(prefix):
    """Yield each page (up to 1000) of object names directly under `prefix`.
    Folders (like users/) come back with a null id and are skipped."""
    base, _key, bucket = _cfg()
    offset = 0
    while True:
        req = _authed(urllib.request.Request(
            f"{base}/storage/v1/object/list/{bucket}",
            data=json.dumps({"prefix": prefix, "limit": 1000, "offset": offset}).encode(),
            method="POST",
        ))
        req.add_header("Content-Type", "application/json")
        with _open(req) as resp:
            page = json.loads(resp.read())
        yield [o["name"] for o in page if o.get("id")]
        if len(page) < 1000:
            return
        offset += 1000


def list_root_objects():
    """Names of the objects at the bucket root (not under any folder). Used
    by the migration script's --delete-old."""
    return [name for page in _list_pages("") for name in page]


def count_user_images(user_id, stop_at):
    """How many images user_id has stored, not counting thumbnails. Stops
    listing once the count reaches stop_at, so a full account costs one page
    rather than all of them."""
    count = 0
    for page in _list_pages(f"users/{user_id}/"):
        count += sum(1 for name in page if not name.endswith(".thumb"))
        if count >= stop_at:
            break
    return count


def delete_object(name):
    """Delete an object from the bucket. Raises NotFound if it isn't there;
    other exceptions propagate to the caller."""
    base, _key, bucket = _cfg()
    req = _authed(urllib.request.Request(
        f"{base}/storage/v1/object/{bucket}/{name}", method="DELETE"
    ))
    with _open(req) as resp:
        resp.read()
