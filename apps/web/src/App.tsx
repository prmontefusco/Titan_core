import { useEffect, useState } from 'react'
import { useAuth } from 'react-oidc-context'
import { apiBaseUrl, organizationId } from './config'
import {
  fetchMyStatus,
  parseEntityKindClaim,
  submitEntityTypeRequest,
  type EntityKind,
  type MyStatusResponse,
} from './api/entityTypeRequests'
import { AdminQueue } from './components/AdminQueue'
import { Dashboard } from './components/Dashboard'
import { EntityTypeSelectionForm } from './components/EntityTypeSelectionForm'
import { PendingStatus } from './components/PendingStatus'
import titanLogo from './assets/titan-bode.png'

function Brand() {
  return (
    <header className="brand">
      <img src={titanLogo} alt="Titan" width={64} height={64} />
      <h1>Titan</h1>
    </header>
  )
}

function StatusConteudo({
  status,
  accessToken,
  registrationKind,
  onPedidoEnviado,
}: {
  status: MyStatusResponse
  accessToken: string
  registrationKind: EntityKind | undefined
  onPedidoEnviado: () => void
}) {
  const [aba, setAba] = useState<'dashboard' | 'admin'>('dashboard')
  const options = { baseUrl: apiBaseUrl, accessToken, organizationId }

  if (status.has_membership) {
    // A Organization foi aprovada como um EntityKind concreto, mas quem entrou
    // por apps/bootstrap_admin (não pelo fluxo de pedido) não tem um pedido
    // aprovado para citar -- ADMIN é o fallback honesto para esse caso.
    const aprovado = status.requests.find((pedido) => pedido.status === 'APROVADA')
    const kind: EntityKind = aprovado?.requested_kind ?? 'ADMIN'

    return (
      <>
        <nav>
          <button type="button" onClick={() => setAba('dashboard')} disabled={aba === 'dashboard'}>
            Painel
          </button>{' '}
          <button type="button" onClick={() => setAba('admin')} disabled={aba === 'admin'}>
            Fila de aprovação
          </button>
        </nav>
        {aba === 'dashboard' && <Dashboard kind={kind} />}
        {aba === 'admin' && <AdminQueue {...options} />}
      </>
    )
  }

  const pendente = status.requests.find((pedido) => pedido.status === 'PENDENTE')
  if (pendente) {
    return <PendingStatus requestedKind={pendente.requested_kind} requestedAt={pendente.requested_at} />
  }

  const ultimaNegada = status.requests.find((pedido) => pedido.status === 'NEGADA')
  return (
    <EntityTypeSelectionForm
      negatedReason={ultimaNegada?.decision_reason}
      defaultKind={registrationKind}
      onSubmit={async (kind) => {
        await submitEntityTypeRequest(options, kind)
        onPedidoEnviado()
      }}
    />
  )
}

function App() {
  const auth = useAuth()
  const accessToken = auth.user?.access_token ?? null
  const [meuStatus, setMeuStatus] = useState<MyStatusResponse | null>(null)
  const [erroStatus, setErroStatus] = useState<string | null>(null)

  const carregarStatus = () => {
    if (!accessToken) {
      setMeuStatus(null)
      return
    }
    setErroStatus(null)
    fetchMyStatus({ baseUrl: apiBaseUrl, accessToken, organizationId })
      .then(setMeuStatus)
      .catch(() => setErroStatus('Não foi possível consultar seu status nesta Organization.'))
  }

  useEffect(carregarStatus, [accessToken])

  if (auth.isLoading) {
    return <p>Carregando…</p>
  }

  if (auth.error) {
    return <p role="alert">Falha na autenticação: {auth.error.message}</p>
  }

  if (!auth.isAuthenticated) {
    return (
      <>
        <Brand />
        <button type="button" onClick={() => auth.signinRedirect()}>
          Entrar
        </button>
      </>
    )
  }

  return (
    <>
      <Brand />
      <p>Autenticado como {auth.user?.profile.preferred_username ?? auth.user?.profile.sub}.</p>
      {erroStatus && <p role="alert">{erroStatus}</p>}
      {!erroStatus && !meuStatus && <p>Carregando seu status…</p>}
      {!erroStatus && meuStatus && accessToken && (
        <StatusConteudo
          status={meuStatus}
          accessToken={accessToken}
          registrationKind={parseEntityKindClaim(auth.user?.profile.titan_requested_kind)}
          onPedidoEnviado={carregarStatus}
        />
      )}
      <button type="button" onClick={() => auth.signoutRedirect()}>
        Sair
      </button>
    </>
  )
}

export default App
