import { useEffect, useState } from 'react'
import {
  EntityTypeRequestApiError,
  approveRequest,
  denyRequest,
  listPendingRequests,
  type EntityTypeRequestSummary,
} from '../api/entityTypeRequests'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  UnauthorizedState,
} from './AsyncStates'
import { ENTITY_KIND_LABELS } from '../entityKinds'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export function AdminQueue({ baseUrl, accessToken, organizationId }: Options) {
  const [pendentes, setPendentes] = useState<EntityTypeRequestSummary[] | null>(null)
  const [semPermissao, setSemPermissao] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const options = { baseUrl, accessToken, organizationId }

  const recarregar = () => {
    setErro(null)
    listPendingRequests(options)
      .then((lista) => {
        setPendentes(lista)
        setSemPermissao(false)
      })
      .catch((error: unknown) => {
        if (error instanceof EntityTypeRequestApiError && error.status === 403) {
          setSemPermissao(true)
          return
        }
        setErro(error instanceof Error ? error.message : 'Falha ao carregar a fila.')
      })
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(recarregar, [organizationId, accessToken])

  if (semPermissao) {
    return (
      <UnauthorizedState
        message="Você não tem permissão para administrar pedidos nesta Organization."
      />
    )
  }
  if (erro) {
    return <ErrorState message={erro} />
  }
  if (pendentes === null) {
    return <LoadingState message="Carregando..." />
  }
  if (pendentes.length === 0) {
    return <EmptyState message="Nenhum pedido pendente." />
  }

  return (
    <ul>
      {pendentes.map((pedido) => (
        <PedidoPendente key={pedido.request_id} pedido={pedido} options={options} onDecidido={recarregar} />
      ))}
    </ul>
  )
}

function PedidoPendente({
  pedido,
  options,
  onDecidido,
}: {
  pedido: EntityTypeRequestSummary
  options: Options
  onDecidido: () => void
}) {
  const [processando, setProcessando] = useState(false)

  const aprovar = async () => {
    setProcessando(true)
    try {
      await approveRequest(options, pedido.request_id)
      onDecidido()
    } finally {
      setProcessando(false)
    }
  }

  const negar = async () => {
    const motivo = window.prompt('Motivo da negação:')
    if (!motivo) return
    setProcessando(true)
    try {
      await denyRequest(options, pedido.request_id, motivo)
      onDecidido()
    } finally {
      setProcessando(false)
    }
  }

  return (
    <li>
      {ENTITY_KIND_LABELS[pedido.requested_kind]} — pedido em{' '}
      {new Date(pedido.requested_at).toLocaleString('pt-BR')}
      {' '}
      <button type="button" onClick={aprovar} disabled={processando}>
        Aprovar
      </button>{' '}
      <button type="button" onClick={negar} disabled={processando}>
        Negar
      </button>
    </li>
  )
}
