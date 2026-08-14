import { useState } from 'react'
import {
  TerritorialCaptureApiError,
  criarPropriedadeQa,
  listarCapturasTerritoriais,
  registrarCapturaOverlapQa,
  registrarCapturaTimelineQa,
  registrarGeometriaQa,
  type CapturaTerritorial,
} from '../api/territorialCaptures'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

interface EstadoQa {
  propertyId: string
  geometryId: string
  geometryVersion: number
  captures: CapturaTerritorial[]
}

function resumo(captura: CapturaTerritorial): string {
  const profile = String(captura.response_summary.profile ?? captura.source_layer)
  const operation = String(captura.response_summary.operation ?? captura.operation)
  return `${profile} / ${operation}`
}

// Corte 5A: tela técnica de QA manual sobre a API sintética do Corte 4.
// Continua deliberadamente fora de geodata real e fora de Policy/Evaluation.
export function TerritorialCaptureQa(options: Options) {
  const [estado, setEstado] = useState<EstadoQa | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const executar = async () => {
    setExecutando(true)
    setErro(null)
    try {
      const sufixo = crypto.randomUUID().slice(0, 8).toUpperCase()
      const propriedade = await criarPropriedadeQa(options, `TERR-QA-${sufixo}`)
      const geometria = await registrarGeometriaQa(options, propriedade.property_id)
      await registrarCapturaOverlapQa(
        options,
        propriedade.property_id,
        geometria.geometry_id,
        geometria.version,
      )
      await registrarCapturaTimelineQa(
        options,
        propriedade.property_id,
        geometria.geometry_id,
        geometria.version,
      )
      const capturas = await listarCapturasTerritoriais(options, propriedade.property_id)
      setEstado({
        propertyId: propriedade.property_id,
        geometryId: geometria.geometry_id,
        geometryVersion: geometria.version,
        captures: capturas.items,
      })
    } catch (error) {
      if (error instanceof TerritorialCaptureApiError) {
        setErro(`${error.message} (${error.reasonCode ?? error.status})`)
      } else {
        setErro(error instanceof Error ? error.message : 'Falha no QA territorial sintético.')
      }
    } finally {
      setExecutando(false)
    }
  }

  return (
    <section>
      <h2>QA territorial sintético</h2>
      <p>
        Esta tela executa somente o fluxo sintético do T-05D. Ela cria material de
        teste para inspeção humana, mas não consulta fonte oficial, não gera Fact e
        não emite Policy, Evaluation, Decision ou Dossier.
      </p>

      <button type="button" onClick={executar} disabled={executando}>
        {executando ? 'Executando QA…' : 'Criar cenário sintético'}
      </button>

      {erro && <p role="alert">{erro}</p>}

      {estado && (
        <>
          <h3>Cenário criado</h3>
          <dl>
            <dt>Property</dt>
            <dd>
              <code>{estado.propertyId}</code>
            </dd>
            <dt>Geometry</dt>
            <dd>
              <code>{estado.geometryId}</code> v{estado.geometryVersion}
            </dd>
            <dt>Resultado</dt>
            <dd>Capturas sintéticas preservadas: {estado.captures.length}</dd>
          </dl>

          <h3>Capturas</h3>
          <ul>
            {estado.captures.map((captura) => (
              <li key={captura.capture_id}>
                <strong>{resumo(captura)}</strong> — {captura.source_environment},{' '}
                digest <code>{captura.response_digest}</code>
                {captura.limitations.length > 0 && (
                  <ul>
                    {captura.limitations.map((limitacao) => (
                      <li key={limitacao}>{limitacao}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>

          <p role="note">
            Fronteira preservada: captura territorial sintética não é conformidade,
            autorização externa nem elegibilidade de mercado.
          </p>
        </>
      )}
    </section>
  )
}
