<template>
  <div class="container-fluid project-admin-view">
    <div class="project-admin-header">
      <h2>Project Administration</h2>
      <p class="subtitle">Manage your annotation projects</p>
    </div>

    <div v-if="loading" class="loading-container">
      <v-progress-circular indeterminate color="primary"></v-progress-circular>
      <span>Loading projects...</span>
    </div>

    <div v-else class="project-admin-content">
      <!-- Project List -->
      <div class="project-list-section">
        <div class="section-header">
          <h3>Your Projects</h3>
          <button class="btn btn-primary" @click="showCreateForm = true">
            <font-awesome-icon icon="plus"></font-awesome-icon>
            Create New Project
          </button>
        </div>

        <v-data-table
          v-if="projects.length > 0"
          :items="projects"
          :headers="tableHeaders"
          :hover="true"
          @click:row="selectProject"
          hide-default-footer
          :items-per-page="-1">
          <template #item.name="{ item }">
            <strong>{{ item.name }}</strong>
          </template>
          <template #item.status="{ item }">
            <span class="badge" :class="getStatusClass(item.project_status)">
              {{ getStatusText(item.project_status) }}
            </span>
          </template>
          <template #item.actions="{ item }">
            <div class="action-buttons" @click.stop>
              <button class="btn btn-sm btn-outline-primary" @click="editProject(item)">
                <font-awesome-icon icon="edit"></font-awesome-icon>
              </button>
              <button class="btn btn-sm btn-outline-danger" @click="confirmDelete(item)">
                <font-awesome-icon icon="trash"></font-awesome-icon>
              </button>
              <button class="btn btn-sm btn-outline-warning" @click="confirmReset(item)">
                <font-awesome-icon icon="undo"></font-awesome-icon>
              </button>
            </div>
          </template>
        </v-data-table>

        <div v-else class="no-projects">
          <p>You don't have any projects yet. Create one to get started!</p>
        </div>
      </div>

      <!-- Create/Edit Form Modal -->
      <modal v-if="showCreateForm || editingProject" :closable="true" @modal:close="closeForm" class="project-form-modal">
        <template #header>
          <h3>{{ editingProject ? 'Edit Project' : 'Create New Project' }}</h3>
        </template>
        <template #body>
          <form @submit.prevent="saveProject" class="project-form">
            <div class="form-section">
              <h4>Basic Information</h4>
              <div class="form-group">
                <label>Project Name *</label>
                <input v-model="formData.name" type="text" class="form-control" required />
              </div>
              <div class="form-group">
                <label>Description</label>
                <textarea v-model="formData.description" class="form-control" rows="3"></textarea>
              </div>
              <div class="form-group">
                <label>Annotation Guideline Link</label>
                <input v-model="formData.annotation_guideline_link" type="url" class="form-control" />
              </div>
              <div class="form-group">
                <label>Dataset *</label>
                <select v-model="formData.dataset" class="form-control" required>
                  <option :value="null">Select a dataset</option>
                  <option v-for="ds in datasets" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
                </select>
              </div>
            </div>

            <div class="form-section">
              <h4>Project Settings</h4>
              <div class="form-group">
                <label>Project Status</label>
                <select v-model="formData.project_status" class="form-control">
                  <option value="A">Annotating</option>
                  <option value="C">Complete</option>
                  <option value="D">Discontinued (Fail)</option>
                </select>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.project_locked" type="checkbox" />
                  Project Locked
                </label>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.annotation_classification" type="checkbox" />
                  Annotation Classification (suitable for training general purpose model)
                </label>
              </div>
            </div>

            <div class="form-section">
              <h4>Model Configuration</h4>
              <div class="form-group">
                <label>Concept DB</label>
                <select v-model="formData.concept_db" class="form-control">
                  <option :value="null">None</option>
                  <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>Vocabulary</label>
                <select v-model="formData.vocab" class="form-control">
                  <option :value="null">None</option>
                  <option v-for="vocab in vocabs" :key="vocab.id" :value="vocab.id">{{ vocab.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>Model Pack</label>
                <select v-model="formData.model_pack" class="form-control">
                  <option :value="null">None</option>
                  <option v-for="mp in modelPacks" :key="mp.id" :value="mp.id">{{ mp.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>CDB Search Filter</label>
                <select v-model="formData.cdb_search_filter" multiple class="form-control">
                  <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
                </select>
                <small class="form-text text-muted">Hold Ctrl/Cmd to select multiple</small>
              </div>
            </div>

            <div class="form-section">
              <h4>Annotation Settings</h4>
              <div class="form-group">
                <label>
                  <input v-model="formData.require_entity_validation" type="checkbox" />
                  Require Entity Validation
                </label>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.train_model_on_submit" type="checkbox" />
                  Train Model on Submit
                </label>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.add_new_entities" type="checkbox" />
                  Add New Entities
                </label>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.restrict_concept_lookup" type="checkbox" />
                  Restrict Concept Lookup
                </label>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.terminate_available" type="checkbox" />
                  Terminate Available
                </label>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.irrelevant_available" type="checkbox" />
                  Irrelevant Available
                </label>
              </div>
              <div class="form-group">
                <label>
                  <input v-model="formData.enable_entity_annotation_comments" type="checkbox" />
                  Enable Entity Annotation Comments
                </label>
              </div>
            </div>

            <div class="form-section">
              <h4>Concept Filtering</h4>
              <div class="form-group">
                <label>CUIs (comma-separated)</label>
                <textarea v-model="formData.cuis" class="form-control" rows="3"
                          placeholder="e.g., C1234567, C7654321"></textarea>
              </div>
              <div class="form-group">
                <label>CUI File</label>
                <input type="file" @change="handleCuiFileChange" accept=".json" class="form-control" />
                <small class="form-text text-muted">JSON file containing array of CUI strings</small>
              </div>
            </div>

            <div class="form-section">
              <h4>Members</h4>
              <div class="form-group">
                <label>Project Members</label>
                <select v-model="formData.members" multiple class="form-control">
                  <option v-for="user in users" :key="user.id" :value="user.id">{{ user.username }}</option>
                </select>
                <small class="form-text text-muted">Hold Ctrl/Cmd to select multiple</small>
              </div>
            </div>

            <div class="form-actions">
              <button type="button" class="btn btn-secondary" @click="closeForm">Cancel</button>
              <button type="submit" class="btn btn-primary" :disabled="saving">
                <font-awesome-icon v-if="!saving" icon="save"></font-awesome-icon>
                <font-awesome-icon v-if="saving" icon="spinner" spin></font-awesome-icon>
                {{ saving ? 'Saving...' : 'Save Project' }}
              </button>
            </div>
          </form>
        </template>
      </modal>

      <!-- Delete Confirmation Modal -->
      <modal v-if="projectToDelete" :closable="true" @modal:close="projectToDelete = null" class="confirm-modal">
        <template #header>
          <h3>Confirm Delete</h3>
        </template>
        <template #body>
          <p>Are you sure you want to delete the project <strong>{{ projectToDelete.name }}</strong>?</p>
          <p class="text-danger">This action cannot be undone.</p>
          <div class="form-actions">
            <button class="btn btn-secondary" @click="projectToDelete = null">Cancel</button>
            <button class="btn btn-danger" @click="deleteProject">Delete</button>
          </div>
        </template>
      </modal>

      <!-- Reset Confirmation Modal -->
      <modal v-if="projectToReset" :closable="true" @modal:close="projectToReset = null" class="confirm-modal">
        <template #header>
          <h3>Confirm Reset</h3>
        </template>
        <template #body>
          <p>Are you sure you want to reset the project <strong>{{ projectToReset.name }}</strong>?</p>
          <p class="text-warning">This will remove all annotations and clear validated/prepared documents.</p>
          <div class="form-actions">
            <button class="btn btn-secondary" @click="projectToReset = null">Cancel</button>
            <button class="btn btn-warning" @click="resetProject">Reset</button>
          </div>
        </template>
      </modal>
    </div>
  </div>
</template>

<script>
import Modal from '@/components/common/Modal.vue'

export default {
  name: 'ProjectAdmin',
  components: {
    Modal
  },
  data() {
    return {
      loading: true,
      projects: [],
      datasets: [],
      conceptDbs: [],
      vocabs: [],
      modelPacks: [],
      users: [],
      showCreateForm: false,
      editingProject: null,
      projectToDelete: null,
      projectToReset: null,
      saving: false,
      formData: {
        name: '',
        description: '',
        annotation_guideline_link: '',
        dataset: null,
        project_status: 'A',
        project_locked: false,
        annotation_classification: false,
        concept_db: null,
        vocab: null,
        model_pack: null,
        cdb_search_filter: [],
        require_entity_validation: true,
        train_model_on_submit: true,
        add_new_entities: false,
        restrict_concept_lookup: false,
        terminate_available: true,
        irrelevant_available: false,
        enable_entity_annotation_comments: false,
        cuis: '',
        cuis_file: null,
        members: []
      },
      tableHeaders: [
        { title: 'Name', value: 'name' },
        { title: 'Description', value: 'description' },
        { title: 'Status', value: 'status' },
        { title: 'Dataset', value: 'dataset' },
        { title: 'Actions', value: 'actions', sortable: false }
      ]
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    async loadData() {
      this.loading = true
      try {
        await Promise.all([
          this.fetchProjects(),
          this.fetchDatasets(),
          this.fetchConceptDbs(),
          this.fetchVocabs(),
          this.fetchModelPacks(),
          this.fetchUsers()
        ])
      } catch (error) {
        console.error('Error loading data:', error)
        this.$toast?.error('Failed to load data')
      } finally {
        this.loading = false
      }
    },
    async fetchProjects() {
      const response = await this.$http.get('/api/project-admin/projects/')
      this.projects = response.data
    },
    async fetchDatasets() {
      const response = await this.$http.get('/api/datasets/')
      this.datasets = response.data.results || response.data
    },
    async fetchConceptDbs() {
      const response = await this.$http.get('/api/concept-dbs/')
      this.conceptDbs = response.data.results || response.data
    },
    async fetchVocabs() {
      const response = await this.$http.get('/api/vocabs/')
      this.vocabs = response.data.results || response.data
    },
    async fetchModelPacks() {
      const response = await this.$http.get('/api/modelpacks/')
      this.modelPacks = response.data.results || response.data
    },
    async fetchUsers() {
      const response = await this.$http.get('/api/users/')
      this.users = response.data.results || response.data
    },
    selectProject(project) {
      this.editProject(project)
    },
    editProject(project) {
      this.editingProject = project
      this.formData = {
        name: project.name || '',
        description: project.description || '',
        annotation_guideline_link: project.annotation_guideline_link || '',
        dataset: project.dataset || null,
        project_status: project.project_status || 'A',
        project_locked: project.project_locked || false,
        annotation_classification: project.annotation_classification || false,
        concept_db: project.concept_db || null,
        vocab: project.vocab || null,
        model_pack: project.model_pack || null,
        cdb_search_filter: project.cdb_search_filter || [],
        require_entity_validation: project.require_entity_validation !== undefined ? project.require_entity_validation : true,
        train_model_on_submit: project.train_model_on_submit !== undefined ? project.train_model_on_submit : true,
        add_new_entities: project.add_new_entities || false,
        restrict_concept_lookup: project.restrict_concept_lookup || false,
        terminate_available: project.terminate_available !== undefined ? project.terminate_available : true,
        irrelevant_available: project.irrelevant_available || false,
        enable_entity_annotation_comments: project.enable_entity_annotation_comments || false,
        cuis: project.cuis || '',
        cuis_file: null,
        members: project.members ? project.members.map(m => typeof m === 'object' ? m.id : m) : []
      }
      this.showCreateForm = true
    },
    closeForm() {
      this.showCreateForm = false
      this.editingProject = null
      this.resetForm()
    },
    resetForm() {
      this.formData = {
        name: '',
        description: '',
        annotation_guideline_link: '',
        dataset: null,
        project_status: 'A',
        project_locked: false,
        annotation_classification: false,
        concept_db: null,
        vocab: null,
        model_pack: null,
        cdb_search_filter: [],
        require_entity_validation: true,
        train_model_on_submit: true,
        add_new_entities: false,
        restrict_concept_lookup: false,
        terminate_available: true,
        irrelevant_available: false,
        enable_entity_annotation_comments: false,
        cuis: '',
        cuis_file: null,
        members: []
      }
    },
    handleCuiFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.formData.cuis_file = file
      }
    },
    async saveProject() {
      this.saving = true
      try {
        const formDataToSend = new FormData()

        // Add all form fields to FormData
        Object.keys(this.formData).forEach(key => {
          if (key === 'cuis_file' && this.formData[key]) {
            formDataToSend.append(key, this.formData[key])
          } else if (key === 'cdb_search_filter' || key === 'members') {
            // Handle arrays
            this.formData[key].forEach(val => {
              formDataToSend.append(key, val)
            })
          } else if (this.formData[key] !== null && this.formData[key] !== undefined) {
            formDataToSend.append(key, this.formData[key])
          }
        })

        let response
        if (this.editingProject) {
          // Update existing project
          response = await this.$http.put(
            `/api/project-admin/projects/${this.editingProject.id}/`,
            formDataToSend,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        } else {
          // Create new project
          response = await this.$http.post(
            '/api/project-admin/projects/create/',
            formDataToSend,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        }

        this.$toast?.success(`Project ${this.editingProject ? 'updated' : 'created'} successfully`)
        this.closeForm()
        await this.fetchProjects()
      } catch (error) {
        console.error('Error saving project:', error)
        const errorMsg = error.response?.data?.error || error.response?.data?.message || 'Failed to save project'
        this.$toast?.error(errorMsg)
      } finally {
        this.saving = false
      }
    },
    confirmDelete(project) {
      this.projectToDelete = project
    },
    async deleteProject() {
      try {
        await this.$http.delete(`/api/project-admin/projects/${this.projectToDelete.id}/`)
        this.$toast?.success('Project deleted successfully')
        this.projectToDelete = null
        await this.fetchProjects()
      } catch (error) {
        console.error('Error deleting project:', error)
        const errorMsg = error.response?.data?.error || 'Failed to delete project'
        this.$toast?.error(errorMsg)
      }
    },
    confirmReset(project) {
      this.projectToReset = project
    },
    async resetProject() {
      try {
        await this.$http.post(`/api/project-admin/projects/${this.projectToReset.id}/reset/`)
        this.$toast?.success('Project reset successfully')
        this.projectToReset = null
        await this.fetchProjects()
      } catch (error) {
        console.error('Error resetting project:', error)
        const errorMsg = error.response?.data?.error || 'Failed to reset project'
        this.$toast?.error(errorMsg)
      }
    },
    getStatusClass(status) {
      const classes = {
        'A': 'badge-primary',
        'C': 'badge-success',
        'D': 'badge-danger'
      }
      return classes[status] || 'badge-secondary'
    },
    getStatusText(status) {
      const texts = {
        'A': 'Annotating',
        'C': 'Complete',
        'D': 'Discontinued'
      }
      return texts[status] || status
    }
  }
}
</script>

<style scoped lang="scss">
.project-admin-view {
  padding: 20px;
}

.project-admin-header {
  margin-bottom: 30px;

  h2 {
    margin-bottom: 5px;
  }

  .subtitle {
    color: #666;
  }
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
}

.project-list-section {
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    h3 {
      margin: 0;
    }
  }
}

.no-projects {
  text-align: center;
  padding: 40px;
  color: #666;
}

.action-buttons {
  display: flex;
  gap: 5px;

  .btn {
    padding: 4px 8px;
  }
}

.project-form-modal {
  .project-form {
    max-height: 70vh;
    overflow-y: auto;
    padding: 10px;
  }

  .form-section {
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid #eee;

    &:last-child {
      border-bottom: none;
    }

    h4 {
      margin-bottom: 15px;
      color: #333;
    }
  }

  .form-group {
    margin-bottom: 15px;

    label {
      display: block;
      margin-bottom: 5px;
      font-weight: 500;

      input[type="checkbox"] {
        margin-right: 8px;
      }
    }

    .form-control {
      width: 100%;
      padding: 8px;
      border: 1px solid #ddd;
      border-radius: 4px;
    }

    textarea.form-control {
      resize: vertical;
    }

    select[multiple].form-control {
      min-height: 100px;
    }
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #eee;
  }
}

.confirm-modal {
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 20px;
  }
}

.badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.875rem;

  &.badge-primary {
    background-color: #007bff;
    color: white;
  }

  &.badge-success {
    background-color: #28a745;
    color: white;
  }

  &.badge-danger {
    background-color: #dc3545;
    color: white;
  }

  &.badge-secondary {
    background-color: #6c757d;
    color: white;
  }
}
</style>
