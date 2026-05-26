import { AxiosError } from 'axios';

interface BackendErrorBody {
  title?: string;
  detail?: string;
  code?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  override readonly cause: unknown;
  constructor(message: string, status: number, code: string, cause: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.cause = cause;
  }
}

const STATUS_FALLBACK: Record<number, string> = {
  400: 'bad request',
  401: 'unauthorized',
  403: 'forbidden',
  404: 'not found',
  409: 'conflict',
  422: 'validation failed',
  500: 'server error',
  502: 'bad gateway',
  503: 'service unavailable',
  504: 'gateway timeout',
};

export function toApiError(input: unknown): ApiError {
  if (input instanceof AxiosError && input.response) {
    const status = input.response.status;
    const body = (input.response.data ?? {}) as BackendErrorBody;
    const code = body.code ?? `HTTP_${status}`;
    const message = body.detail ?? body.title ?? STATUS_FALLBACK[status] ?? `http ${status}`;
    return new ApiError(message, status, code, input);
  }
  if (input instanceof AxiosError) {
    return new ApiError(input.message || 'network error', 0, 'NETWORK', input);
  }
  if (input instanceof Error) {
    return new ApiError(input.message, 0, 'UNKNOWN', input);
  }
  return new ApiError(String(input), 0, 'UNKNOWN', input);
}
