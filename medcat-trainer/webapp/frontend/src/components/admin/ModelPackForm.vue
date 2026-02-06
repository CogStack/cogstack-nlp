<template>
  <div class="form-section">
    <div class="form-header">
      <button class="btn btn-back" @click="$emit('close')">
        <font-awesome-icon icon="arrow-left"></font-awesome-icon>
        <span>Back</span>
      </button>
      <h3>{{ editing ? 'Edit Model Pack' : 'Add Model Pack' }}</h3>
    </div>
    <div class="form-content">
      <form @submit.prevent="$emit('save', formData)" class="admin-form">
        <div class="form-sections-wrapper">
          <div class="form-section form-section-horizontal">
            <div class="form-group">
              <label>Name *</label>
              <input v-model="formData.name" type="text" class="form-control" required :disabled="showLegacyFields" />
            </div>
            <div class="form-group">
              <label>Model Pack File <span v-if="!showLegacyFields">*</span></label>
              <input type="file" @change="handleFileChange" accept=".zip" class="form-control file-input" :required="!editing && !showLegacyFields" :disabled="showLegacyFields" />
              <small class="form-text text-muted">Upload a .zip file containing the model pack</small>
            </div>
            <div class="form-group checkbox-group">
              <label class="checkbox-label">
                <input v-model="showLegacyFields" type="checkbox" class="checkbox-input" />
                <span class="checkbox-text">Legacy model upload (CBD & Vocab)</span>
              </label>
            </div>
          </div>
          <div v-if="showLegacyFields" class="form-section form-section-horizontal">
            <div class="form-group">
              <label>Concept DB</label>
              <select v-model="formData.concept_db" class="form-control" :disabled="!showLegacyFields">
                <option :value="null">None</option>
                <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>Vocabulary</label>
              <select v-model="formData.vocab" class="form-control" :disabled="!showLegacyFields">
                <option :value="null">None</option>
                <option v-for="vocab in vocabs" :key="vocab.id" :value="vocab.id">{{ vocab.name }}</option>
              </select>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button type="button" class="btn btn-secondary" @click="$emit('close')">Cancel</button>
          <button type="submit" class="btn btn-primary" :disabled="saving">
            <font-awesome-icon v-if="saving" icon="spinner" spin></font-awesome-icon>
            <span>{{ saving ? 'Saving...' : 'Save' }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ModelPackForm',
  props: {
    editing: {
      type: Boolean,
      default: false
    },
    modelPack: {
      type: Object,
      default: null
    },
    conceptDbs: {
      type: Array,
      required: true
    },
    vocabs: {
      type: Array,
      required: true
    },
    saving: {
      type: Boolean,
      default: false
    }
  },
  emits: ['close', 'save'],
  data() {
    return {
      showLegacyFields: false,
      formData: {
        name: '',
        model_pack: null,
        concept_db: null,
        vocab: null
      }
    }
  },
  watch: {
    modelPack: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.formData = {
            name: newVal.name || '',
            model_pack: null,
            concept_db: newVal.concept_db || null,
            vocab: newVal.vocab || null
          }
          // Show legacy fields if concept_db or vocab are set
          this.showLegacyFields = !!(newVal.concept_db || newVal.vocab)
        } else {
          this.resetForm()
        }
      }
    },
    showLegacyFields(newVal) {
      if (newVal) {
        // When legacy mode is enabled, clear the model pack file
        this.formData.model_pack = null
        // Clear the file input element if it exists
        const fileInput = this.$el?.querySelector('input[type="file"]')
        if (fileInput) {
          fileInput.value = ''
        }
      } else {
        // When legacy mode is disabled, clear legacy fields
        this.formData.concept_db = null
        this.formData.vocab = null
      }
    }
  },
  methods: {
    handleFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.formData.model_pack = file
      }
    },
    resetForm() {
      this.showLegacyFields = false
      this.formData = {
        name: '',
        model_pack: null,
        concept_db: null,
        vocab: null
      }
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/admin.scss';

// Component-specific overrides
.form-section-horizontal {
  // ModelPackForm uses direct form-group children (no form-row), so make section horizontal
  display: flex;
  flex-direction: row;
  gap: 20px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.checkbox-group {
  margin-bottom: 0;
  display: flex;
  align-items: center;
  min-height: 38px;
  padding-top: 26px;
}
</style>
