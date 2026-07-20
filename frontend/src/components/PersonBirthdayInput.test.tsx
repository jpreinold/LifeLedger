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

    expect(screen.getByLabelText('Turning age')).toHaveValue(40)
    expect(onChange).toHaveBeenLastCalledWith(`${dueYear - 40}-12-31`)
    expect(onInferredBirthYearChange).toHaveBeenLastCalledWith(null)
  })
})
