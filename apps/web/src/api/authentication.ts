export interface AuthenticatedPrincipal {
  issuer: string
  subject: string
  scopes: string[]
}

export class AuthenticatedPrincipalRequestError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`GET /technical/authentication respondeu ${status}`)
    this.status = status
  }
}

// Espelha o contrato de apps/api/main.py::technical_authentication — chamada
// simples usada para provar, na tela, que o Access Token obtido via Keycloak é
// aceito pela API. Não decide Authorization nem substitui um caso de uso real.
export async function fetchAuthenticatedPrincipal(
  baseUrl: string,
  accessToken: string,
): Promise<AuthenticatedPrincipal> {
  const response = await fetch(`${baseUrl}/technical/authentication`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })

  if (!response.ok) {
    throw new AuthenticatedPrincipalRequestError(response.status)
  }

  return (await response.json()) as AuthenticatedPrincipal
}
