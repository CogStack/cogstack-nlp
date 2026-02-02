<template>
  <div class="annotate-text-entry">
    <div class="annotate-text-entry__controls">
      <div class="annotate-text-entry__textbox">
        <div v-if="mode === 'edit'" class="annotate-text-entry__edit-container">
          <div v-if="isAnnotating" class="annotate-text-entry__loading-indicator">
            <div class="annotate-text-entry__spinner"></div>
            <span>{{ loadingMsg || 'Annotating...' }}</span>
          </div>
          <textarea
            ref="textarea"
            v-model="message"
            class="annotate-text-entry__textarea"
            :class="{ 'annotate-text-entry__textarea--loading': isAnnotating }"
            name="message"
            placeholder="Enter text to annotate…"
            @input="scheduleAnnotate"
            @blur="onBlur"
          ></textarea>
        </div>
        <div v-else class="annotate-text-entry__render" @dblclick.stop="switchToEdit">
          <div class="annotate-text-entry__edit-hint" v-if="mode === 'view'">
            Double-click to edit
          </div>
          <clinical-text
            :loading="loadingMsg"
            :text="annotatedText"
            :ents="ents"
            :taskName="taskName"
            :taskValues="taskValues"
            @select:concept="selectEntity"
          ></clinical-text>
        </div>
      </div>

      <div class="annotate-text-entry__actions">
        <span v-if="!modelpackId" class="text-muted small">Select a model pack first.</span>
      </div>
    </div>
  </div>
</template>

<script>
import ClinicalText from '@/components/common/ClinicalText.vue'

export default {
  name: 'AnnotateTextEntry',
  components: { ClinicalText },
  props: {
    modelpackId: {
      type: [Number, String],
      default: null
    },
    cuis: {
      type: String,
      default: ''
    },
    includeSubConcepts: {
      type: Boolean,
      default: false
    },
    taskName: {
      type: String,
      required: true
    },
    taskValues: {
      type: Array,
      required: true
    },
    initialText: {
      type: String,
      default: ''
    }
  },
  emits: [
    'annotated',
    'select:concept'
  ],
  data () {
    return {
      message: this.initialText,
      loadingMsg: null,
      mode: 'edit', // 'edit' | 'view'
      annotatedText: '',
      ents: [],
      debounceTimer: null,
      requestSeq: 0,
      isWaitingForDebounce: false
    }
  },
  computed: {
    isAnnotating () {
      return this.loadingMsg !== null
    }
  },
  watch: {
    modelpackId () {
      // If a model pack gets selected while editing, schedule an annotation.
      this.scheduleAnnotate()
    },
    cuis () {
      // Changing filters should re-annotate the current text as well.
      this.scheduleAnnotate()
    }
  },
  methods: {
    switchToEdit () {
      // keep message as the single source of truth for editing
      this.message = this.annotatedText || this.message
      this.mode = 'edit'
      // annotations are no longer valid once the user edits
      this.ents = []
      this.annotatedText = ''
      this.$emit('select:concept', null)

      this.$nextTick(() => {
        this.$refs.textarea?.focus?.()
      })
    },
    onBlur () {
      // When textarea loses focus, annotate immediately if there's text and a modelpack
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer)
        this.debounceTimer = null
        this.isWaitingForDebounce = false
      }

      if (this.modelpackId && this.message && this.message.trim().length > 0) {
        this.annotateNow()
      }
    },
    scheduleAnnotate () {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer)
        this.debounceTimer = null
      }

      // No modelpack -> nothing to do.
      if (!this.modelpackId) {
        this.isWaitingForDebounce = false
        return
      }

      // Empty/whitespace -> clear view if currently showing annotations.
      if (!this.message || this.message.trim().length === 0) {
        this.loadingMsg = null
        this.isWaitingForDebounce = false
        this.mode = 'edit'
        this.ents = []
        this.annotatedText = ''
        this.$emit('select:concept', null)
        return
      }

      // Show waiting indicator during debounce
      this.isWaitingForDebounce = true
      this.debounceTimer = setTimeout(() => {
        this.debounceTimer = null
        this.isWaitingForDebounce = false
        this.annotateNow()
      }, 1500)
    },
    annotateNow () {
      if (!this.modelpackId) return
      const payload = {
        modelpack_id: this.modelpackId,
        message: this.message,
        cuis: this.cuis,
        include_sub_concepts: this.includeSubConcepts
      }
      const seq = ++this.requestSeq
      this.loadingMsg = 'Annotating Text...'
      return this.$http.post('/api/annotate-text/', payload).then(resp => {
        // Ignore out-of-order responses
        if (seq !== this.requestSeq) return
        this.loadingMsg = null
        this.annotatedText = resp.data.message
        this.ents = (resp.data.entities || []).map(e => {
          // Preserve all existing properties including meta_annotations
          return {
            ...e,
            assignedValues: {
              [this.taskName]: this.taskValues[0]
            }
          }
        })
        this.mode = 'view'
        const first = this.ents.length > 0 ? this.ents[0] : null
        this.$emit('annotated', { message: this.annotatedText, entities: this.ents, selected: first })
        if (first) {
          this.$emit('select:concept', first)
        } else {
          this.$emit('select:concept', null)
        }
      }).catch(() => {
        if (seq !== this.requestSeq) return
        this.loadingMsg = null
      })
    },
    selectEntity (entIndex) {
      const ent = this.ents?.[entIndex]
      this.$emit('select:concept', ent || null)
    }
  }
}
</script>

<style scoped lang="scss">
.annotate-text-entry {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.annotate-text-entry__controls {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.annotate-text-entry__textbox {
  width: 100%;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}

.annotate-text-entry__edit-container {
  flex: 1 1 auto;
  overflow-y: auto;
  background: rgba(0, 114, 206, .2);
  padding: 40px 40px 0 40px;
  border-radius: 10px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.annotate-text-entry__textarea {
  background: white;
  overflow-y: auto;
  height: 100%;
  box-shadow: 0px -2px 3px 2px rgba(0, 0, 0, 0.2);
  padding: 25px;
  white-space: pre-wrap;
  line-height: 1.6;
  border: none;
  resize: none;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
  outline: none;
}

.annotate-text-entry__textarea::placeholder {
  color: #999;
}

.annotate-text-entry__render {
  // ClinicalText already provides its own "textbox-like" styling; keep it full width here
  width: 100%;
  flex: 1 1 auto;
  min-height: 0;
  position: relative;
  cursor: text;
  display: flex;
}

.annotate-text-entry__edit-hint {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  pointer-events: none;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s;
}

.annotate-text-entry__render:hover .annotate-text-entry__edit-hint {
  opacity: 1;
}

.annotate-text-entry__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.annotate-text-entry__edit-container {
  position: relative;
}

.annotate-text-entry__loading-indicator {
  position: absolute;
  top: 50px;
  right: 50px;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.95);
  padding: 10px 16px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 14px;
  color: #0d6efd;
  font-weight: 500;
}

.annotate-text-entry__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(13, 110, 253, 0.2);
  border-top-color: #0d6efd;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.annotate-text-entry__textarea--loading {
  opacity: 0.7;
}
</style>

