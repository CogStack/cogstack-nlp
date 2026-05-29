import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCell from '@/components/metrics/MetricCell.vue'

describe('MetricCell.vue', () => {
  const mountCell = (props: Record<string, unknown> = {}) =>
    mount(MetricCell, {
      props: { value: 0.75, ...props },
      global: {
        stubs: {
          'v-progress-linear': {
            template: '<div class="stub-progress"><slot /></div>'
          }
        }
      }
    })

  it('formats value with default decimal places', () => {
    const wrapper = mountCell({ value: 0.756 })
    expect(wrapper.text()).toContain('0.76')
  })

  it('respects custom decimal places', () => {
    const wrapper = mountCell({ value: 0.756, decimals: 3 })
    expect(wrapper.text()).toContain('0.756')
  })

  it('applies good-perf class when value exceeds threshold', () => {
    const wrapper = mountCell({ value: 0.9, threshold: 0.4 })
    expect(wrapper.find('.good-perf').exists()).toBe(true)
  })

  it('does not apply good-perf class below threshold', () => {
    const wrapper = mountCell({ value: 0.2, threshold: 0.4 })
    expect(wrapper.find('.good-perf').exists()).toBe(false)
  })
})
