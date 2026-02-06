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
      selection: null,
      openPopoverId: null // Track which popover is open
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
        if (a.ent.end_ind !== b.ent.end_ind) {
          return b.ent.end_ind - a.ent.end_ind // Longer spans first when same start
        }
        // For exactly overlapping annotations (same start and end), use original index
        // as tiebreaker to ensure stable, consistent ordering
        return a.origIdx - b.origIdx
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
        // For events at same position and same type (exact overlaps),
        // use entIndex as tiebreaker to ensure stable, consistent ordering
        // For starts: open in order (lower index first)
        // For ends: close in reverse order (higher index first) to maintain proper nesting
        if (a.type === 'start') {
          return a.entIndex - b.entIndex
        } else {
          return b.entIndex - a.entIndex
        }
      })

      // Pre-compute overlapping groups: for each annotation, find all annotations that overlap with it
      const overlappingGroups = new Map() // Map from origIndex to set of all overlapping origIndices
      sortedEnts.forEach((entData1, i1) => {
        const origIdx1 = entData1.origIdx
        const start1 = entData1.ent.start_ind
        const end1 = entData1.ent.end_ind
        const group = new Set([origIdx1])

        sortedEnts.forEach((entData2, i2) => {
          if (i1 === i2) return
          const start2 = entData2.ent.start_ind
          const end2 = entData2.ent.end_ind
          // Check if annotations overlap (they overlap if one starts before the other ends)
          if (!(end1 <= start2 || end2 <= start1)) {
            group.add(entData2.origIdx)
          }
        })

        // Store sorted array of indices for consistent ID generation
        const sortedGroup = Array.from(group).sort((a, b) => a - b)
        overlappingGroups.set(origIdx1, sortedGroup)
      })

      let formattedText = ''
      let currentPos = 0
      const activeEnts = [] // Stack of active entities (ordered by when they were opened)
      const createdPopovers = new Set() // Track which popover IDs have been created to avoid duplicates
      const createdBadges = new Set() // Track which popover IDs have had badges created to avoid multiple badges

      // Helper function to get style class for an entity
      const getStyleClass = (ent, origIndex) => {
        let styleClass = taskHighlightDefault
        if (ent.assignedValues[this.taskName] !== null) {
          let btnIndex = this.taskValues.indexOf(ent.assignedValues[this.taskName])
          styleClass = `highlight-task-${btnIndex}`
        }

        // Only add relation markers if currentRelStartEnt/EndEnt have valid IDs
        if (this.currentRelStartEnt && this.currentRelStartEnt.id && ent.id === this.currentRelStartEnt.id) {
          styleClass += ' current-rel-start'
        } else if (this.currentRelEndEnt && this.currentRelEndEnt.id && ent.id === this.currentRelEndEnt.id) {
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

      // Helper function to build closing span tag with optional remove button and overlap indicator
      const buildCloseSpan = (ent, origIndex, isInnermost, overlappingEnts = []) => {
        let removeButtonEl = ''
        if (isInnermost && ent.manually_created) {
          removeButtonEl = `<font-awesome-icon icon="times" class="remove-new-anno" @click.stop="removeNewAnno(${origIndex})"></font-awesome-icon>`
        }

        // Add overlap indicator only on innermost span and only if there are overlapping annotations
        // Use pre-computed overlapping groups to get the complete group, not just current subset
        let overlapIndicator = ''
        if (isInnermost) {
          // Get the complete overlapping group for this annotation
          const completeGroup = overlappingGroups.get(origIndex) || []
          if (completeGroup.length > 1) {
            // Create popover ID based on complete group
            const popoverId = `popover-${completeGroup.join('-')}`
            const overlapCount = completeGroup.length

            // Only create badge if we haven't created one for this popover ID yet
            if (!createdBadges.has(popoverId)) {
              createdBadges.add(popoverId)

              // Get entity names for all annotations in the complete group
              const entityNames = completeGroup.map(idx => {
                const entData = sortedEnts.find(e => e.origIdx === idx)
                const name = entData ? (entData.ent.pretty_name || 'Unknown') : 'Unknown'
                return `<div class="popover-entity-item" @click.stop="selectEnt(${idx})">${_.escape(name)}</div>`
              }).join('')

              // Only create the popover HTML if it hasn't been created yet for this group
              const popoverHtml = createdPopovers.has(popoverId) ? '' : `<div class="overlap-popover" id="${popoverId}" data-popover-open="false"><div class="popover-content">${entityNames}</div></div>`

              if (!createdPopovers.has(popoverId)) {
                createdPopovers.add(popoverId)
              }

              overlapIndicator = `<span class="overlap-badge" @click.stop="togglePopover('${popoverId}')" data-popover-id="${popoverId}">${overlapCount}</span>${popoverHtml}`
            }
          }
        }

        return `${removeButtonEl}${overlapIndicator}</span>`
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
            // Check if this is the last annotation ending at this position
            // (i.e., all remaining activeEnts also end at this position)
            const allEndAtSamePos = activeEnts.every(ae => {
              const entEndPos = sortedEnts[ae.entIndex].ent.end_ind
              return entEndPos === event.pos
            })

            // If this is not the innermost span, we need to handle overlapping text
            if (index < activeEnts.length - 1 && !allEndAtSamePos) {
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
              // This is either the innermost span, or all remaining spans end at the same position
              // (exactly overlapping case). Add text then close it with remove button if needed
              if (event.pos > currentPos) {
                const textSegment = this.text.slice(currentPos, event.pos)
                if (textSegment.length > 0) {
                  formattedText += _.escape(textSegment)
                }
                currentPos = event.pos
              }
              // For exactly overlapping annotations, only the innermost (last to close) gets the remove button
              const isInnermost = index === activeEnts.length - 1
              // Get all overlapping annotations (all activeEnts at this position)
              // Include this span in the overlapping list
              const overlappingEnts = activeEnts.map(ae => ({
                ent: ae.ent,
                origIndex: ae.origIndex
              }))
              // Show badge on innermost span when there are overlapping annotations
              // The popover HTML will only be created once per group (tracked by createdPopovers)
              const shouldShowBadge = isInnermost && (overlappingEnts.length > 1)
              formattedText += buildCloseSpan(event.ent, event.origIndex, isInnermost, shouldShowBadge ? overlappingEnts : [])
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
          // Get all overlapping annotations (all remaining activeEnts)
          const overlappingEnts = activeEnts.map(ae => ({
            ent: ae.ent,
            origIndex: ae.origIndex
          }))
          // Show badge on innermost span when there are overlapping annotations
          // The popover HTML will only be created once per group (tracked by createdPopovers)
          const shouldShowBadge = isInnermost && (overlappingEnts.length > 1)
          formattedText += buildCloseSpan(activeData.ent, activeData.origIndex, isInnermost, shouldShowBadge ? overlappingEnts : [])
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
      // Get selected text while excluding badge content
      let selStr = ''
      if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0)
        // Clone the range to avoid modifying the original selection
        const clonedRange = range.cloneRange()
        // Create a temporary container to get text content
        const tempDiv = document.createElement('div')
        tempDiv.appendChild(clonedRange.cloneContents())
        // Remove all badge elements from the cloned content
        const badges = tempDiv.querySelectorAll('.overlap-badge')
        badges.forEach(badge => badge.remove())
        const popovers = tempDiv.querySelectorAll('.overlap-popover')
        popovers.forEach(popover => popover.remove())
        // Get text content without badges
        selStr = tempDiv.textContent || tempDiv.innerText || ''
      } else {
        selStr = selection.toString()
      }
      selStr = selStr.trim()
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
    },
    togglePopover (popoverId) {
      // Close all other popovers first
      const allPopovers = document.querySelectorAll('.overlap-popover')
      allPopovers.forEach(pop => {
        if (pop.id !== popoverId) {
          pop.setAttribute('data-popover-open', 'false')
          pop.classList.remove('popover-open')
        }
      })

      // Toggle the clicked popover
      const popover = document.getElementById(popoverId)
      if (popover) {
        const isOpen = popover.getAttribute('data-popover-open') === 'true'
        popover.setAttribute('data-popover-open', isOpen ? 'false' : 'true')
        if (isOpen) {
          popover.classList.remove('popover-open')
          this.openPopoverId = null
        } else {
          popover.classList.add('popover-open')
          this.openPopoverId = popoverId

          // If any entities have "Unknown" as their name, call selectEnt to populate the name
          // Extract entity indices from popover ID (format: popover-15-16-17-18)
          const indicesStr = popoverId.replace('popover-', '')
          const entityIndices = indicesStr.split('-').map(idx => parseInt(idx, 10))

          // Check each entity and call selectEnt if it's unknown
          entityIndices.forEach(origIndex => {
            if (this.ents && this.ents[origIndex]) {
              const ent = this.ents[origIndex]
              const name = ent.pretty_name || ''
              // If name is empty or "Unknown", call selectEnt to populate it
              if (!name || name.trim() === '' || name === 'Unknown') {
                this.selectEnt(origIndex)
              }
            }
          })
        }
      }
    },
    handleOutsideClick (event) {
      // Close popover if clicking outside of it
      if (this.openPopoverId) {
        const popover = document.getElementById(this.openPopoverId)
        const badge = document.querySelector(`[data-popover-id="${this.openPopoverId}"]`)
        if (popover && badge) {
          // Check if click is outside both popover and badge
          if (!popover.contains(event.target) && !badge.contains(event.target)) {
            popover.setAttribute('data-popover-open', 'false')
            popover.classList.remove('popover-open')
            this.openPopoverId = null
          }
        }
      }
    }
  },
  mounted () {
    // Close popovers when clicking outside
    document.addEventListener('click', this.handleOutsideClick)
  },
  beforeUnmount () {
    // Clean up event listener
    document.removeEventListener('click', this.handleOutsideClick)
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

}

.highlight-task-default {
  --underline-base-offset: 3px;
  --underline-thickness: 2px;

  text-decoration: underline;
  text-decoration-color: lightgrey;
  text-decoration-thickness: var(--underline-thickness);
  text-underline-offset: var(--underline-base-offset);
  cursor: pointer;
  position: relative;
  display: inline-block;
}

// Overlap badge and popover styles
.overlap-badge {
  position: absolute;
  top: -12px;
  right: -12px;
  padding: 4px 8px;
  background-color: rgba(245, 245, 245, 0.5);
  color: #666;
  border-radius: 12px;
  font-size: 14px;
  font-weight: bold;
  cursor: pointer;
  z-index: 10;
  user-select: none;
  -webkit-user-select: none;
  pointer-events: auto;
  // Make badge larger and easier to click
  min-width: 24px;
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: background-color 0.2s, transform 0.1s;

  &:hover {
    background-color: #e0e0e0;
    transform: scale(1.1);
  }

  &:active {
    transform: scale(0.95);
  }
}

.overlap-popover {
  // Completely remove from document flow when hidden
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 1000;

  // When hidden - display: none removes element from layout completely
  display: none;
  pointer-events: none;

  // Base styles (applied when visible)
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 220px;
  max-width: 300px;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
  padding: 0;

  &.popover-open {
    display: block;
    pointer-events: auto;
  }

  .popover-content {
    padding: 4px 0;
  }

  .popover-entity-item {
    padding: 10px 12px;
    cursor: pointer;
    border-bottom: 1px solid #eee;
    transition: background-color 0.15s ease;
    color: #333;
    font-size: 14px;
    line-height: 1.4;

    &:hover {
      background-color: #f0f7ff;
      color: #0066cc;
    }

    &:active {
      background-color: #e0f0ff;
    }

    &:last-child {
      border-bottom: none;
    }
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
