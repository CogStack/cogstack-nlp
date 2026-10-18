import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AnnoResult from '@/components/anns/AnnoResult.vue'

const runtimeStub = {
  props: ['template'],
  template: '<div class="runtime-template">{{ template }}</div>'
}

describe('AnnoResult.vue', () => {
  const docText = 'before <tag> {{asthma}} after more text'
  const start = docText.indexOf('asthma')
  const snakeCaseResult = {
    cui: '195967001',
    project_id: 3,
    document_id: 8,
    project_name: 'Clinic',
    document_name: 'Letter',
    source_value: 'asthma',
    text: 'context asthma context',
    start,
    end: start + 'asthma'.length,
    acc: 0.5
  }

  const mountResult = (props: Record<string, unknown> = {}) => {
    const resolve = vi.fn(() => ({ href: '/train-annotations/3/8' }))
    const wrapper = mount(AnnoResult, {
      props: {
        type: 'fn',
        docText,
        result: snakeCaseResult,
        ...props
      },
      global: {
        stubs: { 'v-runtime-template': runtimeStub },
        mocks: { $router: { resolve } }
      }
    })
    return { wrapper, resolve }
  }

  it('shows snake_case example fields and escapes text compiled into the template', () => {
    const { wrapper } = mountResult()
    expect(wrapper.find('.doc-name').text()).toBe('Letter')
    expect(wrapper.find('.source-value').text()).toBe('asthma')
    expect(wrapper.find('.accu').text()).toBe('0.500')

    const template = wrapper.find('.runtime-template').text()
    expect(template).toContain('highlight-task-1')
    expect(template).toContain('@click="openAnno"')
    expect(template).toContain('&lt;tag&gt;')
    expect(template).toContain('&#123;&#123;')
    expect(template).toContain('>asthma</span>')
    expect(template).toContain('&#125;&#125;')
    expect(template).not.toContain('<tag>')
    expect(template).not.toContain('{{')
  })

  it('still renders legacy spaced keys', () => {
    const { wrapper } = mountResult({
      type: 'tp',
      docText: 'alpha asthma omega',
      result: {
        cui: 'C001',
        'project id': 1,
        'document id': 2,
        'document name': 'Legacy note',
        'source value': 'asthma',
        text: 'alpha asthma omega',
        start: 6,
        end: 12,
        acc: 1
      }
    })
    expect(wrapper.find('.doc-name').text()).toBe('Legacy note')
    expect(wrapper.find('.runtime-template').text()).toContain('highlight-task-0')
  })

  it('uses the stored context when the full document text is missing', () => {
    const { wrapper } = mountResult({
      docText: undefined,
      result: {
        ...snakeCaseResult,
        text: 'seen <asthma> {{today}}'
      }
    })
    const template = wrapper.find('.runtime-template').text()
    expect(template).toContain('highlight-task-1')
    expect(template).toContain('seen &lt;')
    expect(template).toContain('>asthma</span>')
    expect(template).toContain('&gt; &#123;&#123;today&#125;&#125;')
    expect(template).not.toContain('<asthma>')
  })

  it('does not repeat the mention when the example end equals its start', () => {
    const doc = 'Patient is a 70-year-old female with prior history of lung cancer, status post upper lobectomy.'
    const start = doc.indexOf('lung cancer')
    const { wrapper } = mountResult({
      docText: doc,
      result: {
        ...snakeCaseResult,
        source_value: 'lung cancer',
        text: doc.slice(Math.max(0, start - 60), start + 60),
        start,
        end: start
      }
    })
    const template = wrapper.find('.runtime-template').text()
    const marker = '>lung cancer</span>'
    const at = template.indexOf(marker)
    expect(at).toBeGreaterThan(-1)
    expect(template.slice(at + marker.length)).toContain(', status post upper lobectomy.')
    expect(template.slice(at + marker.length)).not.toContain('lung cancer')
    expect(template.slice(0, at)).not.toContain('lung cancer')
  })

  it('highlights the centred mention when the context window repeats it', () => {
    const left = `prior asthma ${'x'.repeat(47)}`
    const context = `${left}asthma later`
    const { wrapper } = mountResult({
      docText: undefined,
      result: {
        ...snakeCaseResult,
        text: context,
        start: 80,
        end: 80
      }
    })
    const template = wrapper.find('.runtime-template').text()
    const marker = '>asthma</span>'
    const at = template.indexOf(marker)
    expect(template.slice(0, at)).toContain('prior asthma ')
    expect(template.slice(at + marker.length)).toBe(' later</span>')
  })

  it('opens the annotation from snake_case project and document ids', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const { wrapper, resolve } = mountResult()
    wrapper.vm.openAnno()
    expect(resolve).toHaveBeenCalledWith({
      path: '/train-annotations/3/8',
      query: { annoStart: start, annoEnd: start + 'asthma'.length }
    })
    expect(open).toHaveBeenCalledWith('/train-annotations/3/8', '_blank')
    open.mockRestore()
  })
})
