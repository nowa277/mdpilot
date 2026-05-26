import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { notifyAgentComplete } from './notifications';

interface GlobalWithNotification {
  Notification?: typeof Notification;
}

describe('notifyAgentComplete', () => {
  let originalNotification: typeof Notification | undefined;

  beforeEach(() => {
    originalNotification = (global as unknown as GlobalWithNotification).Notification;
  });

  afterEach(() => {
    if (originalNotification) {
      (global as unknown as GlobalWithNotification).Notification = originalNotification;
    } else {
      delete (global as unknown as GlobalWithNotification).Notification;
    }
    vi.clearAllMocks();
  });

  it('creates a notification when permission is granted', () => {
    const mockNotification = vi.fn();
    (global as unknown as GlobalWithNotification).Notification = mockNotification as unknown as typeof Notification;
    Object.defineProperty((global as unknown as GlobalWithNotification).Notification, 'permission', {
      value: 'granted',
      writable: true,
      configurable: true,
    });

    notifyAgentComplete('Agent task completed');

    expect(mockNotification).toHaveBeenCalledWith('Agent Complete', {
      body: 'Agent task completed',
      icon: undefined,
    });
  });

  it('does nothing when Notification API is unavailable', () => {
    delete (global as unknown as GlobalWithNotification).Notification;

    expect(() => {
      notifyAgentComplete('Agent task completed');
    }).not.toThrow();
  });

  it('does nothing when permission is denied', () => {
    const mockNotification = vi.fn();
    (global as unknown as GlobalWithNotification).Notification = mockNotification as unknown as typeof Notification;
    Object.defineProperty((global as unknown as GlobalWithNotification).Notification, 'permission', {
      value: 'denied',
      writable: true,
      configurable: true,
    });

    notifyAgentComplete('Agent task completed');

    expect(mockNotification).not.toHaveBeenCalled();
  });

  it('does nothing when permission is default', () => {
    const mockNotification = vi.fn();
    (global as unknown as GlobalWithNotification).Notification = mockNotification as unknown as typeof Notification;
    Object.defineProperty((global as unknown as GlobalWithNotification).Notification, 'permission', {
      value: 'default',
      writable: true,
      configurable: true,
    });

    notifyAgentComplete('Agent task completed');

    expect(mockNotification).not.toHaveBeenCalled();
  });
});
