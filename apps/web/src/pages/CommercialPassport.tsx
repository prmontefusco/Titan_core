import { useMemo, useState, type FormEvent } from 'react'
import {
  CommercialPassportApiError,
  fetchPropertyCommercialPassport,
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
        </div>
      </form>

      {erro && <ErrorState tone="compact" message={erro} />}

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
      </dl>

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
            <ul>
              {Object.entries(population.counts_by_status).map(([status, count]) => (
                <li key={status}>
                  {status}: {count}
                </li>
              ))}
            </ul>
          ) : (
            <p>Resumo populacional não informado.</p>
          )}
        </section>
      </div>
    </article>
  )
}
