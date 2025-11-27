<template>
  <div class="note-container">
    <v-overlay :model-value="loading !== null"
               class="align-center justify-center"
               color="primary"
               activator="parent"
               :disabled="true"
               :persistent="true">
      <v-progress-circular indeterminate color="primary"></v-progress-circular>
      <span class="overlay-message">{{loading}}</span>
    </v-overlay>
    <div v-if="!loading" class="clinical-note">
      <v-runtime-template ref="clinicalText" :template="formattedText"></v-runtime-template>
    </div>
    <vue-simple-context-menu
      :elementId="'ctxMenuId'"
      :options="ctxMenuOptions"
      ref="ctxMenu"
      @option-clicked="ctxOptionClicked">
    </vue-simple-context-menu>
  </div>
</template>

<script>
import VRuntimeTemplate from "vue3-runtime-template"
import VueSimpleContextMenu from 'vue-simple-context-menu'
import _ from 'lodash'

export default {
  name: 'ClinicalText',
  components: {
    VRuntimeTemplate,
    VueSimpleContextMenu
  },
  props: {
    text: String,
    taskName: String,
    taskValues: Array,
    task: Object,
    ents: Array,
    loading: String,
    currentEnt: Object,
    currentRelStartEnt: {
      default () {
        return {}
      },
      type: Object,
    },
    currentRelEndEnt: {
      default () {
        return {}
      },
      type: Object,
    },
    addAnnos: Boolean
  },
  emits: [
    'select:concept',
    'select:addSynonym',
    'remove:newAnno'
  ],
  data () {
    return {
      ctxMenuOptions: [
        {
          name: 'Add Term'
        }
      ],
      selection: null
    }
  },
  computed: {
    formattedText () {
      if (this.loading || !this.text || !this.ents) { return '' }
      if (this.ents.length === 0) {
        let text = this.text.replace('&', '&amp').replace('<', '&gt').replace('>', '&gt')
        text = text === 'nan' ? '' : text
        return this.addAnnos ? `<div @contextmenu.prevent.stop="showCtxMenu($event)">${text}</div>` : `<div>${text}</div>`
      }

      // Sort entities by start_ind, then by end_ind (longer first for same start)
      // Preserve original index for click handlers
      const sortedEnts = this.ents.map((ent, origIdx) => ({ ent, origIdx })).sort((a, b) => {
        if (a.ent.start_ind !== b.ent.start_ind) {
          return a.ent.start_ind - b.ent.start_ind
        }
        return b.ent.end_ind - a.ent.end_ind // Longer spans first when same start
      })

      const taskHighlightDefault = 'highlight-task-default'
      let timeout = 0

      // Create events for start and end of each annotation
      const events = []
      sortedEnts.forEach((entData, i) => {
        const ent = entData.ent
        const origIdx = entData.origIdx
        events.push({ pos: ent.start_ind, type: 'start', entIndex: i, origIndex: origIdx, ent: ent })
        events.push({ pos: ent.end_ind, type: 'end', entIndex: i, origIndex: origIdx, ent: ent })
      })
      events.sort((a, b) => {
        if (a.pos !== b.pos) {
          return a.pos - b.pos
        }
        // At same position, process starts before ends
        if (a.type !== b.type) {
          return a.type === 'start' ? -1 : 1
        }
        return 0
      })

      let formattedText = ''
      let currentPos = 0
      const activeEnts = [] // Stack of active entities (ordered by when they were opened)

      // Helper function to get style class for an entity
      const getStyleClass = (ent, origIndex) => {
        let styleClass = taskHighlightDefault
        if (ent.assignedValues[this.taskName] !== null) {
          let btnIndex = this.taskValues.indexOf(ent.assignedValues[this.taskName])
          styleClass = `highlight-task-${btnIndex}`
        }

        if (ent.id === this.currentRelStartEnt.id) {
          styleClass += ' current-rel-start'
        } else if (ent.id === this.currentRelEndEnt.id) {
          styleClass += ' current-rel-end'
        }

        if (ent === this.currentEnt) {
          styleClass += ' highlight-task-selected'
          timeout = origIndex === 0 ? 500 : timeout
        }
        return styleClass
      }

      // Helper function to build opening span tag
      const buildOpenSpan = (ent, origIndex) => {
        const styleClass = getStyleClass(ent, origIndex)
        return `<span @click.stop="selectEnt(${origIndex})" class="${styleClass}">`
      }

      // Helper function to build closing span tag with optional remove button
      const buildCloseSpan = (ent, origIndex, isInnermost) => {
        let removeButtonEl = ''
        if (isInnermost && ent.manually_created) {
          removeButtonEl = `<font-awesome-icon icon="times" class="remove-new-anno" @click.stop="removeNewAnno(${origIndex})"></font-awesome-icon>`
        }
        return `${removeButtonEl}</span>`
      }

      for (const event of events) {
        // Handle start events first (before adding text)
        if (event.type === 'start') {
          // Add any text up to this point
          if (event.pos > currentPos) {
            const textSegment = this.text.slice(currentPos, event.pos)
            if (textSegment.length > 0) {
              formattedText += _.escape(textSegment)
            }
            currentPos = event.pos
          }
          // Open the span for this annotation
          formattedText += buildOpenSpan(event.ent, event.origIndex)
          activeEnts.push({ entIndex: event.entIndex, origIndex: event.origIndex, ent: event.ent })
        } else if (event.type === 'end') {
          // Close the span (in reverse order to maintain nesting)
          const index = activeEnts.findIndex(ae => ae.entIndex === event.entIndex)
          if (index !== -1) {
            // If this is not the innermost span, we need to handle overlapping text
            if (index < activeEnts.length - 1) {
              // Add text up to the end position while all spans are still active
              // This text is inside all active spans including this one
              if (event.pos > currentPos) {
                const textSegment = this.text.slice(currentPos, event.pos)
                if (textSegment.length > 0) {
                  formattedText += _.escape(textSegment)
                }
                currentPos = event.pos
              }
              // Close all inner spans (from innermost to the one after this)
              // Don't add remove buttons here - these are temporary closes for nesting
              // We'll add remove buttons only when we reach the actual end position
              for (let j = activeEnts.length - 1; j > index; j--) {
                const innerData = activeEnts[j]
                // Always pass false here - these are temporary closes, not final ends
                formattedText += buildCloseSpan(innerData.ent, innerData.origIndex, false)
              }
              // Close this span (temporary close, no remove button)
              formattedText += buildCloseSpan(event.ent, event.origIndex, false)
              // Reopen inner spans (in the same order) so text after this position is inside them
              for (let j = index + 1; j < activeEnts.length; j++) {
                const innerData = activeEnts[j]
                formattedText += buildOpenSpan(innerData.ent, innerData.origIndex)
              }
            } else {
              // This is the innermost span at its final end position
              // Add text then close it with remove button if needed
              if (event.pos > currentPos) {
                const textSegment = this.text.slice(currentPos, event.pos)
                if (textSegment.length > 0) {
                  formattedText += _.escape(textSegment)
                }
                currentPos = event.pos
              }
              // Only add remove button when closing at the actual end position
              formattedText += buildCloseSpan(event.ent, event.origIndex, true)
            }
            activeEnts.splice(index, 1)
          }
        }
      }

      // Add remaining text after all events
      if (currentPos < this.text.length) {
        const textSegment = this.text.slice(currentPos)
        if (textSegment.length > 0) {
          formattedText += _.escape(textSegment)
        }
        // Close any remaining active spans (in reverse order)
        for (let j = activeEnts.length - 1; j >= 0; j--) {
          const activeData = activeEnts[j]
          const isInnermost = j === activeEnts.length - 1
          formattedText += buildCloseSpan(activeData.ent, activeData.origIndex, isInnermost)
        }
      }

      formattedText = this.addAnnos ? `<div @contextmenu.prevent.stop="showCtxMenu($event)">${formattedText}</div>` : `<div>${formattedText}</div>`
      this.scrollIntoView(timeout)
      return formattedText
    }
  },
  methods: {
    scrollIntoView  (timeout) {
      let el = document.getElementsByClassName('highlight-task-selected')
      setTimeout(function () { // setTimeout to put this into event queue
        if (el[0]) {
          el[0].scrollIntoView({
            block: 'nearest',
            behavior: 'smooth'
          })
        }
      }, timeout)
    },
    selectEnt  (entIdx) {
      this.$emit('select:concept', entIdx)
    },
    showCtxMenu  (event) {
      const selection = window.getSelection()
      const selStr = selection.toString().trim()
      const anchor = selection.anchorNode
      const focus = selection.focusNode

      if (selStr.length > 0 && focus !== null && focus.data) {
        let nextText = focus.data.slice(selection.focusOffset)
        let nextSibling = focus.nextSibling || focus.parentElement.nextSibling
        let priorText = anchor.data.slice(0, selection.anchorOffset)
        let priorSibling = anchor.previousSibling || anchor.parentElement.previousSibling

        let sameNode = anchor.compareDocumentPosition(focus) === 0
        let focusProceedingAnchor = anchor.compareDocumentPosition(focus) === 2
        if (!sameNode) {
          if (focusProceedingAnchor) {
            priorText = focus.data.slice(0, selection.focusOffset)
            priorSibling = focus.previousSibling || focus.parentElement.previousSibling
            nextText = anchor.data.slice(selection.anchorOffset)
            nextSibling = anchor.nextSibling || anchor.parentElement.nextSibling
          }
        } else if (selection.anchorOffset > selection.focusOffset) {
          priorText = anchor.data.slice(0, selection.focusOffset)
          nextText = anchor.data.slice(selection.anchorOffset)
        }

        let i = 0
        while (priorSibling !== null) {
          priorText = `${priorSibling.innerText || priorSibling.textContent}${priorText}`
          priorSibling = priorSibling.previousSibling
          i++
        }
        i = 0
        while (nextSibling !== null && i < 15) {
          nextText += (nextSibling.innerText || nextSibling.textContent)
          nextSibling = nextSibling.nextSibling
          i++
        }

        // occurrences of the selected string in the text before.
        let selectionOcurrenceIdx = 0
        let idx = 0
        while (idx !== -1) {
          idx = priorText.indexOf(selStr, idx)
          if (idx !== -1) {
            idx += selStr.length
            selectionOcurrenceIdx += 1
          }
        }

        // take only 100 chars of either side?
        nextText = nextText.length < 100 ? nextText : nextText.slice(0, 100)
        priorText = priorText.length < 15 ? priorText : priorText.slice(-15)
        this.selection = {
          selStr: selStr,
          prevText: priorText,
          nextText: nextText,
          selectionOccurrenceIdx: selectionOcurrenceIdx
        }

        // event is 132 px too large.
        // TODO: Fix hack, bug introduced with vue-multipane.
        let ev = {
          pageY: event.pageY - 42,
          pageX: event.pageX
        }
        this.$refs.ctxMenu.showMenu(ev)
      }
    },
    ctxOptionClicked  () {
      this.$emit('select:addSynonym', this.selection)
    },
    removeNewAnno (idx) {
      this.$emit('remove:newAnno', idx)
    }
  }
}
</script>

<style lang="scss">

.note-container {
  flex: 1 1 auto;
  overflow-y: auto;
  background: rgba(0, 114, 206, .2);
  padding: 40px 40px 0 40px;
  border-radius: 10px;
  height: 100%;
}

.clinical-note {
  background: white;
  overflow-y: auto;
  height: 100%;
  box-shadow: 0px -2px 3px 2px rgba(0, 0, 0, 0.2);
  padding: 25px;
  white-space: pre-wrap;
  line-height: 1.6; // Base line height for normal text

  // Increase line height when there are 3 or more nested underlines
  // to prevent underlines from overlapping with next line
  [class^="highlight-task-"] [class^="highlight-task-"] [class^="highlight-task-"] {
    line-height: 2.2; // Increased line height for 3+ levels of nesting
    padding-bottom: 4px; // Extra padding to push next line down
    display: inline-block; // Ensure padding applies
  }

  // Also handle when default is deeply nested
  .highlight-task-default [class^="highlight-task-"] [class^="highlight-task-"] {
    line-height: 2.2;
    padding-bottom: 4px;
    display: inline-block;
  }
}

.highlight-task-default {
  text-decoration: underline;
  text-decoration-color: lightgrey;
  text-decoration-thickness: 3px;
  text-underline-offset: 3px; // Moved down 1px to avoid descender breaks
  cursor: pointer;

  // Stack underlines when nested - each nested level gets a larger offset with clear spacing
  [class^="highlight-task-"] {
    text-underline-offset: 7px; // Second level underline (4px spacing from first, moved down 1px)
  }

  [class^="highlight-task-"] [class^="highlight-task-"] {
    text-underline-offset: 11px; // Third level underline (4px spacing from second, moved down 1px)
    // Increase line height for 3+ levels to prevent overlap with next line
    line-height: 2.2;
    padding-bottom: 4px;
    display: inline-block;
  }

  [class^="highlight-task-"] [class^="highlight-task-"] [class^="highlight-task-"] {
    text-underline-offset: 15px; // Fourth level underline (4px spacing from third, moved down 1px)
    // Further increase line height for 4+ levels
    line-height: 2.4;
    padding-bottom: 6px;
    display: inline-block;
  }
}

.highlight-task-selected {
  // Background highlight is applied via the specific highlight-task-{i} class
  // This ensures the background color matches the state color
  text-decoration-thickness: 4px;
}

// Selected state for default (unvalidated) annotations
.highlight-task-default.highlight-task-selected {
  background-color: rgba(211, 211, 211, 0.3); // Light grey background for selected default
  padding: 1px 2px;
  border-radius: 2px;
}

.current-rel-start {
  &::after {
    content: "START";
    position: relative;
    font-size: 12px;
    top: -4px;
    left: 1px;
  }
}

.current-rel-end {
  &:after {
    content: "END";
    position: relative;
    font-size: 12px;
    top: -4px;
    left: 1px;
  }
}

.remove-new-anno {
  font-size: 15px;
  color: $task-color-1;
  cursor: pointer;
  position: relative;
  top: -5px;
}

</style>
