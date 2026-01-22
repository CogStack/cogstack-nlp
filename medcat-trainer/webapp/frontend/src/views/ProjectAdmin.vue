<template>
  <div class="container-fluid project-admin-view">
    <div class="project-admin-header">
      <div class="header-content">
        <div class="header-text">
          <h2>Project Administration</h2>
          <p class="subtitle">Manage your annotation projects</p>
        </div>
        <button class="btn btn-primary btn-create" @click="showCreateForm = true">
          <font-awesome-icon icon="plus"></font-awesome-icon>
          <span>Create New Project</span>
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
      <span class="loading-text">Loading projects...</span>
    </div>

    <div v-else class="project-admin-content">
      <!-- Project List View -->
      <div v-if="!showCreateForm && !editingProject" class="project-list-section">
        <div class="section-header">
          <h3>
            Your Projects
            <span class="project-count">({{ projects.length }})</span>
          </h3>
        </div>

        <div v-if="projects.length > 0" class="projects-table-container">
          <v-data-table
            :items="projects"
            :headers="tableHeaders"
            :hover="true"
            @click:row="selectProject"
            hide-default-footer
            :items-per-page="-1"
            class="projects-table"
            item-class="project-row"
            dense>
            <template #item.name="{ item }">
              <div class="project-name-cell">
                <strong class="project-name">{{ item.name }}</strong>
                <span v-if="item.description" class="project-description">{{ item.description }}</span>
              </div>
            </template>
            <template #item.status="{ item }">
              <span class="badge" :class="getStatusClass(item.project_status)">
                {{ getStatusText(item.project_status) }}
              </span>
            </template>
            <template #item.dataset="{ item }">
              <span class="dataset-name">{{ getDatasetName(item.dataset) }}</span>
            </template>
            <template #item.actions="{ item }">
              <div class="action-buttons" @click.stop>
                <button
                  class="btn btn-sm btn-action btn-edit"
                  @click="editProject(item)"
                  :title="'Edit ' + item.name">
                  <font-awesome-icon icon="edit"></font-awesome-icon>
                </button>
                <button
                  class="btn btn-sm btn-action btn-reset"
                  @click="confirmReset(item)"
                  :title="'Reset ' + item.name">
                  <font-awesome-icon icon="undo"></font-awesome-icon>
                </button>
                <button
                  class="btn btn-sm btn-action btn-delete"
                  @click="confirmDelete(item)"
                  :title="'Delete ' + item.name">
                  <font-awesome-icon icon="trash"></font-awesome-icon>
                </button>
              </div>
            </template>
          </v-data-table>
        </div>

        <div v-else class="no-projects">
          <div class="empty-state">
            <h4>No Projects Yet</h4>
            <p>You don't have any projects yet. Create one to get started!</p>
            <button class="btn btn-primary btn-create-empty" @click="showCreateForm = true">
              <font-awesome-icon icon="plus"></font-awesome-icon>
              <span>Create Your First Project</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Project Form View (replaces list) -->
      <div v-else class="project-form-section">
        <div class="form-header">
          <button class="btn btn-back" @click="closeForm">
            <font-awesome-icon icon="arrow-left"></font-awesome-icon>
            <span>Back</span>
          </button>
          <h3>{{ editingProject ? 'Edit Project' : 'Create New Project' }}</h3>
        </div>
        <div class="form-content">
          <form @submit.prevent="saveProject" class="project-form">

            <div class="form-section form-section-horizontal">
              <h4>Basic Information</h4>
              <div class="form-row">
                <div class="form-group form-group-inline">
                  <label>Project Name *</label>
                  <input v-model="formData.name" type="text" class="form-control" required placeholder="Enter project name" />
                </div>
                <div class="form-group form-group-inline">
                  <label>Dataset *</label>
                  <select v-model="formData.dataset" class="form-control" required>
                    <option :value="null">Select a dataset</option>
                    <option v-for="ds in datasets" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
                  </select>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group form-group-inline">
                  <label>Description</label>
                  <textarea v-model="formData.description" class="form-control" rows="2" placeholder="Enter project description"></textarea>
                </div>
                <div class="form-group form-group-inline">
                  <label>Annotation Guideline Link</label>
                  <input v-model="formData.annotation_guideline_link" type="url" class="form-control" placeholder="https://..." />
                </div>
              </div>
            </div>

            <div class="form-section form-section-horizontal">
              <h4>Project Settings</h4>
              <div class="form-row">
                <div class="form-group form-group-inline">
                  <label>Project Status</label>
                  <select v-model="formData.project_status" class="form-control">
                    <option value="A">Annotating</option>
                    <option value="C">Complete</option>
                    <option value="D">Discontinued (Fail)</option>
                  </select>
                </div>
                <div class="form-group checkbox-group form-group-inline">
                  <label class="checkbox-label">
                    <input v-model="formData.project_locked" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Project Locked</span>
                  </label>
                </div>
                <div class="form-group checkbox-group form-group-inline">
                  <label class="checkbox-label">
                    <input v-model="formData.annotation_classification" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Annotation Classification</span>
                  </label>
                </div>
              </div>
            </div>

            <div class="form-section form-section-horizontal">
              <h4>Model Configuration</h4>
              <div class="form-row">
                <div class="form-group form-group-inline">
                  <label>Model Pack</label>
                  <select v-model="formData.model_pack" class="form-control">
                    <option :value="null">None</option>
                    <option v-for="mp in modelPacks" :key="mp.id" :value="mp.id">{{ mp.name }}</option>
                  </select>
                </div>
                <div class="form-group checkbox-group form-group-inline">
                  <label class="checkbox-label">
                    <input v-model="useBackupOption" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Use backup option</span>
                  </label>
                </div>
              </div>
              <div v-if="useBackupOption" class="form-row backup-options">
                <div class="form-group form-group-inline">
                  <label>Concept DB</label>
                  <select v-model="formData.concept_db" class="form-control">
                    <option :value="null">None</option>
                    <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
                  </select>
                </div>
                <div class="form-group form-group-inline">
                  <label>Vocabulary</label>
                  <select v-model="formData.vocab" class="form-control">
                    <option :value="null">None</option>
                    <option v-for="vocab in vocabs" :key="vocab.id" :value="vocab.id">{{ vocab.name }}</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="form-section">
              <h4>Annotation Settings</h4>
              <div class="checkbox-grid">
                <div class="form-group checkbox-group">
                  <label class="checkbox-label">
                    <input v-model="formData.require_entity_validation" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Require Entity Validation</span>
                  </label>
                </div>
                <div class="form-group checkbox-group">
                  <label class="checkbox-label">
                    <input v-model="formData.train_model_on_submit" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Train Model on Submit</span>
                  </label>
                </div>
                <div class="form-group checkbox-group">
                  <label class="checkbox-label">
                    <input v-model="formData.add_new_entities" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Add New Entities</span>
                  </label>
                </div>
                <div class="form-group checkbox-group">
                  <label class="checkbox-label">
                    <input v-model="formData.restrict_concept_lookup" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Restrict Concept Lookup</span>
                  </label>
                </div>
                <div class="form-group checkbox-group">
                  <label class="checkbox-label">
                    <input v-model="formData.terminate_available" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Terminate Available</span>
                  </label>
                </div>
                <div class="form-group checkbox-group">
                  <label class="checkbox-label">
                    <input v-model="formData.irrelevant_available" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Irrelevant Available</span>
                  </label>
                </div>
                <div class="form-group checkbox-group">
                  <label class="checkbox-label">
                    <input v-model="formData.enable_entity_annotation_comments" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Enable Entity Annotation Comments</span>
                  </label>
                </div>
              </div>
            </div>

            <div class="form-section form-section-horizontal">
              <h4>Concept Filtering</h4>
              <div class="form-row">
                <div class="form-group form-group-inline">
                  <label>CUIs (comma-separated)</label>
                  <textarea v-model="formData.cuis" class="form-control" rows="2"
                            placeholder="e.g., C1234567, C7654321"></textarea>
                </div>
                <div class="form-group form-group-inline">
                  <label>CUI File</label>
                  <input type="file" @change="handleCuiFileChange" accept=".json" class="form-control file-input" />
                  <small class="form-text text-muted">JSON file containing array of CUI strings</small>
                </div>
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
              <button type="button" class="btn btn-secondary btn-cancel" @click="closeForm">
                <span>Cancel</span>
              </button>
              <button type="submit" class="btn btn-primary btn-save" :disabled="saving">
                <font-awesome-icon v-if="saving" icon="spinner" spin></font-awesome-icon>
                <span>{{ saving ? 'Saving...' : 'Save Project' }}</span>
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Delete Confirmation Modal -->
      <modal v-if="projectToDelete" :closable="true" @modal:close="projectToDelete = null" class="confirm-modal">
        <template #header>
          <h3>Confirm Delete</h3>
        </template>
        <template #body>
          <div class="confirm-content">
            <p>Are you sure you want to delete the project <strong class="project-name-highlight">{{ projectToDelete.name }}</strong>?</p>
            <p class="text-danger warning-text">This action cannot be undone.</p>
            <div class="form-actions">
              <button class="btn btn-secondary" @click="projectToDelete = null">Cancel</button>
              <button class="btn btn-danger" @click="deleteProject">Delete</button>
            </div>
          </div>
        </template>
      </modal>

      <!-- Reset Confirmation Modal -->
      <modal v-if="projectToReset" :closable="true" @modal:close="projectToReset = null" class="confirm-modal">
        <template #header>
          <h3>Confirm Reset</h3>
        </template>
        <template #body>
          <div class="confirm-content">
            <p>Are you sure you want to reset the project <strong class="project-name-highlight">{{ projectToReset.name }}</strong>?</p>
            <p class="text-warning warning-text">This will remove all annotations and clear validated/prepared documents.</p>
            <div class="form-actions">
              <button class="btn btn-secondary" @click="projectToReset = null">Cancel</button>
              <button class="btn btn-warning" @click="resetProject">Reset</button>
            </div>
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
      useBackupOption: false,
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
      // Show backup options if CDB or Vocab are set
      this.useBackupOption = !!(project.concept_db || project.vocab)
      this.showCreateForm = true
    },
    closeForm() {
      this.showCreateForm = false
      this.editingProject = null
      this.useBackupOption = false
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
      this.useBackupOption = false
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

        // If not using backup option, clear CDB and Vocab
        if (!this.useBackupOption) {
          this.formData.concept_db = null
          this.formData.vocab = null
        }

        // CDB Search Filter is hidden - will use ModelPack by default
        // Clear it so backend uses ModelPack
        this.formData.cdb_search_filter = []

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
    },
    getStatusIcon(status) {
      const icons = {
        'A': 'spinner',
        'C': 'check-circle',
        'D': 'times-circle'
      }
      return icons[status] || 'circle'
    },
    getDatasetName(datasetId) {
      const dataset = this.datasets.find(ds => ds.id === datasetId)
      return dataset ? dataset.name : 'N/A'
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/variables.scss';

.project-admin-view {
  padding: 30px;
  max-width: 1400px;
  margin: 0 auto;
  background: var(--color-background);
}

.project-admin-header {
  margin-bottom: 40px;
  padding-bottom: 20px;
  border-bottom: 2px solid var(--color-border);

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
  }

  .header-text {
    flex: 1;

    h2 {
      margin-bottom: 8px;
      font-size: 2rem;
      font-weight: 600;
      color: var(--color-heading);
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .subtitle {
      color: var(--color-text);
      opacity: 0.7;
      font-size: 1rem;
      margin: 0;
    }
  }

  .btn-create {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px;
    font-weight: 500;
    border-radius: 6px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(0, 114, 206, 0.2);

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 8px rgba(0, 114, 206, 0.3);
    }

    svg {
      font-size: 0.9rem;
    }
  }
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 80px 40px;
  min-height: 400px;

  .loading-text {
    color: var(--color-text);
    font-size: 1.1rem;
    opacity: 0.8;
  }
}

.project-list-section {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

  .section-header {
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--color-border);

    h3 {
      margin: 0;
      font-size: 1.3rem;
      font-weight: 600;
      color: var(--color-heading);

      .project-count {
        font-size: 0.9rem;
        font-weight: 400;
        color: var(--color-text);
        opacity: 0.6;
        margin-left: 8px;
      }
    }
  }
}

.projects-table-container {
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid var(--color-border);

  .projects-table {
    :deep(.project-row) {
      cursor: pointer;
      transition: background-color 0.2s ease;

      &:hover {
        background-color: rgba(0, 114, 206, 0.05);
      }
    }

    :deep(th) {
      background-color: #f8f9fa;
      font-weight: 600;
      color: var(--color-heading);
      text-transform: uppercase;
      font-size: 0.7rem;
      letter-spacing: 0.5px;
      padding: 8px 12px;
    }

    :deep(td) {
      padding: 8px 12px;
      vertical-align: middle;
    }
  }
}

.project-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .project-name {
    font-size: 0.95rem;
    color: var(--color-heading);
    margin: 0;
    font-weight: 500;
  }

  .project-description {
    font-size: 0.8rem;
    color: var(--color-text);
    opacity: 0.6;
    max-width: 400px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.dataset-name {
  color: var(--color-text);
  font-size: 0.9rem;
}

.action-buttons {
  display: flex;
  gap: 6px;
  justify-content: flex-end;

  .btn-action {
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 32px;
    font-size: 0.85rem;

    &:hover {
      transform: translateY(-1px);
    }

    &.btn-edit {
      color: $primary;
      border-color: $primary;

      &:hover {
        background-color: $primary;
        color: white;
      }
    }

    &.btn-reset {
      color: $warning;
      border-color: $warning;

      &:hover {
        background-color: $warning;
        color: white;
      }
    }

    &.btn-delete {
      color: $danger;
      border-color: $danger;

      &:hover {
        background-color: $danger;
        color: white;
      }
    }
  }
}

.no-projects {
  padding: 60px 40px;
  text-align: center;

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;

    h4 {
      font-size: 1.5rem;
      color: var(--color-heading);
      margin: 0;
    }

    p {
      color: var(--color-text);
      opacity: 0.7;
      font-size: 1rem;
      margin: 0;
      max-width: 400px;
    }

    .btn-create-empty {
      margin-top: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 24px;
      font-weight: 500;
      border-radius: 6px;
      transition: all 0.2s ease;
      box-shadow: 0 2px 4px rgba(0, 114, 206, 0.2);

      &:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0, 114, 206, 0.3);
      }
    }
  }
}

.badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
  white-space: nowrap;

  &.badge-primary {
    background-color: rgba(0, 114, 206, 0.1);
    color: $primary;
    border: 1px solid rgba(0, 114, 206, 0.2);
  }

  &.badge-success {
    background-color: rgba(0, 150, 57, 0.1);
    color: $success;
    border: 1px solid rgba(0, 150, 57, 0.2);
  }

  &.badge-danger {
    background-color: rgba(218, 41, 28, 0.1);
    color: $danger;
    border: 1px solid rgba(218, 41, 28, 0.2);
  }

  &.badge-secondary {
    background-color: rgba(108, 117, 125, 0.1);
    color: #6c757d;
    border: 1px solid rgba(108, 117, 125, 0.2);
  }
}

// Project Form Section (Full Screen)
.project-form-section {
  background: white;
  border-radius: 8px;
  padding: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 200px);
  min-height: 600px;

  .form-header {
    padding: 12px 20px;
    border-bottom: 1px solid var(--color-border);
    background: linear-gradient(135deg, $primary 0%, darken($primary, 10%) 100%);
    color: white;
    display: flex;
    align-items: center;
    gap: 12px;

    .btn-back {
      background: rgba(255, 255, 255, 0.2);
      border: 1px solid rgba(255, 255, 255, 0.3);
      color: white;
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 4px;
      transition: all 0.2s ease;
      font-weight: 500;
      font-size: 0.9rem;

      &:hover {
        background: rgba(255, 255, 255, 0.3);
        transform: translateX(-2px);
      }

      svg {
        font-size: 0.85rem;
      }
    }

    h3 {
      margin: 0;
      font-size: 1.1rem;
      font-weight: 600;
      color: white;
    }
  }

  .form-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
  }

  .project-form {
    padding: 0;
    max-width: 1400px;
    margin: 0 auto;
  }

  .form-section {
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--color-border);

    &:last-child {
      border-bottom: none;
      margin-bottom: 0;
      padding-bottom: 0;
    }

    h4 {
      margin-bottom: 12px;
      color: var(--color-heading);
      font-size: 1rem;
      font-weight: 600;
    }

    &.form-section-horizontal {
      .form-row {
        display: flex;
        gap: 16px;
        align-items: flex-start;
        flex-wrap: wrap;

        .form-group-inline {
          flex: 1;
          min-width: 200px;
          margin-bottom: 12px;
        }
      }

      .backup-options {
        margin-top: 12px;
        padding-top: 12px;
        border-top: 1px solid var(--color-border);
      }
    }
  }

  .form-group {
    margin-bottom: 12px;

    label {
      display: block;
      margin-bottom: 4px;
      font-weight: 500;
      color: var(--color-heading);
      font-size: 0.9rem;
    }

    &.form-group-inline {
      margin-bottom: 0;
    }

    .form-control {
      width: 100%;
      padding: 6px 10px;
      border: 1px solid var(--color-border);
      border-radius: 4px;
      font-size: 0.9rem;
      transition: all 0.2s ease;
      background: white;

      &:focus {
        outline: none;
        border-color: $primary;
        box-shadow: 0 0 0 2px rgba(0, 114, 206, 0.1);
      }

      &::placeholder {
        color: var(--color-text);
        opacity: 0.5;
      }
    }

    textarea.form-control {
      resize: vertical;
      min-height: 60px;
    }

    select[multiple].form-control {
      min-height: 120px;
    }

    .file-input {
      padding: 8px;
      cursor: pointer;

      &::file-selector-button {
        padding: 8px 16px;
        margin-right: 12px;
        border: 1px solid var(--color-border);
        border-radius: 4px;
        background: #f8f9fa;
        cursor: pointer;
        transition: all 0.2s ease;

        &:hover {
          background: #e9ecef;
        }
      }
    }

    .form-text {
      display: block;
      margin-top: 6px;
      font-size: 0.85rem;
      color: var(--color-text);
      opacity: 0.7;
    }
  }

  .checkbox-group {
    margin-bottom: 8px;

    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      padding: 4px 0;
      transition: opacity 0.2s ease;
      margin-bottom: 0;

      &:hover {
        opacity: 0.8;
      }

      .checkbox-input {
        margin: 0;
        width: 16px;
        height: 16px;
        cursor: pointer;
        accent-color: $primary;
        flex-shrink: 0;
      }

      .checkbox-text {
        flex: 1;
        font-weight: 400;
        color: var(--color-text);
        font-size: 0.85rem;
        line-height: 1.3;
      }
    }

    &.form-group-inline {
      margin-bottom: 0;
      align-self: center;
    }
  }

  .checkbox-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 8px;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--color-border);

    .btn {
      padding: 8px 20px;
      font-weight: 500;
      border-radius: 4px;
      font-size: 0.9rem;
      transition: all 0.2s ease;

      &:hover {
        transform: translateY(-1px);
      }

      &.btn-save {
        box-shadow: 0 2px 4px rgba(0, 114, 206, 0.2);

        &:hover {
          box-shadow: 0 4px 8px rgba(0, 114, 206, 0.3);
        }
      }
    }
  }
}

.confirm-modal {
  :deep(.modal-container) {
    width: 500px;
    border-radius: 8px;
  }

  :deep(.modal-header) {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    padding: 20px 24px;
    margin: 0;
    border-bottom: 1px solid var(--color-border);

    h3 {
      color: var(--color-heading);
      margin: 0;
    }
  }

  :deep(.modal-body) {
    padding: 24px;
  }

  .confirm-content {
    .project-name-highlight {
      color: $primary;
      font-weight: 600;
    }

    .warning-text {
      padding: 12px;
      background-color: rgba(218, 41, 28, 0.1);
      border-left: 3px solid $danger;
      border-radius: 4px;
      margin: 16px 0;
    }

    .text-warning {
      padding: 12px;
      background-color: rgba(118, 134, 146, 0.1);
      border-left: 3px solid $warning;
      border-radius: 4px;
      margin: 16px 0;
    }
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;

    .btn {
      padding: 10px 20px;
      font-weight: 500;
      border-radius: 6px;
      transition: all 0.2s ease;

      &:hover {
        transform: translateY(-1px);
      }
    }
  }
}

// Responsive design
@media (max-width: 768px) {
  .project-admin-view {
    padding: 20px 15px;
  }

  .project-admin-header {
    .header-content {
      flex-direction: column;
      align-items: stretch;

      .btn-create {
        width: 100%;
        justify-content: center;
      }
    }
  }

  .projects-table-container {
    :deep(table) {
      font-size: 0.85rem;
    }

    :deep(th),
    :deep(td) {
      padding: 6px 8px;
    }
  }

  .project-form-section {
    height: calc(100vh - 150px);
    min-height: 500px;

    .form-header {
      padding: 10px 16px;

      h3 {
        font-size: 1rem;
      }

      .btn-back {
        padding: 4px 10px;
        font-size: 0.85rem;
      }
    }

    .form-content {
      padding: 12px 16px;
    }

    .form-section {
      margin-bottom: 16px;
      padding-bottom: 12px;

      h4 {
        font-size: 0.95rem;
        margin-bottom: 8px;
      }

      .form-row {
        flex-direction: column;
        gap: 12px;

        .form-group-inline {
          min-width: 100%;
        }
      }
    }

    .form-group {
      margin-bottom: 10px;

      label {
        font-size: 0.85rem;
        margin-bottom: 3px;
      }
    }
  }

  .checkbox-grid {
    grid-template-columns: 1fr;
  }
}
</style>
