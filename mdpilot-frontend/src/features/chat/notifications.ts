/**
 * notifyAgentComplete — send browser notification when agent completes.
 */

export function notifyAgentComplete(message: string): void {
  // Check if Notification API is available
  if (typeof Notification === 'undefined') {
    return;
  }

  // Only show notification if permission is granted
  if (Notification.permission !== 'granted') {
    return;
  }

  new Notification('Agent Complete', {
    body: message,
  });
}
