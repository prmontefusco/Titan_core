import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LotDetail } from './LotDetail'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderTela(lotId = 'l1') {
  return render(
    <MemoryRouter initialEntries={[`/lots/${lotId}`]}>
      <Routes>
        <Route path="/lots/:lotId" element={<LotDetail {...options} />} />
      </Routes>
    </MemoryRouter>,
  )
}

function respostaLote() {
  return { lot_id: 'l1', property_id: 'p1', code: 'LOTE-01', name: 'Lote de engorda', lot_type: 'ENGORDA', status: 'ATIVO' }
}

function respostaMembros() {
  return {
    lot_id: 'l1',
    at_time: null,
    members: [
      { membership_id: 'm1', animal_id: 'a1', valid_from: '2026-01-01T00:00:00Z', valid_until: null, reason: 'ENTRADA' },
    ],
  }
}

describe('LotDetail', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('mostra a identidade do lote e a lista de membros ao carregar', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/members')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => respostaMembros() })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => respostaLote() })
    })
    vi.stubGlobal('fetch', fetchMock)

    renderTela()

    expect(await screen.findByText('LOTE-01', { exact: false })).toBeInTheDocument()
    expect(await screen.findByText('a1')).toBeInTheDocument()
  })

  it('mostra mensagem clara quando o lote não é encontrado (404)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ reason_code: 'RECURSO_NAO_ENCONTRADO', detail: 'não encontrado' }),
      }),
    )

    renderTela()

    expect(await screen.findByRole('alert')).toHaveTextContent(/não encontrado/i)
  })

  it('executa a análise de mercado e mostra os animais agrupados por status', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/members')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => respostaMembros() })
      }
      if (url.includes('/lots/evaluations')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({
            lot_id: 'l1',
            member_count: 1,
            requested_markets: ['exportacao-estados-unidos'],
            commercial_outlook: 'PODE_VENDER',
            can_sell_to_any_requested_market: true,
            executive_summary: 'Resumo.',
            eligible_markets: ['exportacao-estados-unidos'],
            blocked_markets: [],
            conditioned_markets: [],
            indeterminate_markets: [],
            missing_markets: [],
            required_subjects: [],
            market_gaps: [],
            markets: [
              {
                market: 'exportacao-estados-unidos',
                status: 'ELEGIVEL',
                summary: 'Todos elegíveis.',
                dependency: null,
                eligible_animal_ids: ['a1'],
                blocked_animal_ids: [],
                conditioned_animal_ids: [],
                indeterminate_animal_ids: [],
                missing_animal_ids: [],
                animals: [],
              },
            ],
          }),
        })
      }
      void init
      return Promise.resolve({ ok: true, status: 200, json: async () => respostaLote() })
    })
    vi.stubGlobal('fetch', fetchMock)

    renderTela()
    await screen.findByText('LOTE-01', { exact: false })

    fireEvent.click(screen.getByRole('button', { name: /executar análise de mercado do lote/i }))

    expect(await screen.findByText(/PODE_VENDER/)).toBeInTheDocument()
    expect(screen.getByText(/Elegíveis \(1\)/)).toBeInTheDocument()
  })
})
