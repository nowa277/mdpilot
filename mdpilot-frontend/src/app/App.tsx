import { RouterProvider } from 'react-router-dom';

import { BackgroundEffects } from '@/components/background';

import { HealthGate } from './HealthGate';
import { Providers } from './providers';
import { router } from './router';

export function App() {
  return (
    <Providers>
      {/* 背景效果层 */}
      <BackgroundEffects />
      <HealthGate>
      <RouterProvider router={router} />
      </HealthGate>
    </Providers>
  );
}
