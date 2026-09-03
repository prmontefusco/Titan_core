import { useMemo, useState, type FormEvent } from 'react'
import {
  MarketSupplyApiError,
  assessMarketSupplyAggregate,
  type MarketSupplyAggregateAssessmentResponse,
  type MarketSupplyAggregatePayload,
} from '../api/marketSupply'
import { ErrorState } from '../components/AsyncStates'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

const PURPOSE = 'MARKET_SUPPLY_AGGREGATE_ASSESSMENT'
const SUBJECT_TYPE = 'animal'
const DEFAULT_POLICY_ID = '00000000-0000-0000-0000-000000000000'

function utcLocalValue(date: Date): string {
  return date.toISOString().slice(0, 16)
}

function toUtcIso(localValue: string): string {
  return new Date(localValue).toISOString()
}

function newIdempotencyKey(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `market-supply-${Date.now()}`
}

export function MarketSupplyAggregate(options: Options) {
  const agora = useMemo(() => new Date(), [])
  const daquiTrintaDias = useMemo(
    () => new Date(agora.getTime() + 30 * 24 * 60 * 60 * 1000),
    [agora],
  )

  const [policyId, setPolicyId] = useState(DEFAULT_POLICY_ID)
  const [policyVersion, setPolicyVersion] = useState(1)
  const [quantity, setQuantity] = useState(1)
  const [windowFrom, setWindowFrom] = useState(utcLocalValue(agora))
  const [windowUntil, setWindowUntil] = useState(utcLocalValue(daquiTrintaDias))
  const [referenceTime, setReferenceTime] = useState(utcLocalValue(agora))
  const [knowledgeCutoff, setKnowledgeCutoff] = useState(utcLocalValue(agora))
  const [requiredTags, setRequiredTags] = useState('')
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey)
  const [resultado, setResultado] = useState<MarketSupplyAggregateAssessmentResponse | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const executar = async (evento: FormEvent) => {
    evento.preventDefault()
    setExecutando(true)
    setErro(null)
    setResultado(null)
    try {
      const resposta = await assessMarketSupplyAggregate(options, {
        idempotencyKey,
        request: {
          policy_id: policyId.trim(),
          policy_version: policyVersion,
          purpose: PURPOSE,
          quantity,
          commercial_window: {
            from: toUtcIso(windowFrom),
            until: toUtcIso(windowUntil),
          },
          reference_time: toUtcIso(referenceTime),
          knowledge_cutoff: toUtcIso(knowledgeCutoff),
          candidate_criteria: {
            subject_type: SUBJECT_TYPE,
            required_tags: requiredTags
              .split(',')
              .map((tag) => tag.trim())
              .filter(Boolean),
          },
        },
      })
      setResultado(resposta)
    } catch (error) {
      if (error instanceof MarketSupplyApiError && error.status === 503) {
        setErro('Market Supply agregado ainda não está habilitado neste ambiente.')
      } else if (error instanceof MarketSupplyApiError && error.status === 403) {
        setErro('A Organization atual não possui permissão para solicitar esta visão agregada.')
      } else {
        setErro(
          error instanceof Error
            ? error.message
            : 'Falha ao solicitar a análise agregada de Market Supply.',
        )
      }
    } finally {
      setExecutando(false)
    }
  }

  return (
    <section className="detail-page market-supply-page">
      <header className="detail-page-header">
        <div className="detail-header-main">
          <div>
            <p className="detail-eyebrow">Market Supply</p>
            <h1 className="detail-title">Análise agregada</h1>
            <p className="detail-subtitle">
              Visão agregada e autorizada derivada de MarketReadiness. Não é Decision,
              certificado, promessa de disponibilidade futura ou reconhecimento oficial.
            </p>
          </div>
          <span className="detail-status-chip">aggregate-first</span>
        </div>
      </header>

      <form className="market-supply-form" onSubmit={executar}>
        <fieldset>
          <legend>Contexto</legend>
          <label htmlFor="market-supply-policy-id">Policy ID</label>
          <input
            id="market-supply-policy-id"
            type="text"
            value={policyId}
            onChange={(evento) => setPolicyId(evento.target.value)}
            required
          />

          <label htmlFor="market-supply-policy-version">Versão da Policy</label>
          <input
            id="market-supply-policy-version"
            type="number"
            min={1}
            value={policyVersion}
            onChange={(evento) => setPolicyVersion(Number(evento.target.value))}
            required
          />

          <label htmlFor="market-supply-quantity">Quantidade demandada</label>
          <input
            id="market-supply-quantity"
            type="number"
            min={1}
            value={quantity}
            onChange={(evento) => setQuantity(Number(evento.target.value))}
            required
          />

          <label htmlFor="market-supply-tags">Tags obrigatórias</label>
          <input
            id="market-supply-tags"
            type="text"
            value={requiredTags}
            onChange={(evento) => setRequiredTags(evento.target.value)}
            placeholder="ex.: ms, nelore"
          />
        </fieldset>

        <fieldset>
          <legend>Temporalidade</legend>
          <label htmlFor="market-supply-window-from">Janela comercial início</label>
          <input
            id="market-supply-window-from"
            type="datetime-local"
            value={windowFrom}
            onChange={(evento) => setWindowFrom(evento.target.value)}
            required
          />

          <label htmlFor="market-supply-window-until">Janela comercial fim</label>
          <input
            id="market-supply-window-until"
            type="datetime-local"
            value={windowUntil}
            onChange={(evento) => setWindowUntil(evento.target.value)}
            required
          />

          <label htmlFor="market-supply-reference-time">Reference time</label>
          <input
            id="market-supply-reference-time"
            type="datetime-local"
            value={referenceTime}
            onChange={(evento) => setReferenceTime(evento.target.value)}
            required
          />

          <label htmlFor="market-supply-knowledge-cutoff">Knowledge cutoff</label>
          <input
            id="market-supply-knowledge-cutoff"
            type="datetime-local"
            value={knowledgeCutoff}
            onChange={(evento) => setKnowledgeCutoff(evento.target.value)}
            required
          />
        </fieldset>

        <div className="market-supply-actions">
          <button type="submit" disabled={executando}>
            {executando ? 'Solicitando...' : 'Solicitar análise'}
          </button>
          <button
            type="button"
            onClick={() => setIdempotencyKey(newIdempotencyKey())}
            disabled={executando}
          >
            Nova chave
          </button>
          <span>Idempotency-Key: {idempotencyKey}</span>
        </div>
      </form>

      {erro && <ErrorState tone="compact" message={erro} />}

      {resultado?.status === 'NOT_RELEASED' && (
        <section className="market-supply-not-released" role="status">
          <h2>Resultado não liberado</h2>
          <p>
            A resposta pública foi protegida. O Titan não informa se a limitação veio de
            ausência, autorização, população candidata, privacidade ou supressão.
          </p>
        </section>
      )}

      {resultado?.status === 'RELEASED' && resultado.aggregate && (
        <MarketSupplyReleasedAggregate aggregate={resultado.aggregate} />
      )}
    </section>
  )
}

function MarketSupplyReleasedAggregate({ aggregate }: { aggregate: MarketSupplyAggregatePayload }) {
  const metrics = [
    ['População considerada', aggregate.population_count],
    ['Ready now', aggregate.ready_now],
    ['Condicionados', aggregate.conditioned],
    ['Indeterminados', aggregate.indeterminate],
    ['Não prontos', aggregate.not_ready],
    ['Não avaliados', aggregate.not_evaluated],
    ['Reavaliação requerida', aggregate.reassessment_required],
    ['Déficit estimado agora', aggregate.estimated_shortage_now ?? 'N/D'],
  ]

  return (
    <section className="market-supply-results">
      <h2>Resultado liberado</h2>
      <dl className="market-supply-metrics">
        {metrics.map(([label, value]) => (
          <div key={label} className="market-supply-metric">
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="market-supply-result-columns">
        <section>
          <h3>Gaps agregados</h3>
          {aggregate.gap_summary.length === 0 ? (
            <p>Nenhum gap agregado informado.</p>
          ) : (
            <ul>
              {aggregate.gap_summary.map((gap) => (
                <li key={gap.code}>
                  {gap.code}: {gap.count}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3>Limitações</h3>
          <ul>
            {aggregate.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </section>
      </div>
    </section>
  )
}
