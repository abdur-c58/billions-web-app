"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Folder,
  FolderPlus,
  HardDrive,
  LayoutGrid,
  List,
  Loader2,
  Music,
  Trash2,
  Upload,
  Film,
  FolderInput,
  Download,
  FolderKanban,
} from "lucide-react";
import { isMediaItemType, ROOT_STORAGE_FOLDERS, type StorageItem } from "@/lib/r2";
import { StorageDeleteModal } from "@/components/StorageDeleteModal";
import { StorageMoveModal } from "@/components/StorageMoveModal";
import { StoragePreviewModal } from "@/components/StoragePreviewModal";
import { StorageProjectFiles } from "@/components/StorageProjectFiles";
import { storageMediaUrl } from "@/lib/storage-media";
import { cn } from "@/lib/utils";

type ListResponse = {
  prefix: string;
  items: StorageItem[];
};

type ViewMode = "gallery" | "list";

type UploadProgress = {
  fileName: string;
  fileIndex: number;
  fileTotal: number;
  percent: number;
};

function readPathFromUrl() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("path") ?? "";
}

function readViewFromUrl(): "library" | "project" {
  if (typeof window === "undefined") return "library";
  return new URLSearchParams(window.location.search).get("view") === "project"
    ? "project"
    : "library";
}

function syncUrlState(nextPrefix: string, view: "library" | "project") {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (nextPrefix) {
    url.searchParams.set("path", nextPrefix);
  } else {
    url.searchParams.delete("path");
  }
  if (view === "project") {
    url.searchParams.set("view", "project");
  } else {
    url.searchParams.delete("view");
  }
  const next = `${url.pathname}${url.search}`;
  window.history.replaceState(null, "", next);
}

function uploadFileWithProgress(
  file: File,
  prefix: string,
  onProgress: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("prefix", prefix);
    form.append("file", file);

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
        return;
      }
      try {
        const payload = JSON.parse(xhr.responseText) as { error?: string };
        reject(new Error(payload.error || `Upload failed for ${file.name}`));
      } catch {
        reject(new Error(`Upload failed for ${file.name}`));
      }
    });

    xhr.addEventListener("error", () => reject(new Error(`Upload failed for ${file.name}`)));
    xhr.open("POST", "/api/storage/upload");
    xhr.send(form);
  });
}

const ROOT_FOLDER_META: Record<
  (typeof ROOT_STORAGE_FOLDERS)[number],
  { description: string; icon: typeof Music; accent: string }
> = {
  Audio: {
    description: "Narration, music, and sound effects",
    icon: Music,
    accent: "border-[#3b82f6]/40 bg-[#1e293b] hover:border-[#3b82f6]/60",
  },
  "B-Roll": {
    description: "Stock footage and video clips",
    icon: Film,
    accent: "border-[#8b5cf6]/40 bg-[#1e1b2e] hover:border-[#8b5cf6]/60",
  },
  Other: {
    description: "Everything else",
    icon: HardDrive,
    accent: "border-[var(--border-hover)] bg-[var(--surface-raised)] hover:border-[#71717a]",
  },
};

function formatSize(size: number | null) {
  if (size == null) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function ItemTypeIcon({ type, className }: { type: StorageItem["type"]; className?: string }) {
  if (type === "folder") return <Folder className={className} />;
  if (type === "video") return <Film className={className} />;
  if (type === "audio") return <Music className={className} />;
  return <HardDrive className={className} />;
}

function ViewToggle({
  mode,
  onChange,
}: {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
}) {
  return (
    <div className="view-toggle">
      <button
        type="button"
        aria-pressed={mode === "gallery"}
        onClick={() => onChange("gallery")}
        className={cn("view-toggle-btn", mode === "gallery" && "view-toggle-btn--active")}
      >
        <LayoutGrid className="h-4 w-4" />
        Gallery
      </button>
      <button
        type="button"
        aria-pressed={mode === "list"}
        onClick={() => onChange("list")}
        className={cn("view-toggle-btn", mode === "list" && "view-toggle-btn--active")}
      >
        <List className="h-4 w-4" />
        List
      </button>
    </div>
  );
}

function RootFolderCard({
  item,
  onOpen,
}: {
  item: StorageItem;
  onOpen: (item: StorageItem) => void;
}) {
  const meta = ROOT_FOLDER_META[item.name as (typeof ROOT_STORAGE_FOLDERS)[number]];
  const Icon = meta?.icon ?? Folder;

  return (
    <button
      type="button"
      onClick={() => onOpen(item)}
      className={cn(
        "glow-card group flex min-h-[180px] w-full flex-col items-start gap-4 rounded-[var(--radius-lg)] p-6 text-left transition-colors",
        meta?.accent ?? "hover:border-[var(--border-hover)]",
      )}
    >
      <div className="flex w-full items-start justify-between gap-3">
        <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] p-3">
          <Icon className="h-6 w-6 text-[var(--foreground)]" />
        </div>
        {item.protected ? (
          <span className="text-[0.68rem] font-medium uppercase tracking-[0.08em] text-[var(--muted)]">
            Protected
          </span>
        ) : null}
      </div>
      <div>
        <p className="text-lg font-semibold tracking-tight">{item.name}</p>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {meta?.description ?? "Open folder"}
        </p>
      </div>
      <span className="mt-auto text-sm font-medium text-[var(--muted)] group-hover:text-[var(--foreground)]">
        Open folder →
      </span>
    </button>
  );
}

function GalleryItemCard({
  item,
  busy,
  onOpen,
  onPreview,
  onDelete,
  onMove,
}: {
  item: StorageItem;
  busy: boolean;
  onOpen: (item: StorageItem) => void;
  onPreview: (item: StorageItem) => void;
  onDelete: (item: StorageItem) => void;
  onMove: (item: StorageItem) => void;
}) {
  const isFolder = item.type === "folder";
  const isMedia = isMediaItemType(item.type);

  const handleActivate = () => {
    if (isFolder) onOpen(item);
    else if (isMedia) onPreview(item);
  };

  return (
    <article className="glow-card flex flex-col overflow-hidden rounded-[var(--radius-lg)]">
      <button
        type="button"
        className={cn(
          "flex flex-1 flex-col items-stretch text-left",
          (isFolder || isMedia) && "cursor-pointer",
        )}
        onClick={handleActivate}
        disabled={!isFolder && !isMedia}
      >
        <div className="flex aspect-[4/3] items-center justify-center rounded-t-[var(--radius-lg)] border-b border-[var(--border)] bg-[var(--surface-raised)]">
          <ItemTypeIcon type={item.type} className="h-10 w-10 text-[var(--muted)]" />
        </div>
        <div className="flex flex-1 flex-col gap-1 p-4">
          <p className="line-clamp-2 font-medium leading-snug">{item.name}</p>
          <p className="text-xs text-[var(--muted)]">
            {isFolder ? "Folder" : formatSize(item.size)}
            {!isFolder && item.lastModified ? ` · ${formatDate(item.lastModified)}` : ""}
            {isMedia ? " · Click to preview" : ""}
          </p>
        </div>
      </button>
      <div className="flex items-center justify-end gap-1 border-t border-[var(--border)] px-3 py-2">
        {item.protected ? (
          <span className="mr-auto text-[0.68rem] uppercase tracking-[0.08em] text-[var(--muted)]">
            Protected
          </span>
        ) : (
          <>
            {isMedia ? (
              <a
                href={storageMediaUrl(item.key, true)}
                download={item.name}
                onClick={(event) => event.stopPropagation()}
                className="glow-btn-secondary rounded-[var(--radius-sm)] p-2"
                aria-label={`Download ${item.name}`}
                title="Download"
              >
                <Download className="h-4 w-4" />
              </a>
            ) : null}
            <button
              type="button"
              disabled={busy}
              onClick={() => onMove(item)}
              className="glow-btn-secondary rounded-[var(--radius-sm)] p-2 disabled:opacity-55"
              aria-label={`Move ${item.name}`}
            >
              <FolderInput className="h-4 w-4" />
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => onDelete(item)}
              className="glow-btn-secondary rounded-[var(--radius-sm)] p-2 disabled:opacity-55"
              aria-label={`Delete ${item.name}`}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </>
        )}
      </div>
    </article>
  );
}

function ListItemRow({
  item,
  busy,
  onOpen,
  onPreview,
  onDelete,
  onMove,
}: {
  item: StorageItem;
  busy: boolean;
  onOpen: (item: StorageItem) => void;
  onPreview: (item: StorageItem) => void;
  onDelete: (item: StorageItem) => void;
  onMove: (item: StorageItem) => void;
}) {
  const isFolder = item.type === "folder";
  const isMedia = isMediaItemType(item.type);

  const handleActivate = () => {
    if (isFolder) onOpen(item);
    else if (isMedia) onPreview(item);
  };

  return (
    <li className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3 last:border-b-0">
      <ItemTypeIcon type={item.type} className="h-4 w-4 shrink-0 text-[var(--muted)]" />
      <button
        type="button"
        className={cn(
          "min-w-0 flex-1 text-left",
          (isFolder || isMedia) && "font-medium hover:underline",
        )}
        onClick={handleActivate}
        disabled={!isFolder && !isMedia}
      >
        {item.name}
      </button>
      <span className="hidden text-sm text-[var(--muted)] sm:inline">
        {isFolder ? "Folder" : formatDate(item.lastModified)}
      </span>
      <span className="text-sm text-[var(--muted)]">{formatSize(item.size)}</span>
      {item.protected ? (
        <span className="text-[0.68rem] uppercase tracking-[0.08em] text-[var(--muted)]">
          Protected
        </span>
      ) : (
        <div className="flex items-center gap-1">
          {isMedia ? (
            <a
              href={storageMediaUrl(item.key, true)}
              download={item.name}
              className="glow-btn-secondary rounded-[var(--radius-sm)] p-2"
              aria-label={`Download ${item.name}`}
              title="Download"
            >
              <Download className="h-4 w-4" />
            </a>
          ) : null}
          <button
            type="button"
            disabled={busy}
            onClick={() => onMove(item)}
            className="glow-btn-secondary rounded-[var(--radius-sm)] p-2 disabled:opacity-55"
            aria-label={`Move ${item.name}`}
          >
            <FolderInput className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onDelete(item)}
            className="glow-btn-secondary rounded-[var(--radius-sm)] p-2 disabled:opacity-55"
            aria-label={`Delete ${item.name}`}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      )}
    </li>
  );
}

export function StorageBrowser() {
  const [prefix, setPrefix] = useState("");
  const [items, setItems] = useState<StorageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [folderName, setFolderName] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("gallery");
  const [deleteTarget, setDeleteTarget] = useState<StorageItem | null>(null);
  const [moveTarget, setMoveTarget] = useState<StorageItem | null>(null);
  const [previewTarget, setPreviewTarget] = useState<StorageItem | null>(null);
  const [storageView, setStorageView] = useState<"library" | "project">("library");
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const breadcrumbs = useMemo(() => {
    if (!prefix) return [];
    return prefix.replace(/\/$/, "").split("/");
  }, [prefix]);

  const isAtRoot = prefix === "";
  const folders = items.filter((item) => item.type === "folder");
  const files = items.filter((item) => item.type !== "folder");

  const refresh = useCallback(async (nextPrefix: string) => {
    setLoading(true);
    setError(null);
    setPrefix(nextPrefix);
    try {
      const response = await fetch(`/api/storage?prefix=${encodeURIComponent(nextPrefix)}`);
      const payload = (await response.json()) as ListResponse & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Failed to list storage");
      }
      setPrefix(payload.prefix);
      setItems(payload.items);
      syncUrlState(payload.prefix, storageView);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to list storage");
    } finally {
      setLoading(false);
    }
  }, [storageView]);

  useEffect(() => {
    setStorageView(readViewFromUrl());
    void refresh(readPathFromUrl());
  }, [refresh]);

  const openProjectFiles = () => {
    setStorageView("project");
    syncUrlState(prefix, "project");
  };

  const backToLibrary = () => {
    setStorageView("library");
    syncUrlState(prefix, "library");
  };

  const openFolder = (item: StorageItem) => {
    if (item.type !== "folder") return;
    void refresh(item.key);
  };

  const goToCrumb = (index: number) => {
    const parts = breadcrumbs.slice(0, index + 1);
    void refresh(parts.length ? `${parts.join("/")}/` : "");
  };

  const createFolder = async () => {
    if (!folderName.trim()) return;
    const name = folderName.trim();
    setBusy(true);
    setCreatingFolder(true);
    setError(null);
    setStatus(null);
    try {
      const response = await fetch("/api/storage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prefix, folderName: name }),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(payload.error || "Failed to create folder");
      setFolderName("");
      setStatus(`Created folder "${name}"`);
      await refresh(prefix);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create folder");
    } finally {
      setBusy(false);
      setCreatingFolder(false);
    }
  };

  const uploadFiles = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    const files = Array.from(fileList);
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      for (let index = 0; index < files.length; index += 1) {
        const file = files[index];
        setUploadProgress({
          fileName: file.name,
          fileIndex: index + 1,
          fileTotal: files.length,
          percent: 0,
        });
        await uploadFileWithProgress(file, prefix, (percent) => {
          setUploadProgress({
            fileName: file.name,
            fileIndex: index + 1,
            fileTotal: files.length,
            percent,
          });
        });
      }
      setStatus(`Uploaded ${files.length} file${files.length === 1 ? "" : "s"}`);
      await refresh(prefix);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploadProgress(null);
      setBusy(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  };

  const confirmDelete = async (item: StorageItem) => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const response = await fetch("/api/storage/delete", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: item.key }),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(payload.error || "Delete failed");
      setDeleteTarget(null);
      setStatus(`Deleted ${item.name}`);
      await refresh(prefix);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const confirmMove = async (item: StorageItem, destinationPrefix: string) => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const response = await fetch("/api/storage/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sourceKey: item.key, destinationPrefix }),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(payload.error || "Move failed");
      setMoveTarget(null);
      setStatus(`Moved ${item.name}`);
      await refresh(prefix);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Move failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 text-[var(--foreground)] lg:px-6">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Cloud storage</h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-[var(--muted)]">
          {storageView === "project"
            ? "Temporary project files from the b-roll pipeline."
            : isAtRoot
              ? "Choose a library folder to browse, upload, and organize your media."
              : `Browsing ${breadcrumbs.join(" / ")}`}
        </p>
        <div className="mt-4 flex justify-center">
          {storageView === "project" ? (
            <button
              type="button"
              onClick={backToLibrary}
              className="glow-btn-secondary px-3 py-1.5 text-xs font-semibold"
            >
              Back to library
            </button>
          ) : (
            <button
              type="button"
              onClick={openProjectFiles}
              className="glow-btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold"
            >
              <FolderKanban className="h-3.5 w-3.5" />
              View project files
            </button>
          )}
        </div>
      </div>

      {storageView === "project" ? (
        <StorageProjectFiles onPreview={setPreviewTarget} />
      ) : (
        <>

        <div className="glow-card mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-lg)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={loading}
            className="glow-btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold disabled:opacity-55"
            onClick={() => void refresh("")}
          >
            {loading && prefix === "" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Root
          </button>
          {breadcrumbs.map((crumb, index) => (
            <button
              key={`${crumb}-${index}`}
              type="button"
              disabled={loading}
              className="glow-btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold disabled:opacity-55"
              onClick={() => goToCrumb(index)}
            >
              {loading && index === breadcrumbs.length - 1 ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              {crumb}
            </button>
          ))}
        </div>
        {!isAtRoot ? <ViewToggle mode={viewMode} onChange={setViewMode} /> : null}
      </div>

      {!isAtRoot ? (
        <div className="glow-card mb-4 flex flex-wrap items-end gap-3 rounded-[var(--radius-lg)] p-4">
          <label className="min-w-[200px] flex-1">
            <span className="mb-1 block text-sm text-[var(--muted)]">New folder</span>
            <input
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              placeholder="Folder name"
              className="glow-control w-full px-3 py-2.5"
            />
          </label>
          <button
            type="button"
            disabled={busy || !folderName.trim()}
            onClick={() => void createFolder()}
            className="glow-btn-primary inline-flex items-center gap-2 px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
          >
            {creatingFolder ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FolderPlus className="h-4 w-4" />
            )}
            {creatingFolder ? "Creating…" : "Create folder"}
          </button>
          <label
            className={cn(
              "glow-btn-secondary inline-flex cursor-pointer items-center gap-2 px-3.5 py-2.5 text-sm font-semibold",
              busy && "cursor-not-allowed opacity-55",
            )}
          >
            {uploadProgress ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {uploadProgress ? "Uploading…" : "Upload media"}
            <input
              ref={uploadInputRef}
              type="file"
              multiple
              className="hidden"
              accept="video/*,audio/*,.mp4,.webm,.mov,.avi,.mkv,.m4v,.wmv,.flv,.mp3,.wav,.m4a,.aac,.ogg,.flac,.wma"
              disabled={busy}
              onChange={(event) => void uploadFiles(event.target.files)}
            />
          </label>
        </div>
      ) : null}

      {uploadProgress ? (
        <div className="glow-card mb-4 rounded-[var(--radius-lg)] p-4">
          <div className="flex items-center gap-2 text-sm">
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--accent)]" />
            <span>
              Uploading <span className="font-medium">{uploadProgress.fileName}</span> (
              {uploadProgress.fileIndex}/{uploadProgress.fileTotal})
            </span>
            <span className="ml-auto tabular-nums text-[var(--muted)]">{uploadProgress.percent}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--surface-raised)]">
            <div
              className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-150"
              style={{ width: `${uploadProgress.percent}%` }}
            />
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="mb-4 rounded-[var(--radius)] border border-red-500/35 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </p>
      ) : null}
      {status ? <p className="mb-4 text-center text-sm text-green-300">{status}</p> : null}

      {loading && items.length === 0 ? (
        <div className="flex items-center justify-center gap-2 py-16 text-[var(--muted)]">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading…
        </div>
      ) : isAtRoot ? (
        <div className={cn("relative", loading && "pointer-events-none opacity-60")}>
          {loading ? (
            <div className="absolute inset-x-0 top-0 z-10 flex justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--muted)]" />
            </div>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {folders.map((item) => (
              <RootFolderCard key={item.key} item={item} onOpen={openFolder} />
            ))}
          </div>
        </div>
      ) : items.length === 0 && !loading ? (
        <div className="glow-card px-4 py-16 text-center text-[var(--muted)]">
          This folder is empty. Upload media or create a subfolder.
        </div>
      ) : viewMode === "gallery" ? (
        <div className={cn("relative space-y-8", loading && "pointer-events-none opacity-60")}>
          {loading ? (
            <div className="absolute inset-x-0 top-0 z-10 flex justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--muted)]" />
            </div>
          ) : null}
          {folders.length > 0 ? (
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-[0.08em] text-[var(--muted)]">
                Folders
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {folders.map((item) => (
                  <GalleryItemCard
                    key={item.key}
                    item={item}
                    busy={busy}
                    onOpen={openFolder}
                    onPreview={setPreviewTarget}
                    onDelete={setDeleteTarget}
                    onMove={setMoveTarget}
                  />
                ))}
              </div>
            </section>
          ) : null}
          {files.length > 0 ? (
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-[0.08em] text-[var(--muted)]">
                Files
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {files.map((item) => (
                  <GalleryItemCard
                    key={item.key}
                    item={item}
                    busy={busy}
                    onOpen={openFolder}
                    onPreview={setPreviewTarget}
                    onDelete={setDeleteTarget}
                    onMove={setMoveTarget}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : (
        <div
          className={cn(
            "glow-card relative overflow-hidden rounded-[var(--radius-lg)]",
            loading && "pointer-events-none opacity-60",
          )}
        >
          {loading ? (
            <div className="absolute inset-x-0 top-0 z-10 flex justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--muted)]" />
            </div>
          ) : null}
          <ul>
            {items.map((item) => (
              <ListItemRow
                key={item.key}
                item={item}
                busy={busy}
                onOpen={openFolder}
                onPreview={setPreviewTarget}
                onDelete={setDeleteTarget}
                onMove={setMoveTarget}
              />
            ))}
          </ul>
        </div>
      )}
        </>
      )}

      <StoragePreviewModal item={previewTarget} onClose={() => setPreviewTarget(null)} />
      <StorageDeleteModal
        item={deleteTarget}
        busy={busy}
        onClose={() => setDeleteTarget(null)}
        onConfirm={(item) => void confirmDelete(item)}
      />
      <StorageMoveModal
        item={moveTarget}
        busy={busy}
        onClose={() => setMoveTarget(null)}
        onConfirm={(item, destinationPrefix) => void confirmMove(item, destinationPrefix)}
      />
    </main>
  );
}
