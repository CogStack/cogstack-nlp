<template>
  <div class="task-bar" >
    <div class="task-bar-choices">
      <button :disabled="taskLocked" class="btn task-btn-0" @click="correct">
        Correct</button>
      <button :disabled="taskLocked" class="btn task-btn-1" @click="remove">
        Incorrect</button>
      <button v-if="terminateEnabled" :disabled="taskLocked" class="btn task-btn-2" @click="kill">
        Terminate</button>
      <button :disabled="taskLocked" class="btn task-btn-3" @click="alternative">
        Alternative</button>
      <button v-if="irrelevantEnabled" :disabled="taskLocked" class="btn task-btn-4" @click="irrelevant">
        Irrelevant
      </button>
    </div>
    <button :disabled="submitDisabled()" @click="submit()" class="btn btn-outline-primary mb-2 submit-btn submit"
              type="button">Submit</button>
  </div>
</template>

<script>
import _ from 'lodash'

export default {
  name: 'TaskBar',
  props: {
    ents: Array,
    taskLocked: Boolean,
    submitLocked: Boolean,
    altSearch: Boolean,
    terminateEnabled: Boolean,
    irrelevantEnabled: Boolean,
    conceptSelection: Object
  },
  emits: [
    'select:correct',
    'select:remove',
    'select:kill',
    'select:alternative',
    'select:irrelevant',
    'submit'
  ],
  watch: {
    'submitLocked' (newVal) {
      if (newVal === null || newVal === false) {
        this.listenShortcuts()
      } else {
        this.ignoreShortcuts()
      }
    }
  },
  methods: {
    correct () {
      this.$emit('select:correct')
    },
    remove () {
      this.$emit('select:remove')
    },
    kill () {
      this.$emit('select:kill')
    },
    alternative () {
      this.$emit('select:alternative', !this.altSearch)
    },
    irrelevant () {
      this.$emit('select:irrelevant')
    },
    submit () {
      this.$emit('submit', true)
    },
    submitDisabled () {
      if (this.ents !== null && !this.submitLocked) {
        return !this.ents.every(e => {
          return Object.values(e.assignedValues).every(e => e !== null)
        })
      }
      return true
    },
    keydown (e) {
      if (e.keyCode === 13 && !this.conceptSelection) {
        if (!this.submitDisabled()) {
          this.ignoreShortcuts()
          this.submit()
        }
      } else if (e.keyCode >= 49 && e.keyCode < 54 && !this.taskLocked) {
        let codeRange = _.range(5)
        let keyRange = _.range(49, 54)
        let selectIdx = _.zipObject(keyRange, codeRange)[e.keyCode]
        switch (selectIdx) {
          case 0:
            this.correct()
            break
          case 1:
            this.remove()
            break
          case 2:
            if (this.terminateEnabled) {
              this.kill()
            }
            break
          case 3:
            this.alternative()
            break
          case 4:
            if (this.irrelevantEnabled) {
              this.irrelevant()
            }
        }
      }
    },
    listenShortcuts () {
      window.addEventListener('keydown', this.keydown)
    },
    ignoreShortcuts () {
      window.removeEventListener('keydown', this.keydown)
    }
  },
  mounted () {
    this.listenShortcuts()
  },
  beforeDestroy () {
    this.ignoreShortcuts()
  }
}
</script>

<style scoped lang="scss">
.task-bar {
  width: 100%;
  background-color: $background;
  color: $text;
  text-align: center;

  .task-bar-choices {
    width: calc(100% - 100px);
  }

  div {
    display: inline-block;
  }

  .submit {
    float: right;
    width: 100px;
  }
}
</style>
