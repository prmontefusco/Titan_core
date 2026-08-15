import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  EntityTypeRequestApiError,
  listPendingRequests,
  type EntityTypeRequestSummary,
} from '../api/entityTypeRequests'
import { EmptyState, ErrorState, LoadingState, UnauthorizedState } from '../components/AsyncStates'
import { ENTITY_KIND_LABELS } from '../entityKinds'

interface Props {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export function AdminDashboard({ baseUrl, accessToken, organizationId }: Props) {
  const [pendentes, setPendentes] = useState<EntityTypeRequestSummary[] | null>(null)
  const [semPermissao, setSemPermissao] = useState(false)
  const [erroFila, setErroFila] = useState<string | null>(null)

  const options = { baseUrl, accessToken, organizationId }

  useEffect(() => {
    setErroFila(null)
    listPendingRequests(options)
      .then((lista) => {
        setPendentes(lista)
        setSemPermissao(false)
      })
      .catch((err: unknown) => {
        if (err instanceof EntityTypeRequestApiError && err.status === 403) {
          setSemPermissao(true)
          return
        }
        setErroFila(err instanceof Error ? err.message : 'Falha ao consultar a fila de pedidos.')
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, accessToken, organizationId])

  return (
    <div className="admin-dashboard">
      <header className="dashboard-header">
        <div>
          <div className="dashboard-eyebrow">Capacidades administrativas disponíveis</div>
          <h1 className="dashboard-title">Visão geral de acessos</h1>
          <p className="dashboard-subtitle">
            Esta área mostra somente solicitações de acesso que a Organization atual permite consultar.
          </p>
        </div>
      </header>

      <section className="dashboard-grid" aria-label="Itens que exigem atenção">
        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-icon" aria-hidden="true">📋</span>
            <div className="card-title-group">
              <h2 className="card-title">Solicitações de acesso</h2>
              <span className="card-subtitle">Única fila administrativa disponível neste momento</span>
            </div>
          </div>

          <div className="card-body">
            {semPermissao && (
              <UnauthorizedState
                tone="compact"
                message="Não autorizado a consultar solicitações de acesso nesta Organization."
              />
            )}
            {erroFila && (
              <ErrorState tone="compact" message={erroFila} />
            )}
            {pendentes === null && !semPermissao && !erroFila && (
              <LoadingState tone="compact" message="Consultando solicitações pendentes…" />
            )}
            {pendentes !== null && !semPermissao && !erroFila && (
              <div className="pending-queue-summary">
                <div className="metric-highlight">
                  <span className="metric-number">{pendentes.length}</span>
                  <span className="metric-desc">
                    {pendentes.length === 1 ? 'pedido pendente' : 'pedidos pendentes'}
                  </span>
                </div>

                {pendentes.length > 0 ? (
                  <ul className="pending-recent-list">
                    {pendentes.slice(0, 3).map((p) => (
                      <li key={p.request_id} className="pending-item">
                        <span className="pending-kind">{ENTITY_KIND_LABELS[p.requested_kind]}</span>
                        <span className="pending-date">
                          {new Date(p.requested_at).toLocaleDateString('pt-BR')}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    tone="compact"
                    message="Nenhuma solicitação aguardando decisão no momento."
                  />
                )}
              </div>
            )}
          </div>

          <div className="card-footer">
            <Link to="/admin" className="card-btn-action">
              Gerenciar Fila de Acessos →
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
