import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ConceptSummary from '@/components/metrics/ConceptSummary.vue'

const concepts = [
  {
    cui: 'C0001',
    concept_name: 'Low concept',
    concept_count: 8,
    variations: 2,
    value: ['low', 'low concept'],
    count_variations_ratio: 4,
    cui_f1: 0.2,
    cui_prec: 0.25,
    cui_rec: 0.2,
    tps: 1,
    fps: 3,
    fns: 4,
    tp_examples: [],
    fp_examples: [],
    fn_examples: []
  },
  {
    cui: 'C0002',
    concept_name: 'Strong concept',
    concept_count: 4,
    variations: 1,
    value: ['strong'],
    count_variations_ratio: 4,
    cui_f1: 1,
    cui_prec: 1,
    cui_rec: 1,
    tps: 4,
    fps: 0,
    fns: 0,
    tp_examples: [],
    fp_examples: [],
    fn_examples: []
  },
  {
    cui: 'C0003',
    concept_name: 'Mid concept',
    concept_count: 6,
    variations: 2,
    value: ['mid', 'middle'],
    count_variations_ratio: 3,
    cui_f1: 0.8,
    cui_prec: 0.8,
    cui_rec: 0.8,
    tps: 4,
    fps: 1,
    fns: 1,
    tp_examples: [],
    fp_examples: [],
    fn_examples: []
  }
]

const mountSummary = () => mount(ConceptSummary, {
  props: {
    items: concepts.map(concept => ({ ...concept, value: [...concept.value] })),
    docs2text: {}
  },
  global: {
    stubs: {
      'v-row': { template: '<div><slot /></div>' },
      'v-card': { template: '<section class="summary-card"><slot /></section>' },
      'v-card-title': { template: '<h3><slot /></h3>' },
      'v-card-text': { template: '<div><slot /></div>' },
      'v-tooltip': {
        template: '<span><slot name="activator" :props="{}" /><span class="tooltip-body"><slot /></span></span>'
      },
      'v-progress-linear': { template: '<div><slot /></div>' },
      'v-data-table': {
        props: ['items'],
        template: `
          <div>
            <div v-for="item in items" :key="item.cui" class="concept-row">
              <slot name="item.variation_values" :item="item" />
              <slot name="item.exclude" :item="item" />
            </div>
          </div>
        `
      },
      'font-awesome-icon': true,
      modal: true,
      'anno-result': true
    }
  }
})

describe('metrics ConceptSummary.vue', () => {
  it('recalculates scores when a low-performing concept is excluded and restored', async () => {
    const wrapper = mountSummary()

    expect(Number((wrapper.get('#low-f1-threshold').element as HTMLInputElement).value)).toBe(0.7)
    expect(wrapper.text()).toContain('66.7%')
    expect(wrapper.text()).toContain('Exclude 1 low performer')
    expect(wrapper.text()).not.toContain('full set')

    await wrapper.get('[aria-label="Exclude Low concept"]').trigger('click')

    expect(wrapper.text()).toContain('90.0%')
    expect(wrapper.text()).toContain('+23.3 pts')
    expect(wrapper.text()).toContain('full set 66.7%')
    expect(wrapper.text()).toContain('1 concept excluded from these scores')
    expect(wrapper.text()).toContain('2 of 3 concepts in these scores')
    expect(wrapper.find('[aria-label="Exclude Low concept"]').exists()).toBe(false)

    await wrapper.get('[aria-label="Restore Low concept"]').trigger('click')

    expect(wrapper.text()).toContain('66.7%')
    expect(wrapper.text()).not.toContain('full set')
    expect(wrapper.text()).toContain('3 of 3 concepts in these scores')
  })

  it('excludes every concept under the F1 threshold and can restore them together', async () => {
    const wrapper = mountSummary()

    await wrapper.get('#low-f1-threshold').setValue('0.9')
    await wrapper.get('button.btn-outline-danger').trigger('click')

    expect(wrapper.text()).toContain('100.0%')
    expect(wrapper.text()).toContain('2 concepts excluded from these scores')
    expect(wrapper.text()).toContain('Low concept')
    expect(wrapper.text()).toContain('Mid concept')
    expect(wrapper.find('[aria-label="Exclude Strong concept"]').exists()).toBe(true)

    await wrapper.get('button.btn-outline-primary').trigger('click')

    expect(wrapper.text()).toContain('3 of 3 concepts in these scores')
    expect(wrapper.text()).not.toContain('excluded from these scores')
  })

  it('keeps a long variation list on one line and shows the full set in the tooltip', () => {
    const many = Array.from({ length: 12 }, (_, index) => `variation term ${index} with extra words`)
    const wrapper = mount(ConceptSummary, {
      props: {
        items: [{
          ...concepts[0],
          value: many
        }],
        docs2text: {}
      },
      global: {
        stubs: {
          'v-row': { template: '<div><slot /></div>' },
          'v-card': { template: '<section class="summary-card"><slot /></section>' },
          'v-card-title': { template: '<h3><slot /></h3>' },
          'v-card-text': { template: '<div><slot /></div>' },
          'v-tooltip': {
            template: '<span><slot name="activator" :props="{}" /><span class="tooltip-body"><slot /></span></span>'
          },
          'v-progress-linear': { template: '<div><slot /></div>' },
          'v-data-table': {
            props: ['items'],
            template: `
              <div>
                <div v-for="item in items" :key="item.cui">
                  <slot name="item.variation_values" :item="item" />
                </div>
              </div>
            `
          },
          'font-awesome-icon': true,
          modal: true,
          'anno-result': true
        }
      }
    })

    const preview = wrapper.get('.variation-values').text()
    expect(preview).toBe('variation term 0 with extra…, variation term 1 with extra… +10')
    expect(preview).not.toContain('variation term 11')
    expect(wrapper.get('.tooltip-body').text()).toContain(many[11])
  })

  it('shows an em dash when every concept is excluded', async () => {
    const wrapper = mountSummary()
    const vm = wrapper.vm as unknown as {
      excludeConcept: (item: { cui: string, concept_name: string }) => void
      includedItems: Array<{ cui: string, concept_name: string }>
    }

    vm.includedItems.forEach(item => vm.excludeConcept(item))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('0 of 3 concepts in these scores')
    expect(wrapper.text()).toContain('—')
  })
})
