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

  const linkDeVolta = animalId
    ? { to: `/animals/${animalId}/market-matrix`, texto: 'Voltar para a matriz de mercado' }
    : { to: `/lots/${lotId}`, texto: 'Voltar para o lote' }

  return (
    <section>
      <p>
        <Link to={linkDeVolta.to}>&larr; {linkDeVolta.texto}</Link>
      </p>
      <h2>Explicação comercial</h2>

      <button type="button" onClick={executar} disabled={executando}>
        {executando ? 'Executando…' : 'Gerar explicação comercial'}
      </button>

      {proposalId && (
        <p role="alert">
          Revisão humana necessária antes de emitir a decisão. Proposta: <code>{proposalId}</code>.{' '}
          <Link to={`/review/${proposalId}`}>Abrir revisão humana</Link>
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
        </>
      )}
    </section>
  )
}
