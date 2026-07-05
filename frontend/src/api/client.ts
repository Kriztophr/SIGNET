const TOKEN_KEY = "icm.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    detail: string,
  ) {
    super(detail);
  }
}

async function request(path: string, method: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") detail = payload.detail;
      else if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
        detail = payload.detail[0].msg;
      }
    } catch {
      /* non-JSON error body */
    }
    // A dead session anywhere except the login call itself sends us back to login.
    if (response.status === 401 && token && path !== "/auth/login") {
      clearToken();
      window.location.assign("/login");
    }
    throw new ApiError(response.status, detail);
  }
  return response;
}

export async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await request(path, method, body);
  return (await response.json()) as T;
}

export async function apiText(path: string): Promise<string> {
  const response = await request(path, "GET");
  return await response.text();
}
