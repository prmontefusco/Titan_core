// Mesmos padrões locais usados por apps/api (ver DEVELOPMENT.md e
// config/keycloak/titan-realm.json) para que `npm run dev` funcione contra a
// stack local sem configuração extra.
export const oidcIssuer =
  import.meta.env.VITE_TITAN_OIDC_ISSUER ?? 'http://localhost:8080/realms/titan'

export const oidcClientId = import.meta.env.VITE_TITAN_OIDC_CLIENT_ID ?? 'titan-web'

export const apiBaseUrl = import.meta.env.VITE_TITAN_API_BASE_URL ?? 'http://127.0.0.1:8000'

// O produto ainda não tem descoberta de múltiplas Organizations (exigiria uma
// consulta cross-organization que a RLS não permite de graça — ver ADR-0003).
// Por ora só existe uma Organization em uso real, e o frontend aponta pra ela
// até essa necessidade aparecer de verdade.
export const organizationId =
  import.meta.env.VITE_TITAN_ORGANIZATION_ID ?? '9ddb2b8b-2fed-48d4-b5ed-a0d308994dbc'
