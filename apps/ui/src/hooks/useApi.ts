// src/hooks/useApi.ts
import { useMemo } from 'react';
import { apiGet, apiPost, apiPut, apiDelete, API_BASE, ApiOptions } from '@/lib/api';

export interface UseApiConfig {
  token?: string;
  tenantId?: string;
  role?: string;
  headers?: Record<string, string>;
}

export function useApi(cfg?: UseApiConfig) {
  const baseOpts: ApiOptions = useMemo(
    () => ({
      token: cfg?.token,
      tenantId: cfg?.tenantId,
      role: cfg?.role,
      headers: cfg?.headers,
    }),
    [cfg?.token, cfg?.tenantId, cfg?.role, cfg?.headers]
  );

  return {
    baseUrl: API_BASE,
    get: <T = unknown>(path: string, opts?: ApiOptions) => apiGet<T>(path, { ...baseOpts, ...opts }),
    post: <T = unknown>(path: string, body?: unknown, opts?: ApiOptions) =>
      apiPost<T>(path, body, { ...baseOpts, ...opts }),
    put: <T = unknown>(path: string, body?: unknown, opts?: ApiOptions) =>
      apiPut<T>(path, body, { ...baseOpts, ...opts }),
    del: <T = unknown>(path: string, opts?: ApiOptions) => apiDelete<T>(path, { ...baseOpts, ...opts }),
  };
}
