import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  TreatmentApiError,
  fetchMedicationBatches,
  fetchMedications,
  registerTreatment,
  type LoteResumo,
  type MedicamentoResumo,
} from '../api/treatments'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

function agoraParaDatetimeLocal(): string {
  const agora = new Date()
  agora.setSeconds(0, 0)
  const deslocamento = agora.getTimezoneOffset() * 60000
  return new Date(agora.getTime() - deslocamento).toISOString().slice(0, 16)
}

// Tela S4 (Onda 2, LIV-PROD-01): primeiro fluxo de escrita do produto.
// Sem seletor de prescrição (POST /v1/livestock/treatments aceita
// prescription_id opcional e nada trava sem ele) e sem evidence_ids (exige o
// subsistema de Evidence, fora de escopo) -- só uma nota de evidência livre,
// que o backend já trata como "não é prova".
export function TreatmentForm(options: Options) {
  const { animalId } = useParams<{ animalId: string }>()
  const navigate = useNavigate()

  const [medicamentos, setMedicamentos] = useState<MedicamentoResumo[] | null>(null)
  const [medicamentoId, setMedicamentoId] = useState('')
  const [lotes, setLotes] = useState<LoteResumo[]>([])
  const [carregandoLotes, setCarregandoLotes] = useState(false)
  const [loteId, setLoteId] = useState('')
  const [appliedAt, setAppliedAt] = useState(agoraParaDatetimeLocal)
  const [dose, setDose] = useState('')
  const [nota, setNota] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    fetchMedications(options)
      .then((resposta) => setMedicamentos(resposta.items))
      .catch((error: unknown) => {
        setErro(error instanceof Error ? error.message : 'Falha ao carregar medicamentos.')
        setMedicamentos([])
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId])

  useEffect(() => {
    if (!medicamentoId) {
      setLotes([])
      setLoteId('')
      return
    }
    setCarregandoLotes(true)
    setLoteId('')
    fetchMedicationBatches(options, { medicationId: medicamentoId })
      .then((resposta) => setLotes(resposta.items))
      .catch((error: unknown) => {
        setErro(error instanceof Error ? error.message : 'Falha ao carregar lotes.')
      })
      .finally(() => setCarregandoLotes(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId, medicamentoId])

  if (!animalId) return null

  const submeter = async (evento: FormEvent) => {
    evento.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      await registerTreatment(options, {
        animalId,
        medicationBatchId: loteId,
        appliedAt: new Date(appliedAt).toISOString(),
        dose: dose || undefined,
        evidenceNotes: nota ? [nota] : [],
      })
      navigate(`/animals/${animalId}`)
    } catch (error) {
      if (error instanceof TreatmentApiError) {
        setErro(error.message)
      } else {
        setErro(error instanceof Error ? error.message : 'Falha ao registrar o tratamento.')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section>
      <p>
        <Link to={`/animals/${animalId}`}>&larr; Voltar para o animal</Link>
      </p>
      <h2>Registrar tratamento</h2>

      <form onSubmit={submeter}>
        <p>
          <label htmlFor="tratamento-medicamento">Medicamento</label>
          <br />
          <select
            id="tratamento-medicamento"
            value={medicamentoId}
            onChange={(evento) => setMedicamentoId(evento.target.value)}
            required
          >
            <option value="">
              {medicamentos === null ? 'Carregando…' : 'Selecione um medicamento'}
            </option>
            {medicamentos?.map((medicamento) => (
              <option key={medicamento.medication_id} value={medicamento.medication_id}>
                {medicamento.trade_name} ({medicamento.active_ingredient})
              </option>
            ))}
          </select>
        </p>

        <p>
          <label htmlFor="tratamento-lote">Lote</label>
          <br />
          <select
            id="tratamento-lote"
            value={loteId}
            onChange={(evento) => setLoteId(evento.target.value)}
            required
            disabled={!medicamentoId || carregandoLotes}
          >
            <option value="">
              {carregandoLotes ? 'Carregando…' : 'Selecione um lote'}
            </option>
            {lotes.map((lote) => (
              <option key={lote.batch_id} value={lote.batch_id}>
                {lote.batch_number} — vence em{' '}
                {new Date(lote.expiry_date).toLocaleDateString('pt-BR')}
              </option>
            ))}
          </select>
          {medicamentoId && !carregandoLotes && lotes.length === 0 && (
            <>
              <br />
              <em>Nenhum lote cadastrado para este medicamento.</em>
            </>
          )}
        </p>

        <p>
          <label htmlFor="tratamento-instante">Instante de aplicação</label>
          <br />
          <input
            id="tratamento-instante"
            type="datetime-local"
            value={appliedAt}
            onChange={(evento) => setAppliedAt(evento.target.value)}
            required
          />
        </p>

        <p>
          <label htmlFor="tratamento-dose">Dose (opcional)</label>
          <br />
          <input
            id="tratamento-dose"
            type="text"
            value={dose}
            onChange={(evento) => setDose(evento.target.value)}
          />
        </p>

        <p>
          <label htmlFor="tratamento-nota">Nota de evidência (opcional, não é prova)</label>
          <br />
          <input
            id="tratamento-nota"
            type="text"
            value={nota}
            onChange={(evento) => setNota(evento.target.value)}
          />
        </p>

        {erro && <p role="alert">{erro}</p>}

        <button type="submit" disabled={enviando || !loteId}>
          {enviando ? 'Registrando…' : 'Registrar aplicação'}
        </button>
      </form>
    </section>
  )
}
