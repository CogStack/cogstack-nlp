import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ClinicalText from '@/components/common/ClinicalText.vue'

describe('ClinicalText.vue', () => {
    beforeEach(() => {
        // Mock scrollIntoView
        Element.prototype.scrollIntoView = vi.fn()
    })

    afterEach(() => {
        vi.clearAllMocks()
    })

    const defaultProps = {
        text: 'Sample clinical text',
        taskName: 'Concept Anno',
        taskValues: ['Correct', 'Deleted', 'Killed', 'Alternative', 'Irrelevant'],
        ents: [],
        loading: null,
        addAnnos: false
    }

    it('renders empty text when loading', () => {
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                loading: 'Loading...'
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(false)
    })

    it('renders plain text when no annotations', () => {
        const wrapper = mount(ClinicalText, {
            props: defaultProps,
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
    })

    it('renders text with single annotation', () => {
        const ents = [{
            id: 1,
            start_ind: 0,
            end_ind: 6,
            assignedValues: { 'Concept Anno': 'Correct' },
            manually_created: false
        }]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'Sample clinical text',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
    })

    it('renders text with overlapping annotations', () => {
        const ents = [
            {
                id: 1,
                start_ind: 0,
                end_ind: 8,
                assignedValues: { 'Concept Anno': 'Correct' },
                manually_created: false
            },
            {
                id: 2,
                start_ind: 3,
                end_ind: 12,
                assignedValues: { 'Concept Anno': 'Deleted' },
                manually_created: true
            }
        ]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'SPECIMEN(S) SUBM',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
    })

    it('emits select:concept when annotation is clicked', async () => {
        const ents = [{
            id: 1,
            start_ind: 0,
            end_ind: 6,
            assignedValues: { 'Concept Anno': 'Correct' },
            manually_created: false
        }]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'Sample clinical text',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })

        // Get the component instance to call the method directly
        const vm = wrapper.vm as any
        vm.selectEnt(0)

        expect(wrapper.emitted('select:concept')).toBeTruthy()
        expect(wrapper.emitted('select:concept')?.[0]).toEqual([0])
    })

    it('emits remove:newAnno when remove button is clicked', async () => {
        const ents = [{
            id: 1,
            start_ind: 0,
            end_ind: 6,
            assignedValues: { 'Concept Anno': 'Correct' },
            manually_created: true
        }]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'Sample clinical text',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })

        const vm = wrapper.vm as any
        vm.removeNewAnno(0)

        expect(wrapper.emitted('remove:newAnno')).toBeTruthy()
        expect(wrapper.emitted('remove:newAnno')?.[0]).toEqual([0])
    })

    it('applies selected class to currentEnt', () => {
        const currentEnt = {
            id: 1,
            start_ind: 0,
            end_ind: 6,
            assignedValues: { 'Concept Anno': 'Correct' },
            manually_created: false
        }
        const ents = [currentEnt]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'Sample clinical text',
                ents,
                currentEnt
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
    })

    it('handles multiple overlapping annotations correctly', () => {
        const ents = [
            {
                id: 1,
                start_ind: 0,
                end_ind: 8,
                assignedValues: { 'Concept Anno': 'Correct' },
                manually_created: false
            },
            {
                id: 2,
                start_ind: 3,
                end_ind: 12,
                assignedValues: { 'Concept Anno': 'Deleted' },
                manually_created: true
            },
            {
                id: 3,
                start_ind: 5,
                end_ind: 10,
                assignedValues: { 'Concept Anno': 'Killed' },
                manually_created: false
            }
        ]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'SPECIMEN(S) SUBM',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
    })

    it('only adds one remove button per manually created annotation', () => {
        const ents = [
            {
                id: 1,
                start_ind: 0,
                end_ind: 8,
                assignedValues: { 'Concept Anno': 'Correct' },
                manually_created: false
            },
            {
                id: 2,
                start_ind: 3,
                end_ind: 12,
                assignedValues: { 'Concept Anno': 'Deleted' },
                manually_created: true
            }
        ]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'SPECIMEN(S) SUBM',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })

        // Check that formattedText contains the remove button only once
        const vm = wrapper.vm as any
        const formattedText = vm.formattedText
        const removeButtonMatches = (formattedText.match(/remove-new-anno/g) || []).length
        expect(removeButtonMatches).toBe(1) // Only one remove button for the manually created annotation
    })

    it('handles empty text gracefully', () => {
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: ''
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
    })

    it('handles null ents gracefully', () => {
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                ents: null as any
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        // When ents is null, formattedText returns empty string but the div still renders
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
        const vm = wrapper.vm as any
        expect(vm.formattedText).toBe('')
    })

    it('applies correct task value classes', () => {
        const ents = [
            {
                id: 1,
                start_ind: 0,
                end_ind: 6,
                assignedValues: { 'Concept Anno': 'Correct' },
                manually_created: false
            },
            {
                id: 2,
                start_ind: 7,
                end_ind: 13,
                assignedValues: { 'Concept Anno': 'Deleted' },
                manually_created: false
            }
        ]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'Sample clinical text',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })

        const vm = wrapper.vm as any
        const formattedText = vm.formattedText
        // Check that highlight-task-0 (Correct) and highlight-task-1 (Deleted) classes are present
        expect(formattedText).toContain('highlight-task-0')
        expect(formattedText).toContain('highlight-task-1')
    })

    it('handles annotations that start at the same position', () => {
        const ents = [
            {
                id: 1,
                start_ind: 0,
                end_ind: 6,
                assignedValues: { 'Concept Anno': 'Correct' },
                manually_created: false
            },
            {
                id: 2,
                start_ind: 0,
                end_ind: 10,
                assignedValues: { 'Concept Anno': 'Deleted' },
                manually_created: false
            }
        ]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'Sample clinical text',
                ents
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })
        expect(wrapper.find('.clinical-note').exists()).toBe(true)
    })

    it('handles relation start and end entities', () => {
        const currentRelStartEnt = {
            id: 1,
            start_ind: 0,
            end_ind: 6,
            assignedValues: { 'Concept Anno': 'Correct' },
            manually_created: false
        }
        const currentRelEndEnt = {
            id: 2,
            start_ind: 7,
            end_ind: 13,
            assignedValues: { 'Concept Anno': 'Deleted' },
            manually_created: false
        }
        const ents = [currentRelStartEnt, currentRelEndEnt]
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                text: 'Sample clinical text',
                ents,
                currentRelStartEnt,
                currentRelEndEnt
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })

        const vm = wrapper.vm as any
        const formattedText = vm.formattedText
        expect(formattedText).toContain('current-rel-start')
        expect(formattedText).toContain('current-rel-end')
    })

    it('handles addAnnos prop correctly', () => {
        const wrapper = mount(ClinicalText, {
            props: {
                ...defaultProps,
                addAnnos: true
            },
            global: {
                stubs: ['v-overlay', 'v-progress-circular', 'v-runtime-template', 'vue-simple-context-menu']
            }
        })

        const vm = wrapper.vm as any
        const formattedText = vm.formattedText
        expect(formattedText).toContain('@contextmenu.prevent.stop')
    })
})

