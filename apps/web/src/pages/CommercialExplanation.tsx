import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  EligibilityApiError,
  runCommercialExplanation,
  type ExplicacaoComercialResponse,
} from '../api/eligibility'
import { ErrorState } from '../components/AsyncStates'
import { AnimalFlowContext } from '../components/AnimalFlowContext'
import { DetailPageHeader, DetailSection } from '../components/DetailPage'
import { PageContext } from '../components/PageContext'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

function textosUnicos(textos: string[]): string[] {
  return [...new Set(textos)]
}

function temMercadoAusente(markets: ExplicacaoComercialResponse['markets']): boolean {
  return markets.some((mercado) => mercado.status === 'AUSENTE')
}

function linkGovernancaDeMercado(animalId: string): string {
  const params = new URLSearchParams({
    returnTo: `/animals/${animalId}/commercial-explanation`,
    animalId,
  })
  return `/rule-governance?${params.toString()}`
}

function retornoAnimalSeguro(returnTo: string | null, animalId: string): string | null {
  if (!returnTo) return null
  const rotasPermitidas = [`/animals/${animalId}`, `/animals/${animalId}/market-matrix`]
  return rotasPermitidas.includes(returnTo) ? returnTo : null
}

// Tela S8 (Onda 3), generalizada na Onda 4 para aceitar lote além de animal
// -- POST /market-eligibility/commercial-explanations já aceita lot_id como
// alternativa a animal_id (XOR) e devolve o mesmo ExplicacaoComercialResponse
// com subject_type diferente, então é o mesmo componente, não uma tela nova.
//
// "para onde posso vender, por que não posso, e qual é a próxima ação?" --
// narrativa comercial, não um lugar para resolver dependência de sujeito
// (isso é a Matriz de Mercado/Detalhe do Lote: ExplicacaoMercadoResponse não
// expõe o campo `dependency` estruturado, só `next_action` em texto).
export function CommercialExplanation(options: Options) {
  const { animalId, lotId } = useParams<{ animalId?: string; lotId?: string }>()
  const [searchParams] = useSearchParams()
  const [resultado, setResultado] = useState<ExplicacaoComercialResponse | null>(null)
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  if (!animalId && !lotId) return null

  const executar = async () => {
    setExecutando(true)
    setErro(null)
    setProposalId(null)
    try {
      const resposta = await runCommercialExplanation(
        options,
        animalId ? { animalId } : { lotId: lotId! },
      )
      setResultado(resposta)
    } catch (error) {
      if (error instanceof EligibilityApiError && error.requiresHumanReview) {
        setProposalId(error.proposalId)
      } else {
        setErro(error instanceof Error ? error.message : 'Falha ao gerar a explicação comercial.')
      }
    } finally {
      setExecutando(false)
    }
  }

  const retornoAnimal = animalId ? retornoAnimalSeguro(searchParams.get('returnTo'), animalId) : null
  const linkDeVolta = animalId
    ? {
        to: retornoAnimal ?? `/animals/${animalId}/market-matrix`,
        texto: retornoAnimal === `/animals/${animalId}`
          ? 'Voltar para o animal'
          : 'Voltar para a matriz de mercado',
      }
    : { to: `/lots/${lotId}`, texto: 'Voltar para o lote' }
  const subjectLabel = animalId ? 'Animal' : 'Lote'
  const subjectId = animalId ?? lotId!

  return (
    <article className="detail-page">
      <DetailPageHeader
        eyebrow="Livestock / Explicação comercial"
        title="Explicação comercial"
        subtitle="Narrativa e motivos devolvidos pela API para explicar a conclusão comercial, sem reclassificação no navegador."
        backTo={linkDeVolta.to}
        backLabel={linkDeVolta.texto}
        actions={
          <button type="button" onClick={executar} disabled={executando}>
            {executando ? 'Executando...' : 'Gerar explicação comercial'}
          </button>
        }
      />

      {animalId ? (
        <AnimalFlowContext
          description="A explicação é emitida para o animal e Organization ativos. Ausências e limitações permanecem como a API retornar."
          organizationId={options.organizationId}
          animalId={animalId}
        />
      ) : (
        <PageContext
          description="A explicação é emitida para o lote e Organization ativos. Ausências e limitações permanecem como a API retornar."
          items={[
            { label: 'Organization', value: options.organizationId },
            { label: subjectLabel, value: subjectId },
          ]}
        />
      )}

      {proposalId && (
        <section className="eligibility-review-alert" role="alert">
          <h2>Revisão humana necessária</h2>
          <p>A API recusou a emissão automática. Proposta: <code>{proposalId}</code>.</p>
          <Link to={`/review/${proposalId}`}>Abrir revisão humana</Link>
        </section>
      )}
      {erro && <ErrorState tone="compact" title="Falha ao gerar explicação" message={erro} />}

      {!resultado && !proposalId && !erro && (
        <DetailSection
          title="Antes de gerar"
          description="A explicação comercial só é solicitada quando o operador executa a ação."
        >
          <p className="empty-notice">
            Gere a explicação para ver conclusão, narrativa, próximos passos e motivos por mercado.
          </p>
        </DetailSection>
      )}

      {resultado && (
        <DetailSection
          title="Conclusão explicada"
          description="Conclusão, narrativa e ações recomendadas retornadas pelo backend."
        >
          <div className="market-flow-summary">
            <span className="detail-status-chip">{resultado.commercial_outlook}</span>
            <p>{resultado.narrative}</p>
            <p>{resultado.executive_summary}</p>
            {resultado.recommended_next_action && (
              <p>
                <strong>Próxima ação recomendada:</strong> {resultado.recommended_next_action}
              </p>
            )}
            {temMercadoAusente(resultado.markets) && (
              <Link to={animalId ? linkGovernancaDeMercado(animalId) : '/rule-governance'}>
                Publicar ou adotar regras de mercado
              </Link>
            )}
          </div>

          <ul className="market-flow-list">
            {resultado.markets.map((mercado) => (
              <li key={mercado.market}>
                <div>
                  <strong>{mercado.market}</strong>
                  <span className="market-status-chip">{mercado.status}</span>
                </div>
                <p>{mercado.summary}</p>
                {mercado.why.length > 0 && (
                  <ul>
                    {textosUnicos(mercado.why).map((motivo) => (
                      <li key={motivo}>{motivo}</li>
                    ))}
                  </ul>
                )}
                {mercado.next_action && (
                  <p><em>Próxima ação: {mercado.next_action}</em></p>
                )}
                {mercado.affected_animal_ids.length > 0 && (
                  <p>
                    Animais afetados:{' '}
                    {mercado.affected_animal_ids.map((id, indice) => (
                      <span key={id}>
                        {indice > 0 && ', '}
                        <Link to={`/animals/${id}`}>{id}</Link>
                      </span>
                    ))}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </DetailSection>
      )}
    </article>
  )
}
