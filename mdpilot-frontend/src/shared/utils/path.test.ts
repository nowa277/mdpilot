import { describe, expect, it } from 'vitest';

import { artifactDownloadUrl, type ArtifactKind,artifactPreviewUrl } from './path';

describe('artifact URL helpers', () => {
  it('builds download URL with chatId/kind/filename', () => {
    expect(artifactDownloadUrl('chat-123', 'pdb', 'egfr_pred.pdb')).toBe(
      '/api/artifacts/chat-123/pdb/egfr_pred.pdb',
    );
  });

  it('encodes unsafe characters', () => {
    expect(artifactDownloadUrl('chat 1', 'png', 'rmsd plot.png')).toBe(
    '/api/artifacts/chat%201/png/rmsd%20plot.png',
    );
  });

  it('rejects path traversal in filename', () => {
    expect(() => artifactDownloadUrl('chat-1', 'log', '../etc/passwd')).toThrow(
      /path traversal/i,
    );
  });

  it('rejects unsupported kind via type', () => {
    const kind = 'pdb' satisfies ArtifactKind;
    expect(artifactDownloadUrl('c', kind, 'a.pdb')).toBe('/api/artifacts/c/pdb/a.pdb');
  });

  it('preview URL appends ?preview=1', () => {
    expect(artifactPreviewUrl('c1', 'csv', 'rmsd.csv')).toBe(
      '/api/artifacts/c1/csv/rmsd.csv?preview=1',
    );
  });
});
