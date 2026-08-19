import { useEffect, useState } from 'react'
import { useAuth } from 'react-oidc-context'
import { Route, Routes } from 'react-router-dom'
import { apiBaseUrl, organizationId } from './config'
import {
  fetchMyStatus,
  parseEntityKindClaim,
  submitEntityTypeRequest,
  type EntityKind,
  type MyStatusResponse,
} from './api/entityTypeRequests'
import { ENTITY_KIND_LABELS } from './entityKinds'
import { ApplicationShell } from './components/ApplicationShell'
import type { NavigationItem } from './components/Sidebar'
import { AdminQueue } from './components/AdminQueue'
import { EntityTypeSelectionForm } from './components/EntityTypeSelectionForm'
import { PendingStatus } from './components/PendingStatus'
import { AdminDashboard } from './pages/AdminDashboard'
import { AnimalSearch } from './pages/AnimalSearch'
import { AnimalDetail } from './pages/AnimalDetail'
import { AnimalTimeline } from './pages/AnimalTimeline'
import { TreatmentForm } from './pages/TreatmentForm'
import { AnimalEligibility } from './pages/AnimalEligibility'
import { MarketMatrix } from './pages/MarketMatrix'
import { CommercialExplanation } from './pages/CommercialExplanation'
import { LotSearch } from './pages/LotSearch'
import { LotDetail } from './pages/LotDetail'
import { DecisionReview } from './pages/DecisionReview'
import { MarketRuleGovernance } from './pages/MarketRuleGovernance'
import { TerritorialCaptureQa } from './pages/TerritorialCaptureQa'
import titanLogo from './assets/titan-bode.png'

function LoginScreen({ onEnter }: { onEnter: () => void }) {
  return (
    <main className="access-screen">
      <div className="login-split-card">
        <div className="login-banner">
          <div className="login-banner-content">
            <header className="brand-hero">
              <img src={titanLogo} alt="Titan" width={56} height={56} className="brand-logo-img" />
              <div>
                <h1>Titan</h1>
                <p className="brand-subtitle">Livestock</p>
              </div>
            </header>
            <div className="banner-text">
              <h2>Bem-vindo ao Titan!</h2>
              <p>
                Plataforma de gestão, rastreabilidade individual e conformidade sanitária para a
                pecuária profissional.
              </p>
            </div>
            <ul className="banner-features">
              <li>
                <span className="feature-dot">✓</span> Rastreabilidade vitalícia de bovinos e caprinos
              </li>
              <li>
                <span className="feature-dot">✓</span> Matriz de elegibilidade e conformidade comercial
              </li>
              <li>
                <span className="feature-dot">✓</span> Governança de regras e auditoria territorial
              </li>
            </ul>
          </div>
        </div>
        <section className="login-panel" aria-labelledby="access-title">
          <div className="login-panel-content">
            <p className="eyebrow">Acesso Seguro</p>
            <h2 id="access-title">Entre na sua conta</h2>
            <p className="access-description">
              Conecte-se para gerenciar o rebanho, inventário de lotes e verificar conformidade sanitária.
            </p>
            <div className="login-actions">
              <button type="button" className="btn-primary-pill" onClick={onEnter}>
                Entrar com minha conta
              </button>
              <button type="button" className="btn-secondary-pill" onClick={onEnter}>
                Criar uma conta
              </button>
            </div>
            <p className="access-help">
              Autenticação segura via provedor OIDC da sua organização. Novos acessos podem exigir aprovação de um administrador.
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}

function StatusConteudo({
  status,
  accessToken,
  registrationKind,
  userProfile,
  onSignOut,
  onPedidoEnviado,
}: {
  status: MyStatusResponse
  accessToken: string
  registrationKind: EntityKind | undefined
  userProfile: { preferred_username?: string; name?: string; sub?: string; email?: string }
  onSignOut: () => void
  onPedidoEnviado: () => void
}) {
  const options = { baseUrl: apiBaseUrl, accessToken, organizationId }

  if (status.has_membership) {
    const aprovado = status.requests.find((pedido) => pedido.status === 'APROVADA')
    const kind: EntityKind = aprovado?.requested_kind ?? 'ADMIN'

    const navigationItems: NavigationItem[] = [
      { path: '/', label: 'Dashboard', icon: '📊' },
      { path: '/animals', label: 'Animais', icon: '🐄' },
      { path: '/lots', label: 'Lotes', icon: '📦' },
      { path: '/admin', label: 'Fila de aprovação', icon: '📋' },
      { path: '/rule-governance', label: 'Regras de mercado', icon: '⚖️' },
      { path: '/territorial-capture-qa', label: 'QA territorial', icon: '🗺️' },
    ]

    const userMenuProps = {
      displayName: userProfile.preferred_username ?? userProfile.name ?? userProfile.sub ?? 'Administrador',
      email: userProfile.email,
      subject: userProfile.sub ?? '',
      organizationId,
      roleLabel: ENTITY_KIND_LABELS[kind],
      onSignOut,
    }

    return (
      <ApplicationShell
        organizationId={organizationId}
        userMenuProps={userMenuProps}
        navigationItems={navigationItems}
      >
        <Routes>
          <Route path="/" element={<AdminDashboard {...options} />} />
          <Route path="/animals" element={<AnimalSearch {...options} />} />
          <Route path="/animals/:animalId" element={<AnimalDetail {...options} />} />
          <Route path="/animals/:animalId/timeline" element={<AnimalTimeline {...options} />} />
          <Route
            path="/animals/:animalId/treatments/new"
            element={<TreatmentForm {...options} />}
          />
          <Route
            path="/animals/:animalId/eligibility"
            element={<AnimalEligibility {...options} />}
          />
          <Route path="/animals/:animalId/market-matrix" element={<MarketMatrix {...options} />} />
          <Route
            path="/animals/:animalId/commercial-explanation"
            element={<CommercialExplanation {...options} />}
          />
          <Route path="/lots" element={<LotSearch {...options} />} />
          <Route path="/lots/:lotId" element={<LotDetail {...options} />} />
          <Route
            path="/lots/:lotId/commercial-explanation"
            element={<CommercialExplanation {...options} />}
          />
          <Route path="/review/:proposalId" element={<DecisionReview {...options} />} />
          <Route path="/rule-governance" element={<MarketRuleGovernance {...options} />} />
          <Route path="/territorial-capture-qa" element={<TerritorialCaptureQa {...options} />} />
          <Route path="/admin" element={<AdminQueue {...options} />} />
        </Routes>
      </ApplicationShell>
    )
  }

  const pendente = status.requests.find((pedido) => pedido.status === 'PENDENTE')
  if (pendente) {
    return (
      <main className="pre-membership-container">
        <PendingStatus requestedKind={pendente.requested_kind} requestedAt={pendente.requested_at} />
        <button type="button" className="btn-secondary-pill logout-pre-btn" onClick={onSignOut}>
          Sair da conta
        </button>
      </main>
    )
  }

  const ultimaNegada = status.requests.find((pedido) => pedido.status === 'NEGADA')
  return (
    <main className="pre-membership-container">
      <EntityTypeSelectionForm
        negatedReason={ultimaNegada?.decision_reason}
        defaultKind={registrationKind}
        onSubmit={async (kind) => {
          await submitEntityTypeRequest(options, kind)
          onPedidoEnviado()
        }}
      />
      <button type="button" className="btn-secondary-pill logout-pre-btn" onClick={onSignOut}>
        Sair da conta
      </button>
    </main>
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
    return (
      <main className="access-screen">
        <div className="status-loading-box">
          <p role="status">Verificando sua sessão…</p>
        </div>
      </main>
    )
  }

  if (auth.error) {
    return (
      <main className="access-screen">
        <div className="login-split-card">
          <div className="login-banner">
            <div className="login-banner-content">
              <header className="brand-hero">
                <img src={titanLogo} alt="Titan" width={56} height={56} className="brand-logo-img" />
                <div>
                  <h1>Titan</h1>
                  <p className="brand-subtitle">Livestock</p>
                </div>
              </header>
              <div className="banner-text">
                <h2>Acesso ao Sistema</h2>
                <p>Autenticação segura para operadores, veterinários e gestores da cadeia pecuária.</p>
              </div>
            </div>
          </div>
          <section className="login-panel" aria-labelledby="authentication-error-title">
            <div className="login-panel-content">
              <h2 id="authentication-error-title">Não foi possível concluir o login</h2>
              <div className="error-alert" role="alert">
                <p>{auth.error.message}</p>
              </div>
              <div className="login-actions">
                <button type="button" className="btn-primary-pill" onClick={() => auth.signinRedirect()}>
                  Tentar novamente
                </button>
              </div>
            </div>
          </section>
        </div>
      </main>
    )
  }

  if (!auth.isAuthenticated) {
    return <LoginScreen onEnter={() => auth.signinRedirect()} />
  }

  return (
    <>
      {erroStatus && (
        <main className="access-screen">
          <section className="status-error" role="alert">
            <h2>Falha ao verificar permissões</h2>
            <p>{erroStatus}</p>
            <p>
              Confirme se você recebeu acesso à organização piloto e tente novamente. A seleção de
              outra Organization ainda não está disponível nesta versão.
            </p>
            <div className="error-actions">
              <button type="button" className="btn-primary-pill" onClick={carregarStatus}>
                Tentar novamente
              </button>
              <button type="button" className="btn-secondary-pill" onClick={() => auth.signoutRedirect()}>
                Sair
              </button>
            </div>
          </section>
        </main>
      )}
      {!erroStatus && !meuStatus && (
        <main className="access-screen">
          <div className="status-loading-box">
            <p>Carregando seu status operacional…</p>
          </div>
        </main>
      )}
      {!erroStatus && meuStatus && accessToken && (
        <StatusConteudo
          status={meuStatus}
          accessToken={accessToken}
          registrationKind={parseEntityKindClaim(auth.user?.profile.titan_requested_kind)}
          userProfile={{
            preferred_username: auth.user?.profile.preferred_username,
            name: auth.user?.profile.name,
            sub: auth.user?.profile.sub,
            email: auth.user?.profile.email,
          }}
          onSignOut={() => auth.signoutRedirect()}
          onPedidoEnviado={carregarStatus}
        />
      )}
    </>
  )
}

export default App
