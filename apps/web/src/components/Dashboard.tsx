import type { EntityKind } from '../api/entityTypeRequests'
import { ENTITY_KIND_DASHBOARD_DESCRIPTIONS, ENTITY_KIND_LABELS } from '../entityKinds'

interface Props {
  kind: EntityKind
}

// Shell deliberado: cada tipo ganha funcionalidade real em incremento próprio,
// quando existir um caso de uso concreto (AGENTS.md — nada de abstração para
// necessidade futura sem uso atual).
export function Dashboard({ kind }: Props) {
  return (
    <section>
      <h2>Painel — {ENTITY_KIND_LABELS[kind]}</h2>
      <p>{ENTITY_KIND_DASHBOARD_DESCRIPTIONS[kind]}</p>
      <p>
        <em>Ainda não há funcionalidade além deste painel — chega no próximo incremento.</em>
      </p>
    </section>
  )
}
