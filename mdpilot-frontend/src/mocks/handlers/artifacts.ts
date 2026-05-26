import { http, HttpResponse } from 'msw';

import { allArtifacts } from '../fixtures';

export const artifactHandlers = [
  http.get('/api/artifacts/:chatId', ({ params }) => {
    const list = allArtifacts.filter((a) => a.chatId === params.chatId);
    return HttpResponse.json(list);
  }),
  http.get('/api/artifacts/:chatId/:kind/:filename', () =>
    HttpResponse.text('mock artifact body', { headers: { 'Content-Type': 'text/plain' } }),
  ),
];
