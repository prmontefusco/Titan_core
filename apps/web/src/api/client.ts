export interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
  renewAccessToken?: () => Promise<string | null>
}

type ErrorFactory = (response: Response) => Promise<Error>

function buildHeaders(
  accessToken: string,
  organizationId: string,
  init: RequestInit,
): Record<string, string> {
  return {
    Authorization: `Bearer ${accessToken}`,
    'X-Titan-Organization-Id': organizationId,
    ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    ...(init.headers as Record<string, string> | undefined),
  }
}

async function fetchWithToken(
  path: string,
  { baseUrl, organizationId }: RequestOptions,
  accessToken: string,
  init: RequestInit,
): Promise<Response> {
  return fetch(`${baseUrl}${path}`, {
    ...init,
    headers: buildHeaders(accessToken, organizationId, init),
  })
}

export async function titanRequest<T>(
  path: string,
  options: RequestOptions,
  init: RequestInit = {},
  createError: ErrorFactory,
): Promise<T> {
  let response = await fetchWithToken(path, options, options.accessToken, init)

  if (response.status === 401 && options.renewAccessToken) {
    const refreshedToken = await options.renewAccessToken().catch(() => null)
    if (refreshedToken) {
      response = await fetchWithToken(path, options, refreshedToken, init)
    }
  }

  if (!response.ok) {
    throw await createError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
