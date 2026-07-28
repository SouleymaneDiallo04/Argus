// Dessine la frame courante de la vidéo sur un canvas et renvoie le JPEG base64 (sans préfixe data:).
export function grabFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  quality = 0.6
): string | null {
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (!w || !h) return null;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, w, h);
  const url = canvas.toDataURL("image/jpeg", quality);
  return url.split(",")[1] ?? null;
}
