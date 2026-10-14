import { useMemo, useState, type FormEvent } from 'react'
import {
  CommercialPassportApiError,
  downloadVerificationBundle,
  fetchPropertyCommercialPassport,
  issuePropertyCommercialPassport,
  type CommercialPassportEvidenceNeed,
  type CommercialPassportGap,
  type CommercialPassportOpportunityAssessment,
  type CommercialPassportResponse,
} from '../api/commercialPassport'
import { ErrorState } from '../components/AsyncStates'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
  renewAccessToken?: () => Promise<string | null>
}

function utcLocalValue(date: Date): string {
  return date.toISOString().slice(0, 16)
}

function toUtcIso(localValue: string): string {
  return new Date(localValue).toISOString()
}

export function CommercialPassport(options: Options) {
  const agora = useMemo(() => new Date(), [])
  const [propertyId, setPropertyId] = useState('')
  const [referenceTime, setReferenceTime] = useState(utcLocalValue(agora))
  const [knowledgeCutoff, setKnowledgeCutoff] = useState(utcLocalValue(agora))
  const [passport, setPassport] = useState<CommercialPassportResponse | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [emissao, setEmissao] = useState<string | null>(null)
  const [emitindo, setEmitindo] = useState(false)

  const consultar = async (evento: FormEvent) => {
    evento.preventDefault()
    setExecutando(true)
    setErro(null)
    setPassport(null)
    try {
      const resposta = await fetchPropertyCommercialPassport(options, {
        propertyId: propertyId.trim(),
        referenceTime: toUtcIso(referenceTime),
        knowledgeCutoff: toUtcIso(knowledgeCutoff),
      })
      setPassport(resposta)
    } catch (error) {
      if (error instanceof CommercialPassportApiError && error.status === 503) {
        setErro('Commercial Passport ainda não está habilitado neste ambiente.')
      } else if (error instanceof CommercialPassportApiError && error.status === 403) {
        setErro('A Organization atual não possui permissão para consultar este passaporte.')
      } else if (error instanceof CommercialPassportApiError && error.status === 404) {
        setErro('Passaporte comercial não disponível nesta versão.')
      } else {
        setErro(
          error instanceof Error
            ? error.message
            : 'Falha ao consultar o Commercial Passport da propriedade.',
        )
      }
    } finally {
      setExecutando(false)
    }
  }

  const emitirEBaixar = async () => {
    setEmitindo(true)
    setErro(null)
    setEmissao(null)
    const idempotencyKey = crypto.randomUUID()
    try {
      const issued = await issuePropertyCommercialPassport(options, {
        propertyId: propertyId.trim(),
        referenceTime: toUtcIso(referenceTime),
        knowledgeCutoff: toUtcIso(knowledgeCutoff),
        idempotencyKey,
      })
      const bundle = await downloadVerificationBundle(options, issued.verification_bundle_id)
      const url = URL.createObjectURL(
        new Blob([bundle.bytes.buffer as ArrayBuffer], { type: bundle.contentType }),
      )
      const link = document.createElement('a')
      link.href = url
      link.download = `commercial-passport-${issued.verification_bundle_id}.json`
      link.click()
      URL.revokeObjectURL(url)
      setEmissao(`Bundle ${issued.verification_bundle_id} emitido e baixado.`)
    } catch (error) {
      if (error instanceof CommercialPassportApiError && error.status === 503) {
        setErro('A emissão formal ainda não está habilitada neste ambiente.')
      } else if (error instanceof CommercialPassportApiError && error.status === 403) {
        setErro('A Organization atual não possui permissão para emitir ou recuperar este bundle.')
      } else if (error instanceof CommercialPassportApiError && error.status === 409) {
        setErro('A emissão não pôde ser concluída porque o material autoritativo está em conflito.')
      } else {
        setErro(error instanceof Error ? error.message : 'Falha ao emitir o Commercial Passport.')
      }
    } finally {
      setEmitindo(false)
    }
  }

  return (
    <section className="detail-page commercial-passport-page">
      <header className="detail-page-header">
        <div className="detail-header-main">
          <div>
            <p className="detail-eyebrow">Commercial Passport</p>
            <h1 className="detail-title">Passaporte comercial</h1>
            <p className="detail-subtitle">
              Projeção de prontidão comercial da propriedade, separando requisitos da
              propriedade e elegibilidade da população.
            </p>
          </div>
          <span className="detail-status-chip">property-first</span>
        </div>
      </header>

      <form className="market-supply-form" onSubmit={consultar}>
        <fieldset>
          <legend>Propriedade</legend>
          <label htmlFor="commercial-passport-property-id">Property ID</label>
          <input
            id="commercial-passport-property-id"
            type="text"
            value={propertyId}
            onChange={(evento) => setPropertyId(evento.target.value)}
            required
          />
        </fieldset>

        <fieldset>
          <legend>Temporalidade</legend>
          <label htmlFor="commercial-passport-reference-time">Reference time</label>
          <input
            id="commercial-passport-reference-time"
            type="datetime-local"
            value={referenceTime}
            onChange={(evento) => setReferenceTime(evento.target.value)}
            required
          />

          <label htmlFor="commercial-passport-knowledge-cutoff">Knowledge cutoff</label>
          <input
            id="commercial-passport-knowledge-cutoff"
            type="datetime-local"
            value={knowledgeCutoff}
            onChange={(evento) => setKnowledgeCutoff(evento.target.value)}
            required
          />
        </fieldset>

        <div className="market-supply-actions">
          <button type="submit" disabled={executando}>
            {executando ? 'Consultando...' : 'Consultar passaporte'}
          </button>
          <button type="button" disabled={executando || emitindo || !propertyId.trim()} onClick={emitirEBaixar}>
            {emitindo ? 'Emitindo...' : 'Emitir e baixar bundle'}
          </button>
        </div>
      </form>

      {erro && <ErrorState tone="compact" message={erro} />}
      {emissao && <p role="status">{emissao}</p>}

      {passport && <CommercialPassportProjection passport={passport} />}
    </section>
  )
}

function CommercialPassportProjection({ passport }: { passport: CommercialPassportResponse }) {
  return (
    <section className="market-supply-results">
      <h2>Oportunidades comerciais</h2>
      <dl className="market-supply-metrics">
        <div className="market-supply-metric">
          <dt>Reference time</dt>
          <dd>{new Date(passport.reference_time).toLocaleDateString()}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Knowledge cutoff</dt>
          <dd>{new Date(passport.knowledge_cutoff).toLocaleDateString()}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Oportunidades</dt>
          <dd>{passport.opportunities.length}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Lacunas acionáveis</dt>
          <dd>{passport.gap_analysis.gap_count}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Necessidades de evidência</dt>
          <dd>{passport.evidence_vault.missing_count}</dd>
        </div>
      </dl>

      <CommercialGapAnalysisSummary passport={passport} />
      <CommercialEvidenceVaultSummary passport={passport} />

      <div className="commercial-passport-opportunity-list">
        {passport.opportunities.map((assessment) => (
          <CommercialOpportunityCard
            key={assessment.opportunity.code}
            assessment={assessment}
          />
        ))}
      </div>
    </section>
  )
}

function CommercialEvidenceVaultSummary({ passport }: { passport: CommercialPassportResponse }) {
  const needs = passport.evidence_vault.needs
  const statusEntries = Object.entries(passport.evidence_vault.status_counts).filter(
    ([, count]) => count > 0,
  )

  return (
    <section className="market-supply-card">
      <h3>Cofre de evidências</h3>
      <p>
        Índice operacional do que precisa estar documentado para reduzir lacunas do
        passaporte. Não armazena arquivos, não substitui Evidence do Core e não valida
        admissibilidade.
      </p>

      {statusEntries.length > 0 && (
        <dl className="market-supply-metrics">
          {statusEntries.map(([status, count]) => (
            <div className="market-supply-metric" key={status}>
              <dt>{status}</dt>
              <dd>{count}</dd>
            </div>
          ))}
        </dl>
      )}

      {needs.length > 0 ? (
        <ul>
          {needs.map((need) => (
            <CommercialEvidenceNeedItem need={need} key={need.need_code} />
          ))}
        </ul>
      ) : (
        <p>Nenhuma necessidade de evidência foi derivada para esta projeção.</p>
      )}

      <details>
        <summary>Limitações do cofre</summary>
        <ul>
          {passport.evidence_vault.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </details>
    </section>
  )
}

function CommercialEvidenceNeedItem({ need }: { need: CommercialPassportEvidenceNeed }) {
  return (
    <li>
      <strong>{need.evidence_type}</strong> — {need.status} em {need.opportunity_name}.
      <br />
      Cobertura esperada: {need.expected_coverage}
      <br />
      Próxima ação: {need.recommended_action}
      {need.referenced_evidence_ids.length > 0 && (
        <>
          <br />
          Evidências referenciadas: {need.referenced_evidence_ids.join(', ')}
        </>
      )}
    </li>
  )
}

function CommercialGapAnalysisSummary({ passport }: { passport: CommercialPassportResponse }) {
  const gaps = passport.gap_analysis.gaps
  const categoryEntries = Object.entries(passport.gap_analysis.category_counts).filter(
    ([, count]) => count > 0,
  )

  return (
    <section className="market-supply-card">
      <h3>Lacunas e próximas ações</h3>
      <p>
        Recomendações operacionais derivadas do passaporte dinâmico. Não são decisão
        regulatória, garantia comercial ou substituto de Policy/Evaluation/Decision.
      </p>

      {categoryEntries.length > 0 ? (
        <dl className="market-supply-metrics">
          {categoryEntries.map(([category, count]) => (
            <div className="market-supply-metric" key={category}>
              <dt>{category}</dt>
              <dd>{count}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>Nenhuma lacuna acionável foi derivada para esta projeção.</p>
      )}

      {gaps.length > 0 && (
        <ul>
          {gaps.map((gap) => (
            <CommercialGapItem gap={gap} key={`${gap.opportunity_code}:${gap.gap_code}`} />
          ))}
        </ul>
      )}

      <details>
        <summary>Limitações da análise</summary>
        <ul>
          {passport.gap_analysis.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </details>
    </section>
  )
}

function CommercialGapItem({ gap }: { gap: CommercialPassportGap }) {
  return (
    <li>
      <strong>{gap.label}</strong> — {gap.category} em {gap.opportunity_name}.
      {gap.affected_count !== null && <> Afeta {gap.affected_count} item(ns).</>}
      <br />
      Próxima ação: {gap.recommended_action.description}
    </li>
  )
}

function CommercialOpportunityCard({
  assessment,
}: {
  assessment: CommercialPassportOpportunityAssessment
}) {
  const breakdown = assessment.property_readiness.breakdown
  const population = assessment.population_eligibility

  return (
    <article className="commercial-passport-opportunity-card">
      <header>
        <div>
          <h3>{assessment.opportunity.name}</h3>
          <p>{assessment.opportunity.kind}</p>
        </div>
        <span>{assessment.property_readiness.interpretation}</span>
      </header>

      <dl className="market-supply-metrics">
        <div className="market-supply-metric">
          <dt>Satisfeitos</dt>
          <dd>{breakdown.satisfied}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Ausentes</dt>
          <dd>{breakdown.missing}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Desconhecidos</dt>
          <dd>{breakdown.unknown}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Bloqueadores</dt>
          <dd>{breakdown.blocked}</dd>
        </div>
      </dl>

      <div className="market-supply-result-columns">
        <section>
          <h4>Requisitos</h4>
          <ul>
            {assessment.property_readiness.requirements.map((requirement) => (
              <li key={requirement.requirement_code}>
                {requirement.label}: {requirement.status}
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h4>População</h4>
          {population ? (
            <>
              <ul>
                {Object.entries(population.counts_by_status).map(([status, count]) => (
                  <li key={status}>
                    {status}: {count}
                  </li>
                ))}
              </ul>
              <CommercialPopulationTrace assessment={assessment} />
            </>
          ) : (
            <p>Resumo populacional não informado.</p>
          )}
        </section>
      </div>
    </article>
  )
}

function CommercialPopulationTrace({
  assessment,
}: {
  assessment: CommercialPassportOpportunityAssessment
}) {
  const population = assessment.population_eligibility
  if (!population) {
    return null
  }

  const windowStart = population.commercial_window.start
  const windowEnd = population.commercial_window.end

  return (
    <details>
      <summary>Rastreio da população</summary>
      <p>
        Resumo agregado usado para validar a origem temporal da população. Não expõe
        IDs individuais de animais.
      </p>
      <dl className="market-supply-metrics">
        <div className="market-supply-metric">
          <dt>Total avaliado</dt>
          <dd>{population.total_count}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Fonte do relatório</dt>
          <dd>{population.source_report_reference || 'não informada'}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Digest da população</dt>
          <dd>{population.population_snapshot_digest || 'não informado'}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Digest dos critérios</dt>
          <dd>{population.selection_criteria_digest || 'não informado'}</dd>
        </div>
        <div className="market-supply-metric">
          <dt>Janela comercial</dt>
          <dd>
            {windowStart && windowEnd
              ? `${new Date(windowStart).toLocaleDateString()} — ${new Date(
                  windowEnd,
                ).toLocaleDateString()}`
              : 'não informada'}
          </dd>
        </div>
      </dl>

      {population.limitations.length > 0 && (
        <ul>
          {population.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      )}
    </details>
  )
}
