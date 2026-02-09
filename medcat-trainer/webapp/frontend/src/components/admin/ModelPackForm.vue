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
      <form @submit.prevent="handleSubmit" class="admin-form">
        <div class="form-sections-wrapper">
          <div class="form-section form-section-horizontal">
            <div class="form-group">
              <label>Name *</label>
              <input
                v-model="formData.name"
                type="text"
                name="name"
                data-field="name"
                class="form-control"
                :class="{ 'is-invalid': validationErrors.name }"
                required
                :disabled="showLegacyFields"
                @invalid="handleInvalid($event)"
                @input="clearValidationError('name')"
              />
              <small v-if="validationErrors.name" class="form-text text-danger">{{ validationErrors.name }}</small>
            </div>
            <div class="form-group">
              <label>Model Pack File <span v-if="!showLegacyFields">*</span></label>
              <input
                type="file"
                name="model_pack"
                data-field="model_pack"
                @change="handleFileChange"
                accept=".zip"
                class="form-control file-input"
                :class="{ 'is-invalid': validationErrors.model_pack }"
                :required="!editing && !showLegacyFields"
                :disabled="showLegacyFields"
                @invalid="handleInvalid($event)"
              />
              <small v-if="validationErrors.model_pack" class="form-text text-danger">{{ validationErrors.model_pack }}</small>
              <small v-else class="form-text text-muted">Upload a .zip file containing the model pack</small>
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
              <label>Concept DB *</label>
              <select
                v-model="formData.concept_db"
                name="concept_db"
                data-field="concept_db"
                class="form-control"
                :class="{ 'is-invalid': validationErrors.concept_db }"
                :disabled="!showLegacyFields"
                @change="clearValidationError('concept_db')"
              >
                <option :value="null">None</option>
                <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
              </select>
              <small v-if="validationErrors.concept_db" class="form-text text-danger">{{ validationErrors.concept_db }}</small>
            </div>
            <div class="form-group">
              <label>Vocabulary *</label>
              <select
                v-model="formData.vocab"
                name="vocab"
                data-field="vocab"
                class="form-control"
                :class="{ 'is-invalid': validationErrors.vocab }"
                :disabled="!showLegacyFields"
                @change="clearValidationError('vocab')"
              >
                <option :value="null">None</option>
                <option v-for="vocab in vocabs" :key="vocab.id" :value="vocab.id">{{ vocab.name }}</option>
              </select>
              <small v-if="validationErrors.vocab" class="form-text text-danger">{{ validationErrors.vocab }}</small>
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
      },
      validationErrors: {}
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
        // Clear validation errors when modelPack changes
        this.validationErrors = {}
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
        // Clear model_pack error if switching to legacy mode
        if (this.validationErrors.model_pack) {
          delete this.validationErrors.model_pack
        }
      } else {
        // When legacy mode is disabled, clear legacy fields
        this.formData.concept_db = null
        this.formData.vocab = null
        // Clear legacy field errors if switching to normal mode
        if (this.validationErrors.concept_db) {
          delete this.validationErrors.concept_db
        }
        if (this.validationErrors.vocab) {
          delete this.validationErrors.vocab
        }
      }
    },
    'formData.name'() {
      if (this.validationErrors.name) {
        delete this.validationErrors.name
      }
    },
    'formData.concept_db'() {
      if (this.validationErrors.concept_db) {
        delete this.validationErrors.concept_db
      }
    },
    'formData.vocab'() {
      if (this.validationErrors.vocab) {
        delete this.validationErrors.vocab
      }
    }
  },
  methods: {
    handleInvalid(event) {
      event.preventDefault()
      const field = event.target
      const fieldName = field.name || field.getAttribute('data-field')
      if (fieldName && this.validationErrors[fieldName]) {
        field.setCustomValidity(this.validationErrors[fieldName])
      }
    },
    clearValidationError(fieldName) {
      if (this.validationErrors[fieldName]) {
        delete this.validationErrors[fieldName]
        const field = this.$el?.querySelector(`[data-field="${fieldName}"], [name="${fieldName}"]`)
        if (field) {
          field.setCustomValidity('')
          field.classList.remove('is-invalid')
        }
      }
    },
    validateForm() {
      this.validationErrors = {}
      let isValid = true

      if (!this.formData.name || this.formData.name.trim() === '') {
        this.validationErrors.name = 'Model pack name is required'
        isValid = false
      }

      if (this.showLegacyFields) {
        // Legacy mode: both concept_db and vocab are required
        if (!this.formData.concept_db) {
          this.validationErrors.concept_db = 'Concept DB is required for legacy model upload'
          isValid = false
        }
        if (!this.formData.vocab) {
          this.validationErrors.vocab = 'Vocabulary is required for legacy model upload'
          isValid = false
        }
      } else {
        // Normal mode: model_pack file is required when creating
        if (!this.editing && !this.formData.model_pack) {
          this.validationErrors.model_pack = 'Model pack file is required'
          isValid = false
        }
      }

      // Set HTML5 validation messages
      if (!isValid) {
        this.$nextTick(() => {
          Object.keys(this.validationErrors).forEach(fieldName => {
            const field = this.$el?.querySelector(`[data-field="${fieldName}"], [name="${fieldName}"]`)
            if (field && this.validationErrors[fieldName]) {
              field.setCustomValidity(this.validationErrors[fieldName])
              field.classList.add('is-invalid')
            }
          })
        })
      }

      return isValid
    },
    handleSubmit() {
      if (this.validateForm()) {
        this.$emit('save', this.formData)
      } else {
        this.$toast?.error('Please fix the validation errors before saving')
      }
    },
    handleFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.formData.model_pack = file
        // Clear error when file is selected
        if (this.validationErrors.model_pack) {
          delete this.validationErrors.model_pack
        }
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
      this.validationErrors = {}
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
