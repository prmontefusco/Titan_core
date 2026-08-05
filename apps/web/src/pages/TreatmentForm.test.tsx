import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TreatmentForm } from './TreatmentForm'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderFormulario() {
  return render(
    <MemoryRouter initialEntries={['/animals/a1/treatments/new']}>
      <Routes>
        <Route path="/animals/:animalId/treatments/new" element={<TreatmentForm {...options} />} />
        <Route path="/animals/:animalId" element={<p>Detalhe do animal a1</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

function mockFetchSequence(responses: unknown[]) {
  const fila = [...responses]
  return vi.fn().mockImplementation(() => {
    const proxima = fila.shift()
    if (proxima === undefined) throw new Error('fetch chamado mais vezes do que o esperado')
    return Promise.resolve(proxima)
  })
}

describe('TreatmentForm', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('registra o tratamento e navega para o detalhe do animal', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        {
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              {
                medication_id: 'm1',
                trade_name: 'Ivomec Gold',
                active_ingredient: 'Ivermectina',
                manufacturer: 'Boehringer',
                withdrawal_period_days: 30,
                product_class: 'ANTIPARASITARIO',
                dosage_instruction: null,
              },
            ],
            limit: 50,
            offset: 0,
            has_more: false,
          }),
        },
        {
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              {
                batch_id: 'b1',
                medication_id: 'm1',
                batch_number: 'LOTE-001',
                expiry_date: '2027-01-01T00:00:00Z',
                manufacturing_date: null,
              },
            ],
            limit: 50,
            offset: 0,
            has_more: false,
          }),
        },
        {
          ok: true,
          status: 201,
          json: async () => ({
            application_id: 'app-1',
            animal_id: 'a1',
            medication_batch_id: 'b1',
            applied_at: '2026-08-01T12:00:00Z',
            dose: null,
            prescription_id: null,
            sanitary_campaign_id: null,
            corrects_application_id: null,
          }),
        },
      ]),
    )

    renderFormulario()

    const medicamento = await screen.findByLabelText('Medicamento')
    fireEvent.change(medicamento, { target: { value: 'm1' } })

    const lote = await screen.findByLabelText('Lote')
    await waitFor(() => expect(lote).not.toBeDisabled())
    fireEvent.change(lote, { target: { value: 'b1' } })

    fireEvent.click(screen.getByRole('button', { name: /registrar aplicação/i }))

    expect(await screen.findByText('Detalhe do animal a1')).toBeInTheDocument()
  })

  it('mostra a mensagem de conflito do backend sem perder a seleção', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        {
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              {
                medication_id: 'm1',
                trade_name: 'Ivomec Gold',
                active_ingredient: 'Ivermectina',
                manufacturer: 'Boehringer',
                withdrawal_period_days: 30,
                product_class: 'ANTIPARASITARIO',
                dosage_instruction: null,
              },
            ],
            limit: 50,
            offset: 0,
            has_more: false,
          }),
        },
        {
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              {
                batch_id: 'b1',
                medication_id: 'm1',
                batch_number: 'LOTE-001',
                expiry_date: '2027-01-01T00:00:00Z',
                manufacturing_date: null,
              },
            ],
            limit: 50,
            offset: 0,
            has_more: false,
          }),
        },
        {
          ok: false,
          status: 409,
          json: async () => ({
            reason_code: 'CONFLITO_DE_DOMINIO',
            detail: 'applied_at não pode estar no futuro.',
          }),
        },
      ]),
    )

    renderFormulario()

    const medicamento = await screen.findByLabelText('Medicamento')
    fireEvent.change(medicamento, { target: { value: 'm1' } })

    const lote = await screen.findByLabelText('Lote')
    await waitFor(() => expect(lote).not.toBeDisabled())
    fireEvent.change(lote, { target: { value: 'b1' } })

    fireEvent.click(screen.getByRole('button', { name: /registrar aplicação/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/não pode estar no futuro/i)
    // A seleção continua visível -- o operador não perde o que preencheu.
    expect(screen.getByLabelText('Lote')).toHaveValue('b1')
  })
})
