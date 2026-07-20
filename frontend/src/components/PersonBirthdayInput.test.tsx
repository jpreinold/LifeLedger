import { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PersonBirthdayInput } from './PersonBirthdayInput'

describe('PersonBirthdayInput', () => {
  it('calculates birth year from turning age and can switch back to birth year as the source', () => {
    const onChange = vi.fn()
    const onInferredBirthYearChange = vi.fn()
    render(
      <PersonBirthdayInput
        subjectName="Jasmine"
        value={null}
        onChange={onChange}
        onInferredBirthYearChange={onInferredBirthYearChange}
      />,
    )

    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '12' } })
    fireEvent.change(screen.getByLabelText('Day'), { target: { value: '31' } })
    fireEvent.change(screen.getByLabelText('Turning age'), { target: { value: '31' } })

    const today = new Date()
    const thisBirthday = new Date(today.getFullYear(), 11, 31)
    const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
    const dueYear = thisBirthday < todayStart ? today.getFullYear() + 1 : today.getFullYear()
    expect(screen.getByLabelText('Birth Year')).toHaveValue(String(dueYear - 31))
    expect(onChange).toHaveBeenLastCalledWith('--12-31')
    expect(onInferredBirthYearChange).toHaveBeenLastCalledWith(dueYear - 31)
    expect(screen.getByText('Calculated')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Birth Year'), { target: { value: String(dueYear - 40) } })

    expect(screen.getByLabelText('Turning age')).toHaveValue('40')
    expect(onChange).toHaveBeenLastCalledWith(`${dueYear - 40}-12-31`)
    expect(onInferredBirthYearChange).toHaveBeenLastCalledWith(null)
  })

  it('sets the month and day to today without requiring the user to know the date', () => {
    const onChange = vi.fn()
    render(<PersonBirthdayInput value={null} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Use today' }))

    const today = new Date()
    expect(screen.getByLabelText('Month')).toHaveValue(String(today.getMonth() + 1))
    expect(screen.getByLabelText('Day')).toHaveValue(String(today.getDate()))
    expect(onChange).toHaveBeenLastCalledWith(`--${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`)
  })

  it('preserves age-at-next-birthday when parent props echo each calculated change', () => {
    function Harness() {
      const [birthday, setBirthday] = useState<string | null>(null)
      const [inferredBirthYear, setInferredBirthYear] = useState<number | null>(null)
      return (
        <PersonBirthdayInput
          value={birthday}
          inferredBirthYear={inferredBirthYear}
          onChange={(value) => setBirthday(typeof value === 'string' ? value : null)}
          onInferredBirthYearChange={setInferredBirthYear}
        />
      )
    }

    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Day'), { target: { value: '19' } })
    fireEvent.change(screen.getByLabelText('Turning age'), { target: { value: '29' } })
    fireEvent.click(screen.getByRole('button', { name: 'Use today' }))

    expect(screen.getByLabelText('Turning age')).toHaveValue('29')
    expect(screen.getByLabelText('Birth Year')).not.toHaveValue('')
  })
})
