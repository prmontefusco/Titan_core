import type { EntityKind } from '../api/entityTypeRequests'
import { ENTITY_KIND_LABELS } from '../entityKinds'

interface Props {
  requestedKind: EntityKind
  requestedAt: string
}

export function PendingStatus({ requestedKind, requestedAt }: Props) {
  return (
    <section>
      <h2>Pedido enviado</h2>
      <p>
        Você pediu para ser <strong>{ENTITY_KIND_LABELS[requestedKind]}</strong> em{' '}
        {new Date(requestedAt).toLocaleString('pt-BR')}.
      </p>
      <p>Aguardando aprovação de um administrador da Organization.</p>
    </section>
  )
}
