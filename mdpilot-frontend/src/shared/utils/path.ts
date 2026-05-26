export type ArtifactKind = 'pdb' | 'dcd' | 'csv' | 'png' | 'log' | 'report';

const UNSAFE = /\.\.|^\/|\\/;

function assertSafeSegment(segment: string, label: string): void {
  if (UNSAFE.test(segment) || segment === '') {
    throw new Error(`${label}: path traversal or empty segment rejected`);
  }
}
export function artifactDownloadUrl(
  chatId: string,
  kind: ArtifactKind,
  filename: string,
): string {
  assertSafeSegment(chatId, 'chatId');
  assertSafeSegment(filename, 'filename');
  return `/api/artifacts/${encodeURIComponent(chatId)}/${kind}/${encodeURIComponent(filename)}`;
}

export function artifactPreviewUrl(
  chatId: string,
  kind: ArtifactKind,
  filename: string,
): string {
  return `${artifactDownloadUrl(chatId, kind, filename)}?preview=1`;
}
