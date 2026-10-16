import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ConceptSummary from '@/components/metrics/ConceptSummary.vue'
import conceptSummarySource from '@/components/metrics/ConceptSummary.vue?raw'
import metricsSource from '@/views/Metrics.vue?raw'

const fnExample = {
  cui: '195967001',
  project_id: 7,
  document_id: '10',
  document_name: 'Clinic letter',
  source_value: 'asthma',
  text: 'has asthma today',
  start: 4,
  end: 10,
  acc: 0.91
}

const sourceRow = {
  concept_name: 'Asthma',
  cui: '195967001',
  concept_count: 3,
  variations: 1,
  value: ['asthma'],
  count_variations_ratio: 3,
  cui_f1: 0.5,
  cui_prec: 0.5,
  cui_rec: 0.5,
  tps: 1,
  fns: 1,
  fps: 2,
  tp_examples: [],
  fn_examples: [fnExample],
  fp_examples: [fnExample, { ...fnExample, source_value: 'wheeze' }]
}

const tableStub = {
  props: ['items'],
  template: `
    <div>
      <div v-for="(item, index) in items" :key="index">
        <slot name="item.tps" :item="item" />
        <slot name="item.fns" :item="item" />
        <slot name="item.fps" :item="item" />
      </div>
    </div>
  `
}

const mountSummary = (items = [sourceRow]) =>
  mount(ConceptSummary, {
    props: {
      items,
      docs2text: { 10: 'xxhas asthma today and <script> {{x}}' }
    },
    global: {
      stubs: {
        'font-awesome-icon': true,
        'v-row': { template: '<div><slot /></div>' },
        'v-card': { template: '<div><slot /></div>' },
        'v-card-title': { template: '<div><slot /></div>' },
        'v-card-text': { template: '<div><slot /></div>' },
        'v-tooltip': true,
        'v-progress-linear': { template: '<div><slot /></div>' },
        'v-runtime-template': {
          props: ['template'],
          template: '<span class="runtime-template">{{ template }}</span>'
        },
        'v-data-table': tableStub
      }
    },
    attachTo: document.body
  })

describe('metrics ConceptSummary.vue', () => {
  it('paints non-zero TP, FN, and FP counts green, grey, and red', () => {
    const wrapper = mountSummary()
    const zero = mountSummary([{ ...sourceRow, tps: 0, fns: 0, fps: 0 }])

    expect(wrapper.get('button.tp-count').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('button.fn-count').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('button.fp-count').attributes('disabled')).toBeUndefined()
    expect(zero.get('button.tp-count').attributes('disabled')).toBeDefined()
    expect(zero.get('button.fn-count').attributes('disabled')).toBeDefined()
    expect(zero.get('button.fp-count').attributes('disabled')).toBeDefined()

    // jsdom does not apply Vue SFC CSS, so lock the variable declarations the browser uses.
    expect(metricsSource).toContain('--success: #{map-get($theme-colors, "success")}')
    expect(metricsSource).toContain('--warning: #{map-get($theme-colors, "warning")}')
    expect(metricsSource).toContain('--danger: #{map-get($theme-colors, "danger")}')
    expect(conceptSummarySource).toContain('color: var(--success) !important')
    expect(conceptSummarySource).toContain('color: var(--warning) !important')
    expect(conceptSummarySource).toContain('color: var(--danger) !important')

    wrapper.unmount()
    zero.unmount()
  })

  it('opens the example dialog when an FN count is clicked', async () => {
    const wrapper = mountSummary()
    await wrapper.find('button.fn-count').trigger('click')
    await flushPromises()

    expect(wrapper.vm.showModal).toBe(true)
    expect(document.body.textContent).toContain('False Negative Model Predictions')
    expect(document.body.textContent).toContain('Clinic letter')
    expect(document.body.textContent).toContain('asthma')
    wrapper.unmount()
  })

  it('opens FP examples when the table row is not the same object as the source row', async () => {
    const wrapper = mountSummary()
    const copy = {
      concept_name: sourceRow.concept_name,
      cui: sourceRow.cui,
      tps: sourceRow.tps,
      fns: sourceRow.fns,
      fps: sourceRow.fps
    }

    wrapper.vm.openExamples('fp_examples', copy)
    await flushPromises()

    expect(wrapper.vm.showModal).toBe(true)
    expect(wrapper.vm.modalData.type).toBe('fp')
    expect(wrapper.vm.modalData.results).toHaveLength(2)
    expect(document.body.textContent).toContain('False Positive Model Predictions')
    wrapper.unmount()
  })

  it('reads examples from a v-data-table internal item wrapper', async () => {
    const wrapper = mountSummary()
    wrapper.vm.openExamples('fn_examples', { type: 'item', raw: sourceRow, columns: {} })
    await flushPromises()

    expect(wrapper.vm.showModal).toBe(true)
    expect(wrapper.vm.modalData.results).toEqual(sourceRow.fn_examples)
    wrapper.unmount()
  })

  it('does not throw when the clicked row has no stored examples', async () => {
    const wrapper = mountSummary([{ ...sourceRow, fp_examples: [], fps: 0 }])
    wrapper.vm.openExamples('fp_examples', { cui: 'missing', concept_name: 'Missing', fps: 1 })
    await flushPromises()

    expect(wrapper.vm.showModal).toBe(true)
    expect(wrapper.vm.modalData.results).toEqual([])
    wrapper.unmount()
  })
})
