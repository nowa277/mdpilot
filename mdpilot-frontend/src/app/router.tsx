import { ChatPane } from '@features/chat';
import { ClusterMonitorPage } from '@features/cluster';
import { createBrowserRouter, Navigate, useParams } from 'react-router-dom';

import { WorkspaceLayout } from './layouts/WorkspaceLayout';

function ChatRoute() {
  const { chatId } = useParams<{ chatId: string }>();
  if (!chatId) return <WorkspaceEmpty />;
  return <ChatPane chatId={chatId} />;
}

function WorkspaceEmpty() {
  return (
    <div className="flex h-full items-center justify-center text-text-2">
    <div className="flex flex-col items-center gap-2">
        <div className="font-display text-2xl">Welcome to MDPilot</div>
        <div className="text-sm text-text-3">Ready for some simulations?</div>
      </div>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <WorkspaceLayout />,
    children: [
      { index: true, element: <Navigate to="/workspace" replace /> },
      { path: 'workspace', element: <WorkspaceEmpty /> },
      { path: 'workspace/c/:chatId', element: <ChatRoute /> },
      { path: 'cluster', element: <ClusterMonitorPage /> },
      { path: '*', element: <PlaceholderPage label="404" /> },
    ],
  },
]);

function PlaceholderPage({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center text-text-2">{label}</div>
  );
}
