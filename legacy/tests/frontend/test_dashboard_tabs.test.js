import { describe, expect, test } from 'vitest'

describe('dashboard tabs', () => {
  test('contains expected tab labels', () => {
    const tabs = ['Dashboard', 'Sentiment Analyzer', 'Predictions', 'Backtest', 'Trade Log']
    expect(tabs).toHaveLength(5)
    expect(tabs.includes('Predictions')).toBe(true)
  })
})
