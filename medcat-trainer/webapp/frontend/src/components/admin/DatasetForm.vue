<template>
  <div class="form-section">
    <div class="form-header">
      <button class="btn btn-back" @click="$emit('close')">
        <font-awesome-icon icon="arrow-left"></font-awesome-icon>
        <span>Back</span>
      </button>
      <h3>{{ editing ? 'Edit Dataset' : 'Add Dataset' }}</h3>
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
                @invalid="handleInvalid($event)"
                @input="clearValidationError('name')"
              />
              <small v-if="validationErrors.name" class="form-text text-danger">{{ validationErrors.name }}</small>
            </div>
            <div class="form-group">
              <label>Description</label>
              <textarea v-model="formData.description" class="form-control" rows="2"></textarea>
            </div>
          </div>
          <div class="form-section">
            <div class="form-group">
              <label>Original File *</label>
              <input
                type="file"
                name="original_file"
                data-field="original_file"
                @change="handleFileChange"
                accept=".csv,.xlsx"
                class="form-control file-input"
                :class="{ 'is-invalid': validationErrors.original_file }"
                :required="!editing"
                @invalid="handleInvalid($event)"
              />
              <small v-if="validationErrors.original_file" class="form-text text-danger">{{ validationErrors.original_file }}</small>
              <div class="schema-guide">
                <small class="form-text text-muted">
                  <strong>File Schema Requirements:</strong>
                </small>
                <ul class="schema-list">
                  <li><strong>Format:</strong> .csv or .xlsx file</li>
                  <li><strong>Required columns:</strong>
                    <ul>
                      <li><code>name</code> - A unique identifier for each document</li>
                      <li><code>text</code> - The free-text content to annotate</li>
                    </ul>
                  </li>
                  <li>Additional columns are allowed but will be ignored</li>
                </ul>
                <small class="form-text text-muted example-text">
                  <strong>Example CSV structure:</strong><br>
                  <code>name,text</code><br>
                  <code>doc001,"This is the first document to annotate."</code><br>
                  <code>doc002,"This is the second document with medical text."</code>
                </small>
              </div>
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
  name: 'DatasetForm',
  props: {
    editing: {
      type: Boolean,
      default: false
    },
    dataset: {
      type: Object,
      default: null
    },
    saving: {
      type: Boolean,
      default: false
    }
  },
  emits: ['close', 'save'],
  data() {
    return {
      formData: {
        name: '',
        description: '',
        original_file: null
      },
      validationErrors: {}
    }
  },
  watch: {
    dataset: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.formData = {
            name: newVal.name || '',
            description: newVal.description || '',
            original_file: null
          }
        } else {
          this.resetForm()
        }
        // Clear validation errors when dataset changes
        this.validationErrors = {}
      }
    },
    'formData.name'() {
      // Clear error when user starts typing
      if (this.validationErrors.name) {
        delete this.validationErrors.name
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
        this.validationErrors.name = 'Dataset name is required'
        isValid = false
      }

      if (!this.editing && !this.formData.original_file) {
        this.validationErrors.original_file = 'Original file is required'
        isValid = false
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
        this.formData.original_file = file
        // Clear error when file is selected
        if (this.validationErrors.original_file) {
          delete this.validationErrors.original_file
        }
      }
    },
    resetForm() {
      this.formData = {
        name: '',
        description: '',
        original_file: null
      }
      this.validationErrors = {}
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/admin.scss';

// Component-specific styles
.form-section {
  max-height: calc(100vh - 270px);
}


.form-group {
  textarea.form-control {
    resize: vertical;
    min-height: 80px;
    font-family: inherit;
    line-height: 1.5;
    border-radius: 8px;
  }
}
</style>
