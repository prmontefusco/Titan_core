import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CommercialExplanation } from './CommercialExplanation'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderTela(animalId = 'a1') {
  return render(
    <MemoryRouter initialEntries={[`/animals/${animalId}/commercial-explanation`]}>
      <Routes>
        <Route
          path="/animals/:animalId/commercial-explanation"
          element={<CommercialExplanation {...options} />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

function renderTelaDeLote(lotId = 'l1') {
  return render(
    <MemoryRouter initialEntries={[`/lots/${lotId}/commercial-explanation`]}>
      <Routes>
        <Route
          path="/lots/:lotId/commercial-explanation"
          element={<CommercialExplanation {...options} />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CommercialExplanation', () => {
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

  it('mostra a narrativa e o detalhe por mercado depois de executar', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => ({
          subject_type: 'animal',
          subject_id: 'a1',
          requested_markets: ['exportacao-estados-unidos'],
          commercial_outlook: 'PODE_VENDER',
          can_sell_to_any_requested_market: true,
          executive_summary: 'Resumo executivo.',
          narrative: 'O animal pode ser vendido para os EUA agora.',
          recommended_next_action: 'Nenhuma ação necessária.',
          markets: [
            {
              market: 'exportacao-estados-unidos',
              status: 'ELEGIVEL',
              summary: 'Elegível.',
              why: ['Todos os requisitos foram atendidos.'],
              next_action: null,
              affected_animal_ids: [],
            },
          ],
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /gerar explicação comercial/i }))

    expect(await screen.findByText(/PODE_VENDER/)).toBeInTheDocument()
    expect(screen.getByText(/pode ser vendido para os EUA agora/)).toBeInTheDocument()
    expect(screen.getByText(/Todos os requisitos foram atendidos/)).toBeInTheDocument()
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
    fireEvent.click(screen.getByRole('button', { name: /gerar explicação comercial/i }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/revisão humana/i)
    expect(alerta).toHaveTextContent('p1')
  })

  it('funciona para lote, chamando com lot_id e linkando animais afetados', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        subject_type: 'lot',
        subject_id: 'l1',
        requested_markets: ['exportacao-estados-unidos'],
        commercial_outlook: 'INCONCLUSIVO',
        can_sell_to_any_requested_market: false,
        executive_summary: 'Resumo do lote.',
        narrative: 'Alguns animais do lote ainda não podem ser avaliados.',
        recommended_next_action: null,
        markets: [
          {
            market: 'exportacao-estados-unidos',
            status: 'INDETERMINADO',
            summary: 'Parcialmente avaliado.',
            why: [],
            next_action: null,
            affected_animal_ids: ['a1', 'a2'],
          },
        ],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderTelaDeLote()
    fireEvent.click(screen.getByRole('button', { name: /gerar explicação comercial/i }))

    expect(await screen.findByText(/INCONCLUSIVO/)).toBeInTheDocument()
    expect(screen.getByText('a1')).toBeInTheDocument()
    expect(screen.getByText('a2')).toBeInTheDocument()

    const chamada = fetchMock.mock.calls[0]
    expect(JSON.parse(chamada[1].body)).toEqual({
      animal_id: null,
      lot_id: 'l1',
      slaughterhouse_counterparty_id: null,
    })
  })
})
