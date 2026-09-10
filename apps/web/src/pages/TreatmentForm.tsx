import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  TreatmentApiError,
  fetchMedicationBatches,
  fetchMedications,
  registerTreatment,
  type LoteResumo,
  type MedicamentoResumo,
} from '../api/treatments'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { DetailPageHeader, DetailSection } from '../components/DetailPage'
import { PageContext } from '../components/PageContext'

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
    <article className="detail-page">
      <DetailPageHeader
        eyebrow="Livestock / Tratamento"
        title="Registrar tratamento"
        subtitle="Registro operacional de aplicação. O backend preserva a regra sanitária; a UI apenas envia os dados informados."
        backTo={`/animals/${animalId}`}
        backLabel="Voltar para o animal"
      />
      <PageContext
        description="O registro será feito apenas para o animal e a Organization atualmente em uso."
        items={[
          { label: 'Organization', value: options.organizationId },
          { label: 'Animal', value: animalId },
        ]}
      />

      <DetailSection
        title="Aplicação"
        description="Selecione medicamento e lote antes de registrar. Nenhum dado é salvo até o envio explícito."
      >
        {medicamentos === null && <LoadingState tone="compact" message="Carregando medicamentos..." />}
        {medicamentos !== null && medicamentos.length === 0 && (
          <EmptyState
            tone="compact"
            message="Nenhum medicamento disponível para registro nesta Organization."
          />
        )}
        <form className="treatment-form" onSubmit={submeter}>
          <label htmlFor="tratamento-medicamento">Medicamento</label>
          <select
            id="tratamento-medicamento"
            value={medicamentoId}
            onChange={(evento) => setMedicamentoId(evento.target.value)}
            required
            disabled={medicamentos === null || medicamentos.length === 0}
          >
            <option value="">
              {medicamentos === null ? 'Carregando...' : 'Selecione um medicamento'}
            </option>
            {medicamentos?.map((medicamento) => (
              <option key={medicamento.medication_id} value={medicamento.medication_id}>
                {medicamento.trade_name} ({medicamento.active_ingredient})
              </option>
            ))}
          </select>

          <label htmlFor="tratamento-lote">Lote</label>
          <select
            id="tratamento-lote"
            value={loteId}
            onChange={(evento) => setLoteId(evento.target.value)}
            required
            disabled={!medicamentoId || carregandoLotes}
          >
            <option value="">
              {carregandoLotes ? 'Carregando...' : 'Selecione um lote'}
            </option>
            {lotes.map((lote) => (
              <option key={lote.batch_id} value={lote.batch_id}>
                {lote.batch_number} - vence em{' '}
                {new Date(lote.expiry_date).toLocaleDateString('pt-BR')}
              </option>
            ))}
          </select>
          {medicamentoId && !carregandoLotes && lotes.length === 0 && (
            <p className="field-help">Nenhum lote cadastrado para este medicamento.</p>
          )}

          <label htmlFor="tratamento-instante">Instante de aplicação</label>
          <input
            id="tratamento-instante"
            type="datetime-local"
            value={appliedAt}
            onChange={(evento) => setAppliedAt(evento.target.value)}
            required
          />

          <label htmlFor="tratamento-dose">Dose (opcional)</label>
          <input
            id="tratamento-dose"
            type="text"
            value={dose}
            onChange={(evento) => setDose(evento.target.value)}
          />

          <label htmlFor="tratamento-nota">Nota de evidência (opcional, não é prova)</label>
          <input
            id="tratamento-nota"
            type="text"
            value={nota}
            onChange={(evento) => setNota(evento.target.value)}
          />
          <p className="field-help">
            A nota ajuda a operação, mas não substitui Evidence validada nem comprova verdade material.
          </p>

          {erro && <ErrorState tone="compact" message={erro} />}

          <button type="submit" disabled={enviando || !loteId}>
            {enviando ? 'Registrando...' : 'Registrar aplicação'}
          </button>
        </form>
      </DetailSection>
    </article>
  )
}
