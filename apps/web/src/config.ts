// Mesmos padrões locais usados por apps/api (ver DEVELOPMENT.md e
// config/keycloak/titan-realm.json) para que `npm run dev` funcione contra a
// stack local sem configuração extra.
export const oidcIssuer =
  import.meta.env.VITE_TITAN_OIDC_ISSUER ?? 'http://localhost:8080/realms/titan'

export const oidcClientId = import.meta.env.VITE_TITAN_OIDC_CLIENT_ID ?? 'titan-web'

export const apiBaseUrl = import.meta.env.VITE_TITAN_API_BASE_URL ?? 'http://127.0.0.1:8000'
