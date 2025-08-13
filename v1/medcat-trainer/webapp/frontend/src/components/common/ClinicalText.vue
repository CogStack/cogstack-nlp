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

      const taskHighlightDefault = 'highlight-task-default'
      let formattedText = ''
      let start = 0
      let timeout = 0
      for (let i = 0; i < this.ents.length; i++) {
        // highlight the span with default
        let highlightText = this.text.slice(this.ents[i].start_ind, this.ents[i].end_ind)

        let styleClass = taskHighlightDefault
        if (this.ents[i].assignedValues[this.taskName] !== null) {
          let btnIndex = this.taskValues.indexOf(this.ents[i].assignedValues[this.taskName])
          styleClass = `highlight-task-${btnIndex}`
        }

        if (this.ents[i].id === this.currentRelStartEnt.id) {
          styleClass += ' current-rel-start'
        } else if (this.ents[i].id === this.currentRelEndEnt.id) {
          styleClass += ' current-rel-end'
        }

        styleClass = this.ents[i] === this.currentEnt ? `${styleClass} highlight-task-selected` : styleClass
        timeout = this.ents[i] === this.currentEnt && i === 0 ? 500 : timeout

        let removeButtonEl = ''
        if (this.ents[i].manually_created) {
          removeButtonEl = `<font-awesome-icon icon="times" class="remove-new-anno" @click="removeNewAnno(${i})"></font-awesome-icon>`
        }
        let spanText = `<span @click="selectEnt(${i})" class="${styleClass}">${_.escape(highlightText)}${removeButtonEl}</span>`

        let precedingText = _.escape(this.text.slice(start, this.ents[i].start_ind))
        precedingText = precedingText.length !== 0 ? precedingText : ' '
        start = this.ents[i].end_ind
        formattedText += precedingText + spanText
        if (i === this.ents.length - 1) {
          formattedText += this.text.slice(start, this.text.length)
        }
      }

      // escape '<' '>' that may be interpreted as start/end tags, escape inserted span tags.
      // formattedText = formattedText
      //   .replace(/<(?!\/?span|font-awesome-icon)/g, '&lt')
      //   .replace(/(?<!<span @click="selectEnt\(\d\d?\d?\d?\)".*"|\/span)>/g, '&gt')

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
}

.highlight-task-default {
  background: lightgrey;
  border: 1px solid lightgrey;
  border-radius: 3px;
  cursor: pointer;
}

.highlight-task-selected {
  font-weight: bold;
  font-size: 1.15rem;
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
