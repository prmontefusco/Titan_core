import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MarketSupplyAggregate } from './MarketSupplyAggregate'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-buyer',
}

function renderTela() {
  return render(<MarketSupplyAggregate {...options} />)
}

describe('MarketSupplyAggregate', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('envia o contrato F3.5 com headers de tenant, authorization e idempotência', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'NOT_RELEASED' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderTela()

    fireEvent.change(screen.getByLabelText(/policy id/i), {
      target: { value: '11111111-1111-1111-1111-111111111111' },
    })
    fireEvent.change(screen.getByLabelText(/quantidade demandada/i), {
      target: { value: '7' },
    })
    fireEvent.change(screen.getByLabelText(/tags obrigatórias/i), {
      target: { value: 'ms, nelore' },
    })
    fireEvent.click(screen.getByRole('button', { name: /solicitar análise/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0]

    expect(url).toBe('http://127.0.0.1:8000/v1/livestock/market-supply/aggregate-assessments')
    expect(init.headers.Authorization).toBe('Bearer meu-token')
    expect(init.headers['X-Titan-Organization-Id']).toBe('org-buyer')
    expect(init.headers['Idempotency-Key']).toMatch(/.+/)
    expect(JSON.parse(init.body)).toMatchObject({
      policy_id: '11111111-1111-1111-1111-111111111111',
      policy_version: 1,
      purpose: 'MARKET_SUPPLY_AGGREGATE_ASSESSMENT',
      quantity: 7,
      candidate_criteria: {
        subject_type: 'animal',
        required_tags: ['ms', 'nelore'],
      },
    })
  })

  it('mostra RELEASED com somente agregados públicos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'RELEASED',
          aggregate: {
            population_count: 10,
            readiness_counts: {
              READY: 6,
              CONDITIONED: 1,
              INDETERMINATE: 1,
              NOT_READY: 1,
              NOT_EVALUATED: 1,
              REASSESSMENT_REQUIRED: 0,
            },
            ready_now: 6,
            conditioned: 1,
            indeterminate: 1,
            not_ready: 1,
            not_evaluated: 1,
            reassessment_required: 0,
            current_capacity: 6,
            requested_quantity: 8,
            estimated_shortage_now: 2,
            gap_summary: [{ code: 'DOCUMENTATION_GAP', count: 2 }],
            limitations: ['aggregate summary only'],
          },
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /solicitar análise/i }))

    expect(await screen.findByText(/resultado liberado/i)).toBeInTheDocument()
    expect(screen.getByText('Ready now')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument()
    expect(screen.getByText(/DOCUMENTATION_GAP: 2/)).toBeInTheDocument()
    expect(screen.queryByText(/animal_id/i)).not.toBeInTheDocument()
  })

  it('mostra NOT_RELEASED sem revelar motivo interno', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'NOT_RELEASED',
          internal_reason: 'DIFFERENCING_RISK',
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /solicitar análise/i }))

    const aviso = await screen.findByRole('status')
    expect(aviso).toHaveTextContent(/resultado não liberado/i)
    expect(aviso).not.toHaveTextContent(/DIFFERENCING_RISK/)
  })

  it('trata 503 como capacidade indisponível sem expor detalhe operacional bruto', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({
          reason_code: 'MARKET_SUPPLY_PIPELINE_NAO_HABILITADO',
          detail: 'pipeline interno desligado',
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /solicitar análise/i }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/não está habilitado/i)
    expect(alerta).not.toHaveTextContent(/pipeline interno desligado/i)
  })
})
