// Shrink photos in the browser before they are uploaded.
//
// Uploads go straight to Supabase (see uploadImage), so this is no longer what
// keeps us under Vercel's 4.5 MB function body limit — but a phone photo is
// several megabytes and an entry page shows many of them, so re-encoding is
// what keeps the site quick to load.

export const MAX_DIM = 2000; // longest edge, comfortably past any display size
export const QUALITY = 0.85;
export const SKIP_BYTES = 512 * 1024; // already light enough to leave alone

export interface Fit {
  width: number;
  height: number;
  scaled: boolean;
}

// Extensions the backend's ALLOWED_EXT will sign an upload for.
const EXT_BY_TYPE: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/gif": "gif",
};

export function extFor(type: string): string {
  return EXT_BY_TYPE[type.split(";")[0].trim().toLowerCase()] ?? "";
}

export function fitWithin(width: number, height: number, maxDim = MAX_DIM): Fit {
  const longest = Math.max(width, height);
  if (longest <= maxDim) return { width, height, scaled: false };
  const scale = maxDim / longest;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
    scaled: true,
  };
}

export function shouldReencode(
  file: { type: string; size: number },
  fit: Fit,
): boolean {
  // A GIF may be animated, and drawing it to a canvas keeps only frame one.
  if (file.type === "image/gif") return false;
  return fit.scaled || file.size > SKIP_BYTES;
}

// WebP keeps alpha and compresses far better than JPEG. Every browser we care
// about encodes it, but toDataURL quietly falls back to PNG where it doesn't,
// so ask before relying on it.
function encodeType(): "image/webp" | "image/jpeg" {
  const probe = document.createElement("canvas");
  probe.width = probe.height = 1;
  return probe.toDataURL("image/webp").startsWith("data:image/webp")
    ? "image/webp"
    : "image/jpeg";
}

function toBlob(canvas: HTMLCanvasElement, type: string): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, type, QUALITY));
}

/** The bytes to upload for `file`, plus the extension to register them under. */
export async function prepareImage(
  file: File,
): Promise<{ blob: Blob; ext: string }> {
  const asIs = () => {
    const ext = extFor(file.type);
    if (!ext) {
      throw new Error("That image format isn't supported. Use JPEG, PNG or WebP.");
    }
    return { blob: file as Blob, ext };
  };

  if (file.type === "image/gif") return asIs();

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    // Most often an iPhone HEIC on a browser that can't decode it.
    throw new Error("Could not read that image. Try JPEG, PNG or WebP.");
  }

  const fit = fitWithin(bitmap.width, bitmap.height);
  const ctx = (() => {
    if (!shouldReencode(file, fit)) return null;
    const canvas = document.createElement("canvas");
    canvas.width = fit.width;
    canvas.height = fit.height;
    return canvas.getContext("2d");
  })();

  if (!ctx) {
    bitmap.close();
    return asIs();
  }

  const type = encodeType();
  if (type === "image/jpeg") {
    // JPEG has no alpha; without this, transparent pixels come out black.
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, fit.width, fit.height);
  }
  ctx.drawImage(bitmap, 0, 0, fit.width, fit.height);
  bitmap.close();

  const blob = await toBlob(ctx.canvas, type);
  // Re-encoding can lose to an already well-compressed original; if we didn't
  // need to shrink it either, the original is the better upload.
  if (!blob || (!fit.scaled && blob.size >= file.size)) return asIs();

  return { blob, ext: extFor(blob.type) || (type === "image/webp" ? "webp" : "jpg") };
}
