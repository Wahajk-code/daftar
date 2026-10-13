"use client";

const LONGEST_SIDE = 2200;
const QUALITY = 0.82;
const SKIP_BELOW_BYTES = 900 * 1024;

/**
 * Gets a photo ready to send as a receipt. A phone photo is several megabytes and often sideways in its data; this turns it
 * upright, shrinks it so the longest side is at most 2200 px (plenty to read a receipt) and saves it as a JPEG, which makes the
 * upload a fraction of the size on a mobile connection. A small image that is already the right size is left alone. If the
 * browser cannot do it, the original goes as it is and the server's own checks decide.
 */
export async function prepareReceipt(file: File): Promise<File> {
  if (!file.type.startsWith("image/") || typeof createImageBitmap !== "function") return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, LONGEST_SIDE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size <= SKIP_BELOW_BYTES && file.type === "image/jpeg") {
      bitmap.close();
      return file;
    }
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const context = canvas.getContext("2d");
    if (!context) {
      bitmap.close();
      return file;
    }
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", QUALITY));
    if (!blob || blob.size >= file.size) return file;
    const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
    return new File([blob], `receipt-${stamp}.jpg`, { type: "image/jpeg", lastModified: Date.now() });
  } catch {
    return file;
  }
}
