import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MarketMatrix } from './MarketMatrix'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderTela(animalId = 'a1') {
  return render(
    <MemoryRouter initialEntries={[`/animals/${animalId}/market-matrix`]}>
      <Routes>
        <Route path="/animals/:animalId/market-matrix" element={<MarketMatrix {...options} />} />
      </Routes>
    </MemoryRouter>,
  )
}

function respostaBase(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    animal_id: 'a1',
    requested_markets: ['exportacao-estados-unidos'],
    commercial_outlook: 'PODE_VENDER',
    can_sell_to_any_requested_market: true,
    executive_summary: 'O animal pode ser vendido para os EUA.',
    eligible_markets: ['exportacao-estados-unidos'],
    blocked_markets: [],
    conditioned_markets: [],
    indeterminate_markets: [],
    missing_markets: [],
    required_subjects: [],
    market_gaps: [],
    evaluation_id: 'ev1',
    decision_id: 'dec1',
    dossier_id: 'dos1',
    markets: [
      {
        market: 'exportacao-estados-unidos',
        status: 'ELEGIVEL',
        projection_status: 'ATUAL',
        summary: 'Elegível para os EUA.',
        dependency: null,
        gaps: [],
        reasons: [],
      },
    ],
    ...overrides,
  }
}

describe('MarketMatrix', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('não executa nada até o operador clicar', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    renderTela()

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('mostra o resumo e os mercados depois de executar', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => respostaBase(),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /executar análise de mercado/i }))

    expect(await screen.findByText(/PODE_VENDER/)).toBeInTheDocument()
    expect(screen.getByText(/exportacao-estados-unidos/)).toBeInTheDocument()
    expect(screen.getByText(/Elegível para os EUA/)).toBeInTheDocument()
  })

  it('mostra o seletor de estabelecimento quando há dependência não escolhida, e reavalia', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () =>
          respostaBase({
            commercial_outlook: 'CONDICIONADO',
            markets: [
              {
                market: 'exportacao-china',
                status: 'CONDICIONADO',
                projection_status: 'ATUAL',
                summary: 'Depende do frigorífico.',
                dependency: {
                  subject_key: 'slaughterhouse',
                  subject_label: 'estabelecimento',
                  selected_subject_id: null,
                },
                gaps: [],
                reasons: [],
              },
            ],
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            {
              counterparty_id: 'c1',
              name: 'Frigorífico Escolhido',
              counterparty_type: 'SLAUGHTERHOUSE',
              identifiers: [],
              notes: null,
              created_at: '2026-08-05T00:00:00Z',
            },
          ],
          limit: 50,
          offset: 0,
          has_more: false,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () =>
          respostaBase({
            commercial_outlook: 'PODE_VENDER',
            markets: [
              {
                market: 'exportacao-china',
                status: 'ELEGIVEL',
                projection_status: 'ATUAL',
                summary: 'Elegível com o estabelecimento escolhido.',
                dependency: {
                  subject_key: 'slaughterhouse',
                  subject_label: 'estabelecimento',
                  selected_subject_id: 'c1',
                },
                gaps: [],
                reasons: [],
              },
            ],
          }),
      })
    vi.stubGlobal('fetch', fetchMock)

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /executar análise de mercado/i }))

    const seletor = await screen.findByLabelText(/estabelecimento ainda não escolhido/i)
    expect(await screen.findByText('Frigorífico Escolhido')).toBeInTheDocument()

    fireEvent.change(seletor, { target: { value: 'c1' } })
    fireEvent.click(screen.getByRole('button', { name: /reavaliar com estabelecimento/i }))

    expect(await screen.findByText(/Elegível com o estabelecimento escolhido/)).toBeInTheDocument()
    const terceiraChamada = fetchMock.mock.calls[2]
    expect(JSON.parse(terceiraChamada[1].body)).toEqual({
      animal_id: 'a1',
      slaughterhouse_counterparty_id: 'c1',
    })
  })

  it('mostra a nota de revisão humana necessária', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          reason_code: 'REVISAO_HUMANA_NECESSARIA',
          detail: 'A emissão automática foi recusada.',
          proposal_id: 'p1',
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /executar análise de mercado/i }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/revisão humana/i)
    expect(alerta).toHaveTextContent('p1')
  })
})
