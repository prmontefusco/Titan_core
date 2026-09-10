import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnimalTimeline } from './AnimalTimeline'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderTimeline(animalId = 'a1') {
  return render(
    <MemoryRouter initialEntries={[`/animals/${animalId}/timeline`]}>
      <Routes>
        <Route path="/animals/:animalId/timeline" element={<AnimalTimeline {...options} />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnimalTimeline', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('mostra eventos históricos e preserva o retorno para o animal', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          animal_id: 'a1',
          known_until: '2026-09-10T12:00:00Z',
          entry_count: 1,
          entries: [
            {
              occurred_at: '2026-09-10T10:00:00Z',
              recorded_at: '2026-09-10T10:01:00Z',
              entry_type: 'TREATMENT_APPLIED',
              source_kind: 'TREATMENT',
              aggregate_type: 'treatment_application',
              aggregate_id: 't1',
              superseded_by: null,
            },
          ],
        }),
      }),
    )

    renderTimeline()

    expect(await screen.findByText('TREATMENT_APPLIED')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /voltar para o animal/i })).toHaveAttribute('href', '/animals/a1')
    expect(screen.getByText(/eventos conhecidos/i)).toBeInTheDocument()
  })

  it('mostra mensagem clara quando falta permissão (403)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ reason_code: 'PERMISSAO_AUSENTE', detail: 'sem permissão' }),
      }),
    )

    renderTimeline()

    expect(await screen.findByRole('alert')).toHaveTextContent(/não tem permissão/i)
  })
})
