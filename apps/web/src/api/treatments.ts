// Mesmo padrão de api/animals.ts e api/entityTypeRequests.ts: chamar<T>()
// central, erro tipado a partir de application/problem+json.

interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export class TreatmentApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null

  constructor(status: number, reasonCode: string | null, detail?: string) {
    super(detail ?? `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = reasonCode
  }
}

async function chamar<T>(
  path: string,
  { baseUrl, accessToken, organizationId }: RequestOptions,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-Titan-Organization-Id': organizationId,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })

  if (!response.ok) {
    const corpo = await response.json().catch(() => null)
    throw new TreatmentApiError(response.status, corpo?.reason_code ?? null, corpo?.detail)
  }

  return (await response.json()) as T
}

export interface MedicamentoResumo {
  medication_id: string
  trade_name: string
  active_ingredient: string
  manufacturer: string
  withdrawal_period_days: number
  product_class: string
  dosage_instruction: string | null
}

export interface LoteResumo {
  batch_id: string
  medication_id: string
  batch_number: string
  expiry_date: string
  manufacturing_date: string | null
}

interface Pagina<T> {
  items: T[]
  limit: number
  offset: number
  has_more: boolean
}

export interface TratamentoResponse {
  application_id: string
  animal_id: string
  medication_batch_id: string
  applied_at: string
  dose: string | null
  prescription_id: string | null
  sanitary_campaign_id: string | null
  corrects_application_id: string | null
}

export function fetchMedications(options: RequestOptions): Promise<Pagina<MedicamentoResumo>> {
  return chamar<Pagina<MedicamentoResumo>>('/v1/livestock/medications', options)
}

export function fetchMedicationBatches(
  options: RequestOptions,
  params: { medicationId?: string } = {},
): Promise<Pagina<LoteResumo>> {
  const query = params.medicationId ? `?medication_id=${params.medicationId}` : ''
  return chamar<Pagina<LoteResumo>>(`/v1/livestock/medication-batches${query}`, options)
}

export interface RegisterTreatmentInput {
  animalId: string
  medicationBatchId: string
  appliedAt: string
  dose?: string
  evidenceNotes?: string[]
}

export function registerTreatment(
  options: RequestOptions,
  input: RegisterTreatmentInput,
): Promise<TratamentoResponse> {
  return chamar<TratamentoResponse>('/v1/livestock/treatments', options, {
    method: 'POST',
    body: JSON.stringify({
      animal_id: input.animalId,
      medication_batch_id: input.medicationBatchId,
      applied_at: input.appliedAt,
      dose: input.dose || null,
      evidence_notes: input.evidenceNotes ?? [],
    }),
  })
}
