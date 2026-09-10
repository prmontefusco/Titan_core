import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EligibilityApiError, runAnimalEligibility, type ElegibilidadeResponse } from '../api/eligibility'
import { ErrorState } from '../components/AsyncStates'
import { DetailDescriptionList, DetailPageHeader, DetailSection } from '../components/DetailPage'
import { PageContext } from '../components/PageContext'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

// Tela S6 (Onda 3): primeira tela em que o motor de decisão do Titan aparece
// como valor de produto. Executar é ação explícita (botão), não side-effect
// de navegação -- cada execução grava Evaluation/Decision/Dossier de verdade.
export function AnimalEligibility(options: Options) {
  const { animalId } = useParams<{ animalId: string }>()
  const [resultado, setResultado] = useState<ElegibilidadeResponse | null>(null)
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  if (!animalId) return null

  const executar = async () => {
    setExecutando(true)
    setErro(null)
    setProposalId(null)
    try {
      const resposta = await runAnimalEligibility(options, animalId)
      setResultado(resposta)
    } catch (error) {
      if (error instanceof EligibilityApiError && error.requiresHumanReview) {
        setProposalId(error.proposalId)
      } else {
        setErro(error instanceof Error ? error.message : 'Falha ao executar a elegibilidade.')
      }
    } finally {
      setExecutando(false)
    }
  }

  return (
    <article className="detail-page">
      <DetailPageHeader
        eyebrow="Livestock / Elegibilidade"
        title="Elegibilidade do animal"
        subtitle="Execução explícita do motor de decisão. O navegador apenas solicita a avaliação e exibe o resultado devolvido pela API."
        backTo={`/animals/${animalId}`}
        backLabel="Voltar para o animal"
        actions={
          <button type="button" onClick={executar} disabled={executando}>
            {executando ? 'Executando...' : 'Executar elegibilidade'}
          </button>
        }
      />

      <PageContext
        description="A avaliação será executada no contexto da Organization ativa e pode gravar Evaluation, Decision e Dossier."
        items={[
          { label: 'Organization', value: options.organizationId },
          { label: 'Animal', value: animalId },
        ]}
      />

      {proposalId && (
        <section className="eligibility-review-alert" role="alert">
          <h2>Revisão humana necessária</h2>
          <p>
            A API recusou a emissão automática e criou uma proposta de revisão. Proposta:{' '}
            <code>{proposalId}</code>.
          </p>
          <Link to={`/review/${proposalId}`}>Abrir revisão humana</Link>
        </section>
      )}
      {erro && <ErrorState tone="compact" title="Falha ao executar elegibilidade" message={erro} />}

      {!resultado && !proposalId && !erro && (
        <DetailSection
          title="Antes de executar"
          description="Este fluxo não roda automaticamente ao abrir a tela para evitar gerar decisões sem ação explícita do operador."
        >
          <p className="empty-notice">
            Clique em executar quando quiser solicitar uma nova avaliação ao backend.
          </p>
        </DetailSection>
      )}

      {resultado && (
        <DetailSection
          title="Resultado da avaliação"
          description="Valores retornados pela API; a UI não recalcula nem altera a decisão."
        >
          <DetailDescriptionList>
            <dt>Resultado</dt>
            <dd><span className="detail-status-chip">{resultado.result}</span></dd>
            <dt>Situação</dt>
            <dd>{resultado.outcome}</dd>
            <dt>Corte de conhecimento</dt>
            <dd>{new Date(resultado.knowledge_cutoff).toLocaleString('pt-BR')}</dd>
            <dt>Motivos</dt>
            <dd>
              {resultado.reasons.length === 0 ? (
                'nenhum'
              ) : (
                <ul>
                  {resultado.reasons.map((motivo, indice) => (
                    <li key={indice}>{motivo}</li>
                  ))}
                </ul>
              )}
            </dd>
            <dt>Limitações de conhecimento</dt>
            <dd>
              {resultado.knowledge_limitations.length === 0 ? (
                'nenhuma'
              ) : (
                <ul>
                  {resultado.knowledge_limitations.map((limitacao, indice) => (
                    <li key={indice}>{limitacao}</li>
                  ))}
                </ul>
              )}
            </dd>
            <dt>Evaluation</dt>
            <dd><code>{resultado.evaluation_id}</code></dd>
            <dt>Decision</dt>
            <dd><code>{resultado.decision_id}</code></dd>
            <dt>Dossiê</dt>
            <dd><code>{resultado.dossier_id}</code></dd>
          </DetailDescriptionList>
        </DetailSection>
      )}
    </article>
  )
}
