import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DecisionReview } from './DecisionReview'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderTela(proposalId = 'p1') {
  return render(
    <MemoryRouter initialEntries={[`/review/${proposalId}`]}>
      <Routes>
        <Route path="/review/:proposalId" element={<DecisionReview {...options} />} />
      </Routes>
    </MemoryRouter>,
  )
}

function respostaProposta(overrides: Record<string, unknown> = {}) {
  return {
    proposal_id: 'p1',
    evaluation_id: 'e1',
    evaluation_hash: 'hash',
    purpose: 'eligibility',
    proposed_result: 'INDETERMINADA',
    proposed_reasons: [{ message: 'Evidência sanitária conflitante.' }],
    justification_required: true,
    created_at: '2026-01-01T00:00:00Z',
    review_count: 0,
    current_proposal: true,
    ...overrides,
  }
}

describe('DecisionReview', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('carrega a proposta e mostra o indicador de atualidade', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => respostaProposta() }),
    )

    renderTela()

    expect(await screen.findByText('INDETERMINADA')).toBeInTheDocument()
    expect(screen.getByText(/esta é a proposta corrente/i)).toBeInTheDocument()
  })

  it('mostra que a proposta foi superada quando current_proposal é falso', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => respostaProposta({ current_proposal: false }),
      }),
    )

    renderTela()

    expect(await screen.findByText(/superada por uma proposta mais recente/i)).toBeInTheDocument()
  })

  it('mostra mensagem clara quando a proposta não é encontrada (404)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ reason_code: 'RECURSO_NAO_ENCONTRADO', detail: 'não encontrada' }),
      }),
    )

    renderTela()

    expect(await screen.findByRole('alert')).toHaveTextContent(/não encontrada/i)
  })

  it('registra revisão e mostra o status quando ainda aguarda aprovações', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      void init
      if (url.endsWith('/reviews')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({
            proposal_id: 'p1',
            review_id: 'r1',
            workflow_status: 'AGUARDANDO_APROVACOES',
            decision_id: null,
            dossier_id: null,
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => respostaProposta() })
    })
    vi.stubGlobal('fetch', fetchMock)

    renderTela()
    await screen.findByText('INDETERMINADA')

    fireEvent.change(screen.getByLabelText(/fundamentação/i), {
      target: { value: 'Conflito revisado e aceito.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /registrar revisão/i }))

    expect(await screen.findByText(/aguardando mais aprovações/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /abrir dossiê/i })).not.toBeInTheDocument()

    const chamada = fetchMock.mock.calls.find((call) => (call[0] as string).endsWith('/reviews'))
    expect(JSON.parse(chamada![1]!.body as string)).toEqual({
      conclusion: 'APROVA',
      reasoning: 'Conflito revisado e aceito.',
    })
  })

  it('mostra decisão emitida e abre o dossiê', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      void init
      if (url.endsWith('/reviews')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({
            proposal_id: 'p1',
            review_id: 'r1',
            workflow_status: 'DECISION_EMITTED',
            decision_id: 'd1',
            dossier_id: 'ds1',
          }),
        })
      }
      if (url.endsWith('/dossiers/ds1')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            dossier_id: 'ds1',
            dossier_hash: 'hash-abc',
            generated_at: '2026-01-02T00:00:00Z',
            document: { decision: { emission_method: 'HUMAN' } },
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => respostaProposta() })
    })
    vi.stubGlobal('fetch', fetchMock)

    renderTela()
    await screen.findByText('INDETERMINADA')

    fireEvent.change(screen.getByLabelText(/fundamentação/i), {
      target: { value: 'Conflito revisado e aceito.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /registrar revisão/i }))

    expect(await screen.findByText(/decisão emitida/i)).toBeInTheDocument()
    expect(screen.getByText('d1')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /abrir dossiê/i }))

    expect(await screen.findByText('hash-abc')).toBeInTheDocument()
    expect(screen.getByText(/HUMAN/)).toBeInTheDocument()
  })
})
