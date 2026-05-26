export const USER_ID_KEY = 'mdpilot.user_id';

const VALID = /^u-[a-z0-9-]{8,}$/;

function generate(): string {
  const rand =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  return `u-${rand.replace(/[^a-z0-9-]/gi, '').toLowerCase().slice(0, 16)}`;
}

export function ensureUserId(): string {
  const existing = localStorage.getItem(USER_ID_KEY);
  if (existing && VALID.test(existing)) return existing;
  const id = generate();
  localStorage.setItem(USER_ID_KEY, id);
  return id;
}
