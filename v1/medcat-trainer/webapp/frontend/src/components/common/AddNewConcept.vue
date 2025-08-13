<template>
  <div @keydown.stop>
    <div class="title">
      Add New Concept
      <div @click="selectNewConcept()" @mousedown.stop class="show-form-button">
        <transition name="slide-up">
          <div>
            <font-awesome-icon v-if="!showAdd" class="" icon="angle-right"
                               @click="$emit('select:newConcept')"></font-awesome-icon>
            <font-awesome-icon v-if="showAdd" icon="angle-down"></font-awesome-icon>
          </div>
        </transition>
      </div>
    </div>
    <table class="add-new-concept-table">
      <tbody>
      <tr v-if="showAdd">
        <td>Name *</td>
        <td><input v-model="concept.name" required type="text" class="form-control"></td>
      </tr>
      <tr v-if="showAdd">
        <td>Concept ID *</td>
        <td><input v-model="concept.cui" required type="text" class="form-control"></td>
      </tr>
      <tr v-if="showAdd">
        <td>Description</td>
        <td><textarea v-model="concept.desc" class="form-control"></textarea></td>
      </tr>
      <tr v-if="showAdd">
        <td>Type</td>
        <td><input v-model="concept.type" type="text" class="form-control"></td>
      </tr>
      <tr v-if="showAdd">
        <td>Type IDs</td>
        <td><input v-model="concept.type_ids" type="text" class="form-control"></td>
      </tr>
      <tr v-if="showAdd">
        <td>Synonyms</td>
        <td><textarea v-model="concept.synonyms" class="form-control"></textarea></td>
      </tr>
      </tbody>
    </table>
    <div class="footer action-buttons">
      <button class="btn btn-primary" :disabled="!addConceptEnabled()"
              @click="addConcept">Add Concept</button>
    </div>
    <div class="alert alert-danger" role="alert" v-if="addConceptErr">
      {{addConceptErr}}
    </div>
  </div>
</template>

<script>
export default {
  name: 'AddNewConcept',
  props: {
    selection: Object,
    project: Object,
    documentId: Number
  },
  emits: [
    'select:newConcept',
    'request:addConceptComplete'
  ],
  data () {
    return {
      showAdd: false,
      concept: {
        name: '',
        desc: '',
        type: '',
        type_ids: '',
        cui: '',
        synonyms: ''
      },
      addConceptErr: false
    }
  },
  methods: {
    selectNewConcept () {
      this.showAdd = !this.showAdd
      this.$emit('select:newConcept', this.showAdd)
    },
    addConceptEnabled () {
      return this.concept.name.length > 1 && this.concept.cui.length > 1
    },
    addConcept () {
      // addNewConcept
      const payload = {
        source_value: this.selection.selStr,
        document_id: this.documentId,
        project_id: this.project.id,
        selection_occur_idx: this.selection.selectionOccurrenceIdx
      }
      Object.assign(payload, this.concept)
      let nextCtx = this.selection.nextText.slice(0, 30).split(' ').slice(0, -1)
      payload['context'] = `${this.selection.prevText}${this.selection.selStr}${nextCtx}`

      this.$http.post(`/api/add-concept/`, payload).then(resp => {
        this.$emit('request:addConceptComplete', resp.data.id)
      }).catch(err => {
        if (err.code === 400) {
          this.addConceptErr = 'Invalid CUI value. CUI already exists in MedCAT.'
          let that = this
          setTimeout(function () {
            that.addConceptErr = false
          }, 5000)
        } else {
          this.addConceptErr = `Error adding concept:${(err.response.data || {}).err || 'Unknown error: more info in the console'}`
          console.error(err)
          let that = this
          setTimeout(function () {
            that.addConceptErr = false
          }, 5000)
        }
      })
    }
  }
}
</script>

<style scoped lang="scss">
$button-height: 50px;

.add-new-concept-table {
  width: 100%;

  tbody > tr {
    box-shadow: 0 5px 5px -5px rgba(0, 0, 0, 0.2);

    > td {
      padding: 10px 15px;
      vertical-align: top;
    }
  }
}

.title {
  @extend .title;
  font-size: 16px;
}

.slide-up-enter-active {
  transition: all .5s ease;
}

.slide-up-enter, .slide-up-leave-to {
  position: relative;
  transform: translateY(10px);
  transition: all .2s ease;
  opacity: 0;
}

.action-buttons {
  text-align: center;
  padding-top: 10px;
  height: $button-height;
}

.show-form-button {
  display: inline-block;
  width: 100px;
  min-width: 15px;
  opacity: 0.5;
  text-align: right;
  &:hover {
    opacity: 1.0;
  }
}

</style>
