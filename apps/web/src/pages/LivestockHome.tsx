import { Link } from 'react-router-dom'
import type { EntityKind } from '../api/entityTypeRequests'
import { ENTITY_KIND_LABELS } from '../entityKinds'

interface Props {
  kind: EntityKind
  organizationId: string
}

// Home real do Livestock (Tela S1, LIV-PROD-01). Substitui o painel-stub
// anterior: mostra a organização ativa e os atalhos que já têm funcionalidade
// de verdade por trás — o resto fica listado como "ainda não disponível" em
// vez de fingir que existe (AGENTS.md — limitações explícitas antes de
// atalhos otimistas de UX).
export function LivestockHome({ kind, organizationId }: Props) {
  return (
    <section>
      <h2>Livestock — {ENTITY_KIND_LABELS[kind]}</h2>
      <p>
        Organização ativa: <code>{organizationId}</code>
      </p>

      <h3>Disponível agora</h3>
      <ul>
        <li>
          <Link to="/animals">Buscar animal</Link> — encontrar um animal e ver identidade,
          histórico e timeline.
        </li>
        <li>
          <Link to="/admin">Fila de aprovação</Link> — decidir pedidos de tipo de entidade
          pendentes.
        </li>
      </ul>

      <h3>Ainda não disponível nesta versão</h3>
      <ul>
        <li>Registro de tratamento</li>
        <li>Elegibilidade e matriz de mercado</li>
        <li>Visão comercial do lote</li>
        <li>Revisão humana de decisões</li>
      </ul>
    </section>
  )
}
