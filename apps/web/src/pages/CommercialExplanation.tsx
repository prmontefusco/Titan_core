import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  EligibilityApiError,
  runCommercialExplanation,
  type ExplicacaoComercialResponse,
} from '../api/eligibility'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

// Tela S8 (Onda 3): "para onde posso vender, por que não posso, e qual é a
// próxima ação?" -- narrativa comercial, não um lugar para resolver
// dependência de sujeito (isso é a Matriz de Mercado, S7:
// ExplicacaoMercadoResponse não expõe o campo `dependency` estruturado, só
// `next_action` em texto -- se um mercado depender de frigorífico ainda não
// escolhido, o próprio texto do backend orienta a voltar para a matriz).
export function CommercialExplanation(options: Options) {
  const { animalId } = useParams<{ animalId: string }>()
  const [resultado, setResultado] = useState<ExplicacaoComercialResponse | null>(null)
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  if (!animalId) return null

  const executar = async () => {
    setExecutando(true)
    setErro(null)
    setProposalId(null)
    try {
      const resposta = await runCommercialExplanation(options, { animalId })
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

  return (
    <section>
      <p>
        <Link to={`/animals/${animalId}/market-matrix`}>&larr; Voltar para a matriz de mercado</Link>
      </p>
      <h2>Explicação comercial</h2>

      <button type="button" onClick={executar} disabled={executando}>
        {executando ? 'Executando…' : 'Gerar explicação comercial'}
      </button>

      {proposalId && (
        <p role="alert">
          Revisão humana necessária antes de emitir a decisão. Proposta: <code>{proposalId}</code>.
          O fluxo de revisão ainda não está disponível nesta versão do produto.
        </p>
      )}
      {erro && <p role="alert">{erro}</p>}

      {resultado && (
        <>
          <p>
            <strong>{resultado.commercial_outlook}</strong>
          </p>
          <p>{resultado.narrative}</p>
          <p>{resultado.executive_summary}</p>
          {resultado.recommended_next_action && (
            <p>
              <strong>Próxima ação recomendada:</strong> {resultado.recommended_next_action}
            </p>
          )}

          <ul>
            {resultado.markets.map((mercado) => (
              <li key={mercado.market}>
                <strong>{mercado.market}</strong>: {mercado.status} — {mercado.summary}
                {mercado.why.length > 0 && (
                  <ul>
                    {mercado.why.map((motivo, indice) => (
                      <li key={indice}>{motivo}</li>
                    ))}
                  </ul>
                )}
                {mercado.next_action && (
                  <p>
                    <em>Próxima ação: {mercado.next_action}</em>
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
