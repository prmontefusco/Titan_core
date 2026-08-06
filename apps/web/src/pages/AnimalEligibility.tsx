import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EligibilityApiError, runAnimalEligibility, type ElegibilidadeResponse } from '../api/eligibility'

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
    <section>
      <p>
        <Link to={`/animals/${animalId}`}>&larr; Voltar para o animal</Link>
      </p>
      <h2>Elegibilidade do animal</h2>

      <button type="button" onClick={executar} disabled={executando}>
        {executando ? 'Executando…' : 'Executar elegibilidade'}
      </button>

      {proposalId && (
        <p role="alert">
          Revisão humana necessária antes de emitir a decisão. Proposta: <code>{proposalId}</code>.
          O fluxo de revisão ainda não está disponível nesta versão do produto.
        </p>
      )}
      {erro && <p role="alert">{erro}</p>}

      {resultado && (
        <dl>
          <dt>Resultado</dt>
          <dd>{resultado.result}</dd>
          <dt>Situação</dt>
          <dd>{resultado.outcome}</dd>
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
          <dd>
            <code>{resultado.evaluation_id}</code>
          </dd>
          <dt>Decision</dt>
          <dd>
            <code>{resultado.decision_id}</code>
          </dd>
          <dt>Dossiê</dt>
          <dd>
            <code>{resultado.dossier_id}</code>
          </dd>
        </dl>
      )}
    </section>
  )
}
