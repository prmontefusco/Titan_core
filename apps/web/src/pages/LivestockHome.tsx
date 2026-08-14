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
          Registrar tratamento — a partir do detalhe de um animal encontrado na busca.
        </li>
        <li>
          Elegibilidade e análise de mercado — a partir do detalhe de um animal encontrado
          na busca.
        </li>
        <li>
          <Link to="/lots">Buscar lote</Link> — analisar a posição comercial de um grupo de
          animais.
        </li>
        <li>
          <Link to="/admin">Fila de aprovação</Link> — decidir pedidos de tipo de entidade
          pendentes.
        </li>
        <li>
          Revisão humana de decisões — a partir do aviso de revisão necessária em qualquer
          execução de elegibilidade, mercado ou explicação comercial.
        </li>
        <li>
          <Link to="/rule-governance">Regras de mercado</Link> — publicar política e regra
          governada a partir de um modelo já classificado (NR-5).
        </li>
        <li>
          <Link to="/territorial-capture-qa">QA territorial sintético</Link> — criar dados
          artificiais e conferir a captura territorial sem fonte real nem conclusão normativa.
        </li>
      </ul>
    </section>
  )
}
