import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetaAnnotationsSummary from '@/components/common/MetaAnnotationsSummary.vue'

describe('MetaAnnotationsSummary.vue', () => {
  it('renders nothing when meta annotations are empty', () => {
    const wrapper = mount(MetaAnnotationsSummary, {
      props: { metaAnnotations: [] }
    })
    expect(wrapper.find('.meta-annotations-section').exists()).toBe(false)
  })

  it('renders tasks and confidence scores', () => {
    const metaAnnotations = [
      { task: 'Presence', value: 'Present', confidence: 0.9123 },
      { task: 'Subject', value: 'Patient', confidence: null }
    ]
    const wrapper = mount(MetaAnnotationsSummary, { props: { metaAnnotations } })

    expect(wrapper.text()).toContain('Meta Annotations')
    expect(wrapper.text()).toContain('Presence:')
    expect(wrapper.text()).toContain('Present')
    expect(wrapper.text()).toContain('score: 0.912')
    expect(wrapper.text()).toContain('Subject:')
    expect(wrapper.text()).toContain('Patient')
    expect(wrapper.text()).not.toContain('score: null')
  })
})
