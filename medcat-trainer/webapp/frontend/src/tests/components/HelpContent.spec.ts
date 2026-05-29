import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HelpContent from '@/components/usecases/HelpContent.vue'

describe('HelpContent.vue', () => {
  const descriptions = {
    Presence: {
      description: 'Whether the entity is present.',
      values: {
        Present: 'Entity is present in text',
        Absent: 'Entity is negated or absent'
      }
    }
  }

  it('renders task descriptions and value help table', () => {
    const wrapper = mount(HelpContent, {
      props: { descriptions }
    })

    expect(wrapper.text()).toContain('Task: Presence')
    expect(wrapper.text()).toContain('Whether the entity is present.')
    expect(wrapper.text()).toContain('Present')
    expect(wrapper.text()).toContain('Entity is present in text')
    expect(wrapper.text()).toContain('Absent')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })

  it('renders multiple tasks when provided', () => {
    const wrapper = mount(HelpContent, {
      props: {
        descriptions: {
          ...descriptions,
          Subject: {
            description: 'Who the finding applies to.',
            values: { Patient: 'The patient' }
          }
        }
      }
    })

    expect(wrapper.text()).toContain('Task: Presence')
    expect(wrapper.text()).toContain('Task: Subject')
    expect(wrapper.findAll('h4')).toHaveLength(2)
  })
})
