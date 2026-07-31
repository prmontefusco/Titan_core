import type { ReactNode } from 'react'
import { AuthProvider as OidcAuthProvider } from 'react-oidc-context'
import { WebStorageStateStore } from 'oidc-client-ts'
import { oidcClientId, oidcIssuer } from '../config'

// Authorization Code Flow com PKCE S256 (ADR-0005): react-oidc-context/oidc-client-ts
// implementam PKCE automaticamente para clientes públicos, sem código próprio de
// criptografia. Implicit Flow e Resource Owner Password Credentials permanecem
// proibidos e nunca são configurados aqui.
const oidcConfig = {
  authority: oidcIssuer,
  client_id: oidcClientId,
  redirect_uri: window.location.origin,
  post_logout_redirect_uri: window.location.origin,
  scope: 'openid',
  // Refresh token não é solicitado: o Titan trata apenas Access Tokens de vida
  // curta na API, conforme a fronteira definida pela ADR-0005.
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname)
  },
}

export function AuthProvider({ children }: { children: ReactNode }) {
  return <OidcAuthProvider {...oidcConfig}>{children}</OidcAuthProvider>
}
