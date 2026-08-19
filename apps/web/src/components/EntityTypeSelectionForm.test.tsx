import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { EntityTypeSelectionForm } from './EntityTypeSelectionForm'

describe('EntityTypeSelectionForm', () => {
  it('explica que o pedido é submetido à organização piloto e envia o tipo escolhido', () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)

    render(<EntityTypeSelectionForm onSubmit={onSubmit} />)

    expect(screen.getByText(/organização piloto configurada neste ambiente/i)).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Veterinário'))
    fireEvent.click(screen.getByRole('button', { name: 'Solicitar acesso' }))

    expect(onSubmit).toHaveBeenCalledWith('VETERINARIO')
  })
})
