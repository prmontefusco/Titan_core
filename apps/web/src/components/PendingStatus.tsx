import type { EntityKind } from '../api/entityTypeRequests'
import { ENTITY_KIND_LABELS } from '../entityKinds'

interface Props {
  requestedKind: EntityKind
  requestedAt: string
}

export function PendingStatus({ requestedKind, requestedAt }: Props) {
  return (
    <section>
      <p className="eyebrow">Acesso pendente</p>
      <h2>Solicitação enviada</h2>
      <p>
        Você pediu para ser <strong>{ENTITY_KIND_LABELS[requestedKind]}</strong> em{' '}
        {new Date(requestedAt).toLocaleString('pt-BR')}.
      </p>
      <p>
        Aguarde a aprovação de um administrador da organização piloto. Quando ela for concluída,
        entre novamente para acessar a operação.
      </p>
    </section>
  )
}
