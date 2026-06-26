import {
  DeleteObjectCommand,
  HeadObjectCommand,
  ListObjectsV2Command,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { contentTypeForStorageName } from "@/lib/r2";

export const PROJECT_STORAGE_PREFIX = ".project/";

export const PROJECT_WORKSPACE_FILES = [
  "script.json",
  "script.mp3",
  "segment_timestamps.json",
  "broll_selections.json",
] as const;

export type ProjectWorkspaceFile = (typeof PROJECT_WORKSPACE_FILES)[number];

export const PROJECT_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type ProjectStorageItem = {
  key: string;
  name: ProjectWorkspaceFile;
  size: number | null;
  lastModified: string | null;
  expiresAt: string;
  expired: boolean;
  userId?: string;
  projectId?: string;
};

function getClient() {
  const accountId = process.env.R2_ACCOUNT_ID;
  const accessKeyId = process.env.R2_ACCESS_KEY_ID;
  const secretAccessKey = process.env.R2_SECRET_ACCESS_KEY;
  const bucket = process.env.R2_BUCKET_NAME;

  if (!accountId || !accessKeyId || !secretAccessKey || !bucket) {
    throw new Error(
      "R2 is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME.",
    );
  }

  return {
    client: new S3Client({
      region: "auto",
      endpoint: `https://${accountId}.r2.cloudflarestorage.com`,
      credentials: { accessKeyId, secretAccessKey },
    }),
    bucket,
  };
}

export function isProjectStorageKey(key: string) {
  return key.startsWith(PROJECT_STORAGE_PREFIX);
}

export function isHiddenStorageKey(key: string) {
  return key.startsWith(".project/");
}

export function projectStorageKey(projectId: string, name: string) {
  const safe = name.replace(/[/\\]+/g, "").trim();
  if (!PROJECT_WORKSPACE_FILES.includes(safe as ProjectWorkspaceFile)) {
    throw new Error(`Unsupported project file: ${name}`);
  }
  return `${PROJECT_STORAGE_PREFIX}projects/${projectId}/${safe}`;
}

/** @deprecated Legacy flat key — only for old backups */
export function legacyProjectStorageKey(name: string) {
  const safe = name.replace(/[/\\]+/g, "").trim();
  return `.project/workspace/${safe}`;
}

function expiryFromMetadata(metadata: Record<string, string> | undefined, lastModified?: Date) {
  const raw = metadata?.["expires-at"];
  if (raw) {
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed * 1000;
    }
  }
  if (lastModified) {
    return lastModified.getTime() + PROJECT_TTL_MS;
  }
  return Date.now() + PROJECT_TTL_MS;
}

export function isR2Configured() {
  return Boolean(
    process.env.R2_ACCOUNT_ID &&
      process.env.R2_ACCESS_KEY_ID &&
      process.env.R2_SECRET_ACCESS_KEY &&
      process.env.R2_BUCKET_NAME,
  );
}

export async function uploadProjectWorkspaceFile(projectId: string, name: string, body: Buffer) {
  const fileName = name.replace(/[/\\]+/g, "").trim();
  if (!PROJECT_WORKSPACE_FILES.includes(fileName as ProjectWorkspaceFile)) {
    throw new Error(`Unsupported project file: ${name}`);
  }

  const { client, bucket } = getClient();
  const key = projectStorageKey(projectId, fileName);
  const expiresAt = Math.floor((Date.now() + PROJECT_TTL_MS) / 1000);

  await client.send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: body,
      ContentType: contentTypeForStorageName(fileName),
      Metadata: {
        "expires-at": String(expiresAt),
        "project-file": fileName,
      },
    }),
  );

  return {
    key,
    name: fileName as ProjectWorkspaceFile,
    expiresAt: new Date(expiresAt * 1000).toISOString(),
  };
}

export async function purgeExpiredProjectFiles() {
  if (!isR2Configured()) return { deleted: [] as string[] };

  const { client, bucket } = getClient();
  const response = await client.send(
    new ListObjectsV2Command({
      Bucket: bucket,
      Prefix: PROJECT_STORAGE_PREFIX,
    }),
  );

  const deleted: string[] = [];
  const now = Date.now();

  for (const entry of response.Contents || []) {
    const key = entry.Key;
    if (!key || key.endsWith("/")) continue;

    let expiresMs = expiryFromMetadata(undefined, entry.LastModified);
    try {
      const head = await client.send(
        new HeadObjectCommand({
          Bucket: bucket,
          Key: key,
        }),
      );
      expiresMs = expiryFromMetadata(head.Metadata, head.LastModified);
    } catch {
      // Fall back to list metadata.
    }

    if (expiresMs <= now) {
      await client.send(
        new DeleteObjectCommand({
          Bucket: bucket,
          Key: key,
        }),
      );
      deleted.push(key);
    }
  }

  return { deleted };
}

function parseProjectKey(key: string): { projectId: string; name: ProjectWorkspaceFile } | null {
  const scoped = key.match(
    /^\.project\/projects\/([^/]+)\/(script\.json|script\.mp3|segment_timestamps\.json|broll_selections\.json)$/,
  );
  if (scoped) {
    return {
      projectId: scoped[1],
      name: scoped[2] as ProjectWorkspaceFile,
    };
  }
  const userScoped = key.match(
    /^\.project\/users\/[^/]+\/projects\/([^/]+)\/(script\.json|script\.mp3|segment_timestamps\.json|broll_selections\.json)$/,
  );
  if (userScoped) {
    return {
      projectId: userScoped[1],
      name: userScoped[2] as ProjectWorkspaceFile,
    };
  }
  const legacy = key.match(
    /^\.project\/workspace\/(script\.json|script\.mp3|segment_timestamps\.json|broll_selections\.json)$/,
  );
  if (legacy) {
    return { projectId: "legacy", name: legacy[1] as ProjectWorkspaceFile };
  }
  return null;
}

export async function listProjectWorkspaceFiles(options?: { projectId?: string }) {
  if (!isR2Configured()) {
    return { items: [] as ProjectStorageItem[], ttlDays: 7 };
  }

  await purgeExpiredProjectFiles();

  const { client, bucket } = getClient();
  const response = await client.send(
    new ListObjectsV2Command({
      Bucket: bucket,
      Prefix: PROJECT_STORAGE_PREFIX,
    }),
  );

  const now = Date.now();
  const items: ProjectStorageItem[] = [];

  for (const entry of response.Contents || []) {
    const key = entry.Key;
    if (!key || key.endsWith("/")) continue;
    const parsed = parseProjectKey(key);
    if (!parsed) continue;
    if (options?.projectId && parsed.projectId !== options.projectId) continue;

    const name = parsed.name;

    let expiresMs = expiryFromMetadata(undefined, entry.LastModified);
    try {
      const head = await client.send(
        new HeadObjectCommand({
          Bucket: bucket,
          Key: key,
        }),
      );
      expiresMs = expiryFromMetadata(head.Metadata, head.LastModified);
    } catch {
      // Keep list fallback.
    }

    const expired = expiresMs <= now;
    if (expired) continue;

    items.push({
      key,
      name,
      size: entry.Size ?? null,
      lastModified: entry.LastModified?.toISOString() ?? null,
      expiresAt: new Date(expiresMs).toISOString(),
      expired: false,
      projectId: parsed.projectId,
    });
  }

  items.sort((a, b) => {
    const projectCmp = (a.projectId || "").localeCompare(b.projectId || "");
    if (projectCmp !== 0) return projectCmp;
    return a.name.localeCompare(b.name);
  });

  return { items, ttlDays: 7 };
}
