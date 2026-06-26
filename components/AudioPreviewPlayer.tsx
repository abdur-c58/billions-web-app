"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Pause, Play } from "lucide-react";
import { AUDIO_PREVIEW_SECONDS } from "@/lib/storage-media";
import { cn } from "@/lib/utils";

function formatPreviewTime(seconds: number) {
  const safe = Math.max(0, Math.min(seconds, AUDIO_PREVIEW_SECONDS));
  const whole = Math.floor(safe);
  const minutes = Math.floor(whole / 60);
  const remainder = whole % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

type AudioPreviewPlayerProps = {
  src: string;
  label?: string;
  autoPlay?: boolean;
};

export function AudioPreviewPlayer({
  src,
  label,
  autoPlay = true,
}: AudioPreviewPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const capTime = useCallback((audio: HTMLAudioElement) => {
    if (audio.currentTime < 0) {
      audio.currentTime = 0;
    }
    if (audio.currentTime > AUDIO_PREVIEW_SECONDS) {
      audio.pause();
      audio.currentTime = AUDIO_PREVIEW_SECONDS;
      setPlaying(false);
    }
    setCurrent(Math.min(audio.currentTime, AUDIO_PREVIEW_SECONDS));
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    setPlaying(false);
    setCurrent(0);
    setLoading(true);
    setError(null);
    audio.pause();
    audio.currentTime = 0;

    const onLoadedMetadata = () => {
      setLoading(false);
      audio.currentTime = 0;
      setCurrent(0);
      if (autoPlay) {
        void audio.play().catch(() => {
          setPlaying(false);
        });
      }
    };
    const onTimeUpdate = () => capTime(audio);
    const onSeeked = () => capTime(audio);
    const onPlay = () => {
      if (audio.currentTime >= AUDIO_PREVIEW_SECONDS) {
        audio.currentTime = 0;
        setCurrent(0);
      }
      setPlaying(true);
    };
    const onPause = () => setPlaying(false);
    const onEnded = () => {
      setPlaying(false);
      setCurrent(AUDIO_PREVIEW_SECONDS);
    };
    const onError = () => {
      setLoading(false);
      setPlaying(false);
      setError("Could not load audio preview.");
    };

    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("seeked", onSeeked);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);

    return () => {
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("seeked", onSeeked);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
      audio.pause();
    };
  }, [src, autoPlay, capTime]);

  const togglePlayback = () => {
    const audio = audioRef.current;
    if (!audio || loading) return;

    if (playing) {
      audio.pause();
      return;
    }

    if (audio.currentTime >= AUDIO_PREVIEW_SECONDS) {
      audio.currentTime = 0;
      setCurrent(0);
    }

    void audio.play().catch(() => setPlaying(false));
  };

  const seekTo = (clientX: number) => {
    const audio = audioRef.current;
    const track = trackRef.current;
    if (!audio || !track || loading) return;

    const rect = track.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const nextTime = ratio * AUDIO_PREVIEW_SECONDS;
    audio.currentTime = nextTime;
    setCurrent(nextTime);
    if (nextTime >= AUDIO_PREVIEW_SECONDS) {
      audio.pause();
      setPlaying(false);
    }
  };

  const progress = (current / AUDIO_PREVIEW_SECONDS) * 100;

  return (
    <div className="audio-preview">
      <audio ref={audioRef} src={src} preload="metadata" className="hidden" />

      <div className="audio-preview-wave" aria-hidden="true">
        {Array.from({ length: 48 }).map((_, index) => (
          <span
            key={index}
            className={cn("audio-preview-wave-bar", playing && "is-active")}
            style={{
              animationDelay: `${(index % 12) * 0.07}s`,
              height: `${28 + ((index * 17) % 56)}%`,
            }}
          />
        ))}
      </div>

      <div className="audio-preview-body">
        {label ? (
          <p className="mb-3 truncate text-sm font-medium text-[var(--foreground)]">{label}</p>
        ) : null}

        {error ? (
          <p className="text-sm text-red-300">{error}</p>
        ) : (
          <>
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={togglePlayback}
                disabled={loading}
                className="audio-preview-play"
                aria-label={playing ? "Pause preview" : "Play preview"}
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : playing ? (
                  <Pause className="h-5 w-5" />
                ) : (
                  <Play className="h-5 w-5 translate-x-0.5" />
                )}
              </button>

              <div className="min-w-0 flex-1">
                <div
                  ref={trackRef}
                  className="audio-preview-track"
                  onClick={(event) => seekTo(event.clientX)}
                  onKeyDown={(event) => {
                    if (event.key === "ArrowRight") {
                      const audio = audioRef.current;
                      if (!audio) return;
                      const next = Math.min(AUDIO_PREVIEW_SECONDS, audio.currentTime + 1);
                      audio.currentTime = next;
                      setCurrent(next);
                    }
                    if (event.key === "ArrowLeft") {
                      const audio = audioRef.current;
                      if (!audio) return;
                      const next = Math.max(0, audio.currentTime - 1);
                      audio.currentTime = next;
                      setCurrent(next);
                    }
                  }}
                  role="slider"
                  tabIndex={0}
                  aria-valuemin={0}
                  aria-valuemax={AUDIO_PREVIEW_SECONDS}
                  aria-valuenow={Math.round(current)}
                  aria-label="Preview position"
                >
                  <div className="audio-preview-track-fill" style={{ width: `${progress}%` }} />
                  <div className="audio-preview-track-thumb" style={{ left: `${progress}%` }} />
                </div>

                <div className="mt-2 flex items-center justify-between text-xs tabular-nums text-[var(--muted)]">
                  <span>{formatPreviewTime(current)}</span>
                  <span>Preview · {formatPreviewTime(AUDIO_PREVIEW_SECONDS)} max</span>
                </div>
              </div>
            </div>

            <p className="mt-4 text-xs text-[var(--muted)]">
              Playback is limited to the first {AUDIO_PREVIEW_SECONDS} seconds. Download for the
              full file.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
