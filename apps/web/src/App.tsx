import { useEffect, useState } from 'react'
import { useAuth } from 'react-oidc-context'
import { apiBaseUrl } from './config'
import {
  fetchAuthenticatedPrincipal,
  type AuthenticatedPrincipal,
} from './api/authentication'

function App() {
  const auth = useAuth()
  const [principal, setPrincipal] = useState<AuthenticatedPrincipal | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const accessToken = auth.user?.access_token
    if (!accessToken) {
      setPrincipal(null)
      return
    }
    fetchAuthenticatedPrincipal(apiBaseUrl, accessToken)
      .then(setPrincipal)
      .catch(() => setError('A API recusou o Access Token obtido do Keycloak.'))
  }, [auth.user?.access_token])

  if (auth.isLoading) {
    return <p>Carregando…</p>
  }

  if (auth.error) {
    return <p role="alert">Falha na autenticação: {auth.error.message}</p>
  }

  if (!auth.isAuthenticated) {
    return (
      <>
        <h1>Titan</h1>
        <button type="button" onClick={() => auth.signinRedirect()}>
          Entrar
        </button>
      </>
    )
  }

  return (
    <>
      <h1>Titan</h1>
      <p>Autenticado como {auth.user?.profile.preferred_username ?? auth.user?.profile.sub}.</p>
      {error && <p role="alert">{error}</p>}
      {principal && (
        <dl>
          <dt>issuer</dt>
          <dd>{principal.issuer}</dd>
          <dt>subject</dt>
          <dd>{principal.subject}</dd>
          <dt>scopes</dt>
          <dd>{principal.scopes.join(', ')}</dd>
        </dl>
      )}
      <button type="button" onClick={() => auth.signoutRedirect()}>
        Sair
      </button>
    </>
  )
}

export default App
