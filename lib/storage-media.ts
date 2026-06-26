export function storageMediaUrl(key: string, download = false) {
  const params = new URLSearchParams({ key });
  if (download) params.set("download", "1");
  return `/api/storage/media?${params.toString()}`;
}

export const AUDIO_PREVIEW_SECONDS = 30;

export function probeVideoDuration(url: string): Promise<number | null> {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.preload = "metadata";

    const finish = (value: number | null) => {
      video.removeAttribute("src");
      video.load();
      resolve(value);
    };

    video.addEventListener(
      "loadedmetadata",
      () => {
        finish(Number.isFinite(video.duration) && video.duration > 0 ? video.duration : null);
      },
      { once: true },
    );
    video.addEventListener("error", () => finish(null), { once: true });
    video.src = url;
  });
}
