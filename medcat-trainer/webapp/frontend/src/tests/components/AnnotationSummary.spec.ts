import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AnnotationSummary from '@/components/common/AnnotationSummary.vue'

const docText = 'The patient has diabetes mellitus today.'
const annos = [
  {
    id: 1,
    start_ind: 16,
    end_ind: 33,
    value: 'diabetes mellitus',
    cui: 'C0011860',
    pretty_name: 'Diabetes mellitus',
    icd10: [{ code: 'E11', desc: 'Type 2 diabetes' }],
    correct: true,
    deleted: false,
    killed: false,
    alternative: false,
    manually_created: false
  },
  {
    id: 2,
    start_ind: 4,
    end_ind: 11,
    value: 'patient',
    cui: 'C0030705',
    pretty_name: 'Patients',
    icd10: [],
    manually_created: true,
    deleted: false,
    killed: false,
    alternative: false,
    correct: false
  }
]

describe('AnnotationSummary.vue', () => {
  const mountSummary = (props: Record<string, unknown> = {}) =>
    mount(AnnotationSummary, {
      props: {
        annos,
        currentDoc: { text: docText },
        taskIDs: [],
        ...props
      },
      global: {
        stubs: {}
      }
    })

  it('renders annotation rows with concept details', () => {
    const wrapper = mountSummary()
    expect(wrapper.text()).toContain('diabetes mellitus')
    expect(wrapper.text()).toContain('C0011860')
    expect(wrapper.text()).toContain('Diabetes mellitus')
  })

  it('shows ICD-10 column when annotations include codes', () => {
    const wrapper = mountSummary()
    expect(wrapper.text()).toContain('ICD-10')
    expect(wrapper.text()).toContain('E11 | Type 2 diabetes')
  })

  it('hides ICD-10 column when no annotations have codes', () => {
    const wrapper = mountSummary({
      annos: [{ ...annos[1], icd10: [] }]
    })
    expect(wrapper.text()).not.toContain('ICD-10')
  })

  it('leftContext and rightContext extract surrounding text', () => {
    const wrapper = mountSummary()
    const vm = wrapper.vm as {
      leftContext: (c: (typeof annos)[0]) => string
      rightContext: (c: (typeof annos)[0]) => string
    }
    expect(vm.leftContext(annos[0])).toBe('The patient has ')
    expect(vm.rightContext(annos[0])).toBe(' today.')
  })

  it('highlightClass reflects annotation state', () => {
    const wrapper = mountSummary()
    const vm = wrapper.vm as { highlightClass: (c: (typeof annos)[0]) => Record<string, boolean> }
    expect(vm.highlightClass(annos[0])).toMatchObject({ 'highlight-task-0': true })
    expect(vm.highlightClass(annos[1])).toMatchObject({ 'highlight-task-new': true })
  })

  it('emits select:AnnoSummaryConcept with annotation index on row click', async () => {
    const wrapper = mountSummary()
    await wrapper.find('tbody tr').trigger('click')
    expect(wrapper.emitted('select:AnnoSummaryConcept')?.[0]).toEqual([0])
  })
})
