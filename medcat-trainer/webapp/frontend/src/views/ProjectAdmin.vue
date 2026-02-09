<template>
  <div class="container-fluid project-admin-view">
    <div class="project-admin-header">
      <div class="header-content">
        <div class="header-text">
          <h2>Project Administration</h2>
          <p class="subtitle">Manage your annotation projects</p>
        </div>
        <div class="header-actions">
          <button v-if="activeTab === 'projects'" class="btn btn-primary btn-create" @click="showCreateForm = true">
            <font-awesome-icon icon="plus"></font-awesome-icon>
            <span>Create New Project</span>
          </button>
          <button v-if="activeTab === 'modelpacks'" class="btn btn-primary btn-create" @click="showModelPackForm = true; editingModelPack = null">
            <font-awesome-icon icon="plus"></font-awesome-icon>
            <span>Add Model Pack</span>
          </button>
          <button v-if="activeTab === 'datasets'" class="btn btn-primary btn-create" @click="showDatasetForm = true; editingDataset = null">
            <font-awesome-icon icon="plus"></font-awesome-icon>
            <span>Add Dataset</span>
          </button>
          <button v-if="activeTab === 'users'" class="btn btn-primary btn-create" @click="showUserForm = true; editingUser = null">
            <font-awesome-icon icon="plus"></font-awesome-icon>
            <span>Add User</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="admin-tabs">
      <button
        class="tab-button"
        :class="{ active: activeTab === 'projects' }"
        @click="activeTab = 'projects'; closeAllForms()">
        <font-awesome-icon icon="folder"></font-awesome-icon>
        Projects
      </button>
      <button
        class="tab-button"
        :class="{ active: activeTab === 'modelpacks' }"
        @click="activeTab = 'modelpacks'; closeAllForms()">
        <font-awesome-icon icon="box"></font-awesome-icon>
        Model Packs
      </button>
      <button
        class="tab-button"
        :class="{ active: activeTab === 'datasets' }"
        @click="activeTab = 'datasets'; closeAllForms()">
        <font-awesome-icon icon="database"></font-awesome-icon>
        Datasets
      </button>
      <button
        class="tab-button"
        :class="{ active: activeTab === 'users' }"
        @click="activeTab = 'users'; closeAllForms()">
        <font-awesome-icon icon="users"></font-awesome-icon>
        Users
      </button>
    </div>

    <div v-if="loading" class="loading-container">
      <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
      <span class="loading-text">Loading...</span>
    </div>

    <div v-else class="project-admin-content">
      <!-- Projects Tab -->
      <div v-if="activeTab === 'projects'" class="tab-content">
      <!-- Project List View -->
      <projects-list
        v-if="!showCreateForm && !editingProject"
        :projects="projects"
        :datasets="datasets"
        @select-project="selectProject"
        @clone-project="cloneProject"
        @confirm-reset="confirmReset"
        @confirm-delete="confirmDelete"
        @create-project="showCreateForm = true"
      />

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
            <div class="form-sections-wrapper">
            <div class="form-section form-section-horizontal">
              <h4>Basic Information</h4>
              <div class="form-row">
                <div class="form-group form-group-inline">
                  <label>Project Name *</label>
                  <input
                    v-model="formData.name"
                    type="text"
                    name="name"
                    data-field="name"
                    class="form-control"
                    :class="{ 'is-invalid': validationErrors.name }"
                    required
                    placeholder="Enter project name"
                    @invalid="handleInvalid($event)"
                    @input="clearValidationError('name')"
                  />
                  <small v-if="validationErrors.name" class="form-text text-danger">{{ validationErrors.name }}</small>
                </div>
                <div class="form-group form-group-inline">
                  <label>Dataset *</label>
                  <select
                    v-model="formData.dataset"
                    name="dataset"
                    data-field="dataset"
                    class="form-control"
                    :class="{ 'is-invalid': validationErrors.dataset }"
                    required
                    @invalid="handleInvalid($event)"
                    @change="clearValidationError('dataset')"
                  >
                    <option :value="null">Select a dataset</option>
                    <option v-for="ds in datasets" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
                  </select>
                  <small v-if="validationErrors.dataset" class="form-text text-danger">{{ validationErrors.dataset }}</small>
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
                  <label>Local Model Pack</label>
                  <select
                    v-model="formData.model_pack"
                    name="model_pack"
                    data-field="model_pack"
                    class="form-control"
                    :class="{ 'is-invalid': validationErrors.model_pack }"
                    :disabled="useBackupOption || formData.use_model_service"
                    @change="clearValidationError('model_pack')"
                  >
                    <option :value="null">None</option>
                    <option v-for="mp in modelPacks" :key="mp.id" :value="mp.id">{{ mp.name }}</option>
                  </select>
                  <small v-if="validationErrors.model_pack" class="form-text text-danger">{{ validationErrors.model_pack }}</small>
                </div>
                <div class="form-group checkbox-group form-group-inline">
                  <label class="checkbox-label">
                    <input v-model="useBackupOption" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Use Concept DB / Vocabulary pair</span>
                  </label>
                </div>
              </div>
              <div v-if="useBackupOption" class="form-row backup-options">
                <div class="form-group form-group-inline">
                  <label>Concept DB *</label>
                  <select
                    v-model="formData.concept_db"
                    name="concept_db"
                    data-field="concept_db"
                    class="form-control"
                    :class="{ 'is-invalid': validationErrors.concept_db }"
                    @change="clearValidationError('concept_db')"
                  >
                    <option :value="null">None</option>
                    <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
                  </select>
                  <small v-if="validationErrors.concept_db" class="form-text text-danger">{{ validationErrors.concept_db }}</small>
                </div>
                <div class="form-group form-group-inline">
                  <label>Vocabulary *</label>
                  <select
                    v-model="formData.vocab"
                    name="vocab"
                    data-field="vocab"
                    class="form-control"
                    :class="{ 'is-invalid': validationErrors.vocab }"
                    @change="clearValidationError('vocab')"
                  >
                    <option :value="null">None</option>
                    <option v-for="vocab in vocabs" :key="vocab.id" :value="vocab.id">{{ vocab.name }}</option>
                  </select>
                  <small v-if="validationErrors.vocab" class="form-text text-danger">{{ validationErrors.vocab }}</small>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group checkbox-group form-group-inline">
                  <label class="checkbox-label">
                    <input v-model="formData.use_model_service" type="checkbox" class="checkbox-input" />
                    <span class="checkbox-text">Use remote MedCAT service API for document processing instead of local models</span>
                  </label>
                </div>
              </div>
              <div v-if="formData.use_model_service" class="form-row">
                <div class="form-group form-group-inline" style="flex: 1 1 100%;">
                  <label>Remote Model Service URL *</label>
                  <input
                    v-model="formData.model_service_url"
                    type="url"
                    name="model_service_url"
                    data-field="model_service_url"
                    class="form-control"
                    :class="{ 'is-invalid': validationErrors.model_service_url }"
                    :required="formData.use_model_service"
                    placeholder="http://medcat-service:8000"
                    @invalid="handleInvalid($event)"
                    @input="clearValidationError('model_service_url')"
                  />
                  <small v-if="validationErrors.model_service_url" class="form-text text-danger">{{ validationErrors.model_service_url }}</small>
                  <small v-else class="form-text text-muted">URL of the remote MedCAT service API (e.g., http://medcat-service:8000). Note: interim model training is not supported for remote model service projects.</small>
                </div>
              </div>
              <div v-if="validationErrors.model_config" class="form-row">
                <div class="form-group" style="flex: 1 1 100%;">
                  <small class="form-text text-danger">{{ validationErrors.model_config }}</small>
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

            <div class="form-section">
              <h4>Concept Filtering</h4>
              <div class="cui-filter-controls">
                <label class="cui-filter-checkbox">
                  <input type="checkbox" v-model="includeSubConcepts" />
                  Incl. Sub-concepts
                </label>
                <button
                  type="button"
                  class="btn btn-link btn-sm cui-filter-paste-toggle"
                  @click="showCuiFilterTextarea = !showCuiFilterTextarea"
                >
                  {{ showCuiFilterTextarea ? 'Hide box' : 'Paste CUIs (optional)' }}
                </button>
              </div>

              <div class="cui-filter-row">
                <div class="cui-filter-picker">
                  <div v-if="!getConceptDbForPicker()" class="text-muted small">
                    Please select a Model Pack or enable backup option with Concept DB.
                  </div>
                  <concept-picker
                    v-else
                    :key="`concept-picker-${getConceptDbForPicker()}`"
                    :restrict_concept_lookup="false"
                    :cui_filter="''"
                    :cdb_search_filter="[]"
                    :concept_db="getConceptDbForPicker()"
                    :selection="''"
                    @pickedResult:concept="addCuiToFilter"
                  />
                </div>
                <div class="cui-file-picker">
                  <label>CUI File</label>
                  <input type="file" @change="handleCuiFileChange" accept=".json" class="form-control file-input" />
                  <small class="form-text text-muted">JSON file containing array of CUI strings</small>
                </div>
              </div>

              <div v-if="selectedCuiFilterConcepts.length > 0" class="cui-pill-row">
                <span class="cui-pill" v-for="item in selectedCuiFilterConcepts" :key="item.cui" :title="item.name || item.cui">
                  <span class="cui-pill-text">{{ item.cui }} - {{ item.name }}</span>
                  <button type="button" class="cui-pill-remove" @click="removeCuiFromFilter(item.cui)">×</button>
                </span>
              </div>

              <textarea
                v-if="showCuiFilterTextarea"
                v-model="formData.cuis"
                class="form-control"
                rows="2"
                placeholder="Optional: paste comma separated list e.g. 91175000, 84757009"
                @blur="syncPillsFromCuiText"
              ></textarea>
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
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary" @click="closeForm">Cancel</button>
              <button type="submit" class="btn btn-primary" :disabled="saving">
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

      <!-- Clone Project Modal -->
      <modal v-if="projectToClone" :closable="true" @modal:close="closeCloneModal" class="confirm-modal">
        <template #header>
          <h3>Clone Project</h3>
        </template>
        <template #body>
          <div class="confirm-content">
            <p>Enter a name for the cloned project:</p>
            <div class="form-group" style="margin-top: 16px;">
              <input
                v-model="cloneName"
                type="text"
                class="form-control"
                placeholder="Enter project name"
                @keyup.enter="performClone"
                ref="cloneNameInput"
              />
            </div>
            <div class="form-actions" style="margin-top: 20px;">
              <button class="btn btn-secondary" @click="closeCloneModal">Cancel</button>
              <button class="btn btn-success" @click="performClone" :disabled="!cloneName || cloneName.trim() === ''">Clone</button>
            </div>
          </div>
        </template>
      </modal>
      </div>
      <!-- End Projects Tab -->

      <!-- Model Packs Tab -->
      <div v-if="activeTab === 'modelpacks'" class="tab-content admin-section">
        <model-packs-list
          v-if="!showModelPackForm && !editingModelPack"
          :model-packs="modelPacks"
          :concept-dbs="conceptDbs"
          :vocabs="vocabs"
          @select-model-pack="selectModelPack"
          @confirm-delete-model-pack="confirmDeleteModelPack"
          @add-model-pack="showModelPackForm = true; editingModelPack = null"
        />

        <!-- Model Pack Form -->
        <model-pack-form
          v-else
          :editing="!!editingModelPack"
          :model-pack="editingModelPack"
          :concept-dbs="conceptDbs"
          :vocabs="vocabs"
          :saving="saving"
          @close="closeModelPackForm"
          @save="handleModelPackSave"
        />
      </div>
      <!-- End Model Packs Tab -->

      <!-- Datasets Tab -->
      <div v-if="activeTab === 'datasets'" class="tab-content admin-section">
        <datasets-list
          v-if="!showDatasetForm && !editingDataset"
          :datasets="datasets"
          @select-dataset="selectDataset"
          @confirm-delete-dataset="confirmDeleteDataset"
          @add-dataset="showDatasetForm = true; editingDataset = null"
        />

        <!-- Dataset Form -->
        <dataset-form
          v-else
          :editing="!!editingDataset"
          :dataset="editingDataset"
          :saving="saving"
          @close="closeDatasetForm"
          @save="handleDatasetSave"
        />
      </div>
      <!-- End Datasets Tab -->

      <!-- Users Tab -->
      <div v-if="activeTab === 'users'" class="tab-content admin-section">
        <users-list
          v-if="!showUserForm && !editingUser"
          :users="users"
          @select-user="selectUser"
          @add-user="showUserForm = true; editingUser = null"
        />

        <!-- User Form -->
        <user-form
          v-else
          :editing="!!editingUser"
          :user="editingUser"
          :saving="saving"
          @close="closeUserForm"
          @save="handleUserSave"
        />
      </div>
      <!-- End Users Tab -->

      <!-- Delete Modals -->
      <modal v-if="modelPackToDelete" :closable="true" @modal:close="modelPackToDelete = null" class="confirm-modal">
        <template #header><h3>Confirm Delete</h3></template>
        <template #body>
          <div class="confirm-content">
            <p>Are you sure you want to delete the model pack <strong>{{ modelPackToDelete.name }}</strong>?</p>
            <p class="text-danger warning-text">This action cannot be undone.</p>
            <div class="form-actions">
              <button class="btn btn-secondary" @click="modelPackToDelete = null">Cancel</button>
              <button class="btn btn-danger" @click="deleteModelPack">Delete</button>
            </div>
          </div>
        </template>
      </modal>

      <modal v-if="datasetToDelete" :closable="true" @modal:close="datasetToDelete = null" class="confirm-modal">
        <template #header><h3>Confirm Delete</h3></template>
        <template #body>
          <div class="confirm-content">
            <p>Are you sure you want to delete the dataset <strong>{{ datasetToDelete.name }}</strong>?</p>
            <p class="text-danger warning-text">This action cannot be undone.</p>
            <div class="form-actions">
              <button class="btn btn-secondary" @click="datasetToDelete = null">Cancel</button>
              <button class="btn btn-danger" @click="deleteDataset">Delete</button>
            </div>
          </div>
        </template>
      </modal>

    </div>
  </div>
</template>

<script>
import Modal from '@/components/common/Modal.vue'
import ConceptPicker from '@/components/common/ConceptPicker.vue'
import ProjectsList from '@/components/admin/ProjectsList.vue'
import ModelPacksList from '@/components/admin/ModelPacksList.vue'
import ModelPackForm from '@/components/admin/ModelPackForm.vue'
import DatasetsList from '@/components/admin/DatasetsList.vue'
import DatasetForm from '@/components/admin/DatasetForm.vue'
import UsersList from '@/components/admin/UsersList.vue'
import UserForm from '@/components/admin/UserForm.vue'

export default {
  name: 'ProjectAdmin',
  components: {
    Modal,
    ConceptPicker,
    ProjectsList,
    ModelPacksList,
    ModelPackForm,
    DatasetsList,
    DatasetForm,
    UsersList,
    UserForm
  },
  data() {
    return {
      activeTab: 'projects',
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
      projectToClone: null,
      cloneName: '',
      saving: false,
      useBackupOption: false,
      selectedCuiFilterConcepts: [],
      includeSubConcepts: false,
      showCuiFilterTextarea: false,
      // Model Pack management
      showModelPackForm: false,
      editingModelPack: null,
      modelPackToDelete: null,
      // Dataset management
      showDatasetForm: false,
      editingDataset: null,
      datasetToDelete: null,
      // User management
      showUserForm: false,
      editingUser: null,
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
        use_model_service: false,
        model_service_url: '',
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
      validationErrors: {},
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
    selectProject(event, { item }) {
      // v-data-table click:row passes (event, { item })
      this.editProject(item)
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
        use_model_service: project.use_model_service || false,
        model_service_url: project.model_service_url || '',
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
      // Initialize CUI filter concepts from existing cuis
      if (project.cuis) {
        this.syncPillsFromCuiText()
      } else {
        this.selectedCuiFilterConcepts = []
      }
      this.showCreateForm = true
    },
    closeForm() {
      this.showCreateForm = false
      this.editingProject = null
      this.useBackupOption = false
      this.validationErrors = {}
      this.selectedCuiFilterConcepts = []
      this.includeSubConcepts = false
      this.showCuiFilterTextarea = false
      this.resetForm()
    },
    closeAllForms() {
      this.closeForm()
      this.closeModelPackForm()
      this.closeDatasetForm()
      this.closeUserForm()
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
        use_model_service: false,
        model_service_url: '',
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
      this.selectedCuiFilterConcepts = []
      this.includeSubConcepts = false
      this.showCuiFilterTextarea = false
    },
    handleCuiFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.formData.cuis_file = file
      }
    },
    parseCuis(text) {
      if (!text) return []
      return text
        .split(/[,;\n\r\t]+/g)
        .map(s => s.trim())
        .filter(Boolean)
    },
    syncCuiTextFromPills() {
      const cuis = this.selectedCuiFilterConcepts.map(c => c.cui).filter(Boolean)
      this.formData.cuis = cuis.join(',')
    },
    syncPillsFromCuiText() {
      const cuis = this.parseCuis(this.formData.cuis)
      const existingByCui = Object.assign({}, ...this.selectedCuiFilterConcepts.map(item => ({ [item.cui]: item })))
      this.selectedCuiFilterConcepts = cuis.map(cui => existingByCui[cui] || { cui })
    },
    addCuiToFilter(picked) {
      if (!picked?.cui) return
      if (!this.selectedCuiFilterConcepts.find(x => x.cui === picked.cui)) {
        this.selectedCuiFilterConcepts.push({ cui: picked.cui, name: picked.name })
        this.syncCuiTextFromPills()
      }
    },
    removeCuiFromFilter(cui) {
      this.selectedCuiFilterConcepts = this.selectedCuiFilterConcepts.filter(x => x.cui !== cui)
      this.syncCuiTextFromPills()
    },
    getConceptDbForPicker() {
      // If using backup option, use the selected concept_db
      if (this.useBackupOption && this.formData.concept_db) {
        return this.formData.concept_db
      }
      // Otherwise, try to get concept_db from selected model_pack
      if (this.formData.model_pack) {
        const modelPack = this.modelPacks.find(mp => mp.id === this.formData.model_pack)
        return modelPack?.concept_db || null
      }
      return null
    },
    handleInvalid(event) {
      // Prevent browser's default validation message popup
      event.preventDefault()
      const field = event.target
      const fieldName = field.name || field.id || field.getAttribute('data-field')
      if (fieldName && this.validationErrors[fieldName]) {
        field.setCustomValidity(this.validationErrors[fieldName])
      }
    },
    clearValidationError(fieldName) {
      if (this.validationErrors[fieldName]) {
        delete this.validationErrors[fieldName]
        // Clear HTML5 validation state
        const field = this.$el?.querySelector(`[data-field="${fieldName}"], [name="${fieldName}"]`)
        if (field) {
          field.setCustomValidity('')
          field.classList.remove('is-invalid')
        }
      }
    },
    validateProjectForm() {
      this.validationErrors = {}
      let isValid = true

      // Required fields
      if (!this.formData.name || this.formData.name.trim() === '') {
        this.validationErrors.name = 'Project name is required'
        isValid = false
      }

      if (!this.formData.dataset) {
        this.validationErrors.dataset = 'Dataset is required'
        isValid = false
      }

      // Model configuration validation
      if (this.formData.use_model_service) {
        if (!this.formData.model_service_url || this.formData.model_service_url.trim() === '') {
          this.validationErrors.model_service_url = 'Model service URL is required when using remote model service'
          isValid = false
        }
      } else {
        // Must have either model_pack OR (concept_db AND vocab)
        const hasModelPack = !!this.formData.model_pack
        const hasBackupOption = this.useBackupOption && !!this.formData.concept_db && !!this.formData.vocab

        if (!hasModelPack && !hasBackupOption) {
          this.validationErrors.model_config = 'Must set either a Model Pack or enable backup option with Concept DB and Vocabulary'
          isValid = false
        }

        // Cannot have both model_pack and backup option
        if (hasModelPack && hasBackupOption) {
          this.validationErrors.model_config = 'Cannot set both Model Pack and Concept DB/Vocabulary pair. Use one or the other.'
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
    async saveProject() {
      // Validate before submitting
      if (!this.validateProjectForm()) {
        this.$toast?.error('Please fix the validation errors before saving')
        return
      }

      this.saving = true
      try {
        // Sync CUIs from pills before saving
        this.syncCuiTextFromPills()

        // If not using backup option, clear CDB and Vocab
        if (!this.useBackupOption) {
          this.formData.concept_db = null
          this.formData.vocab = null
        }

        // Prepare data payload - convert members to integers
        const payload = { ...this.formData }

        // Set cdb_search_filter to the linked concept_db: when using a model pack use its
        // concept_db; when using backup option use the project's concept_db.
        let conceptDbIdForFilter = null
        if (payload.model_pack) {
          const modelPack = this.modelPacks.find(mp => mp.id === payload.model_pack)
          if (modelPack?.concept_db != null) {
            conceptDbIdForFilter = typeof modelPack.concept_db === 'object' ? modelPack.concept_db.id : modelPack.concept_db
          }
        } else if (payload.concept_db) {
          conceptDbIdForFilter = payload.concept_db
        }
        payload.cdb_search_filter = conceptDbIdForFilter != null ? [conceptDbIdForFilter] : []

        // Ensure members are integers
        if (Array.isArray(payload.members)) {
          payload.members = payload.members
            .map(val => {
              if (val === null || val === undefined || val === '') return null
              const numVal = typeof val === 'string' ? parseInt(val, 10) : Number(val)
              return (!isNaN(numVal) && isFinite(numVal)) ? numVal : null
            })
            .filter(val => val !== null)
        } else {
          payload.members = []
        }

        // Ensure cdb_search_filter are integers
        if (Array.isArray(payload.cdb_search_filter)) {
          payload.cdb_search_filter = payload.cdb_search_filter
            .map(val => {
              if (val === null || val === undefined || val === '') return null
              const numVal = typeof val === 'string' ? parseInt(val, 10) : Number(val)
              return (!isNaN(numVal) && isFinite(numVal)) ? numVal : null
            })
            .filter(val => val !== null)
        } else {
          payload.cdb_search_filter = []
        }

        // Remove cuis_file from JSON payload (file uploads would need separate handling if needed)
        delete payload.cuis_file

        let response
        if (this.editingProject) {
          // Update existing project
          response = await this.$http.put(
            `/api/project-admin/projects/${this.editingProject.id}/`,
            payload
          )
        } else {
          // Create new project
          response = await this.$http.post(
            '/api/project-admin/projects/create/',
            payload
          )
        }

        // If we get here, the request was successful
        this.$toast?.success(`Project ${this.editingProject ? 'updated' : 'created'} successfully`)
        this.closeForm()
        await this.fetchProjects()
      } catch (error) {
        console.error('Error saving project:', error)
        console.error('Error response:', error.response?.data)
        let errorMsg = 'Failed to save project'
        if (error.response?.data) {
          if (typeof error.response.data === 'string') {
            errorMsg = error.response.data
          } else if (error.response.data.error) {
            errorMsg = error.response.data.error
          } else if (error.response.data.message) {
            errorMsg = error.response.data.message
          } else if (typeof error.response.data === 'object') {
            // Try to format validation errors
            const errors = Object.entries(error.response.data)
              .map(([field, messages]) => {
                const msg = Array.isArray(messages) ? messages.join(', ') : String(messages)
                return `${field}: ${msg}`
              })
              .join('; ')
            errorMsg = errors || errorMsg
          }
        }
        this.$toast?.error(errorMsg)
      } finally {
        this.saving = false
      }
    },
    cloneProject(project) {
      this.projectToClone = project
      this.cloneName = `${project.name} (Clone)`
      // Focus the input after modal opens
      this.$nextTick(() => {
        if (this.$refs.cloneNameInput) {
          this.$refs.cloneNameInput.focus()
          this.$refs.cloneNameInput.select()
        }
      })
    },
    closeCloneModal() {
      this.projectToClone = null
      this.cloneName = ''
    },
    async performClone() {
      if (!this.cloneName || this.cloneName.trim() === '') {
        this.$toast?.error('Please enter a project name')
        return
      }
      try {
        const response = await this.$http.post(
          `/api/project-admin/projects/${this.projectToClone.id}/clone/`,
          { name: this.cloneName.trim() },
          { headers: { 'Content-Type': 'application/json' } }
        )
        this.$toast?.success(`Project "${this.cloneName}" cloned successfully`)
        this.closeCloneModal()
        await this.fetchProjects()
      } catch (error) {
        console.error('Error cloning project:', error)
        const errorMsg = error.response?.data?.error || 'Failed to clone project'
        this.$toast?.error(errorMsg)
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
    },
    // Model Pack methods
    selectModelPack(event, { item }) {
      this.editModelPack(item)
    },
    editModelPack(modelPack) {
      this.editingModelPack = modelPack
      this.showModelPackForm = true
    },
    closeModelPackForm() {
      this.showModelPackForm = false
      this.editingModelPack = null
    },
    async handleModelPackSave(formData) {
      this.saving = true
      try {
        const formDataToSend = new FormData()
        formDataToSend.append('name', formData.name)
        if (formData.model_pack) {
          formDataToSend.append('model_pack', formData.model_pack)
        }
        if (formData.concept_db) {
          formDataToSend.append('concept_db', formData.concept_db)
        }
        if (formData.vocab) {
          formDataToSend.append('vocab', formData.vocab)
        }

        if (this.editingModelPack) {
          await this.$http.put(
            `/api/modelpacks/${this.editingModelPack.id}/`,
            formDataToSend,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        } else {
          await this.$http.post(
            '/api/modelpacks/',
            formDataToSend,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        }

        this.$toast?.success(`Model Pack ${this.editingModelPack ? 'updated' : 'created'} successfully`)
        this.closeModelPackForm()
        await this.fetchModelPacks()
      } catch (error) {
        console.error('Error saving model pack:', error)
        const errorMsg = error.response?.data?.message || error.response?.data?.detail || 'Failed to save model pack'
        this.$toast?.error(errorMsg)
      } finally {
        this.saving = false
      }
    },
    confirmDeleteModelPack(modelPack) {
      this.modelPackToDelete = modelPack
    },
    async deleteModelPack() {
      try {
        await this.$http.delete(`/api/modelpacks/${this.modelPackToDelete.id}/`)
        this.$toast?.success('Model Pack deleted successfully')
        this.modelPackToDelete = null
        await this.fetchModelPacks()
      } catch (error) {
        console.error('Error deleting model pack:', error)
        this.$toast?.error('Failed to delete model pack')
      }
    },
    // Dataset methods
    selectDataset(event, { item }) {
      this.editDataset(item)
    },
    editDataset(dataset) {
      this.editingDataset = dataset
      this.showDatasetForm = true
    },
    closeDatasetForm() {
      this.showDatasetForm = false
      this.editingDataset = null
    },
    async handleDatasetSave(formData) {
      this.saving = true
      try {
        const formDataToSend = new FormData()
        formDataToSend.append('name', formData.name)
        formDataToSend.append('description', formData.description || '')
        if (formData.original_file) {
          formDataToSend.append('original_file', formData.original_file)
        }

        if (this.editingDataset) {
          await this.$http.put(
            `/api/datasets/${this.editingDataset.id}/`,
            formDataToSend,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        } else {
          await this.$http.post(
            '/api/datasets/',
            formDataToSend,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        }

        this.$toast?.success(`Dataset ${this.editingDataset ? 'updated' : 'created'} successfully`)
        this.closeDatasetForm()
        await this.fetchDatasets()
      } catch (error) {
        console.error('Error saving dataset:', error)
        const errorMsg = error.response?.data?.message || error.response?.data?.detail || 'Failed to save dataset'
        this.$toast?.error(errorMsg)
      } finally {
        this.saving = false
      }
    },
    confirmDeleteDataset(dataset) {
      this.datasetToDelete = dataset
    },
    async deleteDataset() {
      try {
        await this.$http.delete(`/api/datasets/${this.datasetToDelete.id}/`)
        this.$toast?.success('Dataset deleted successfully')
        this.datasetToDelete = null
        await this.fetchDatasets()
      } catch (error) {
        console.error('Error deleting dataset:', error)
        this.$toast?.error('Failed to delete dataset')
      }
    },
    // User methods
    selectUser(event, { item }) {
      this.editUser(item)
    },
    editUser(user) {
      this.editingUser = user
      this.showUserForm = true
    },
    closeUserForm() {
      this.showUserForm = false
      this.editingUser = null
    },
    async handleUserSave(formData) {
      this.saving = true
      try {
        const data = {
          username: formData.username,
          email: formData.email || '',
          is_staff: formData.is_staff,
          is_superuser: formData.is_superuser
        }

        // Note: Password is not included in UserSerializer, so it cannot be set via API
        // User creation/update will need to be done through Django admin or a custom endpoint
        if (this.editingUser) {
          await this.$http.put(`/api/users/${this.editingUser.id}/`, data)
        } else {
          // For new users, password cannot be set via this API
          // Users should be created through Django admin or password reset flow
          await this.$http.post('/api/users/', data)
        }

        this.$toast?.success(`User ${this.editingUser ? 'updated' : 'created'} successfully`)
        this.closeUserForm()
        await this.fetchUsers()
      } catch (error) {
        console.error('Error saving user:', error)
        const errorMsg = error.response?.data?.message || error.response?.data?.detail || 'Failed to save user'
        this.$toast?.error(errorMsg)
      } finally {
        this.saving = false
      }
    },
  },
  watch: {
    'formData.cuis'(newVal) {
      // Sync pills when cuis changes externally (e.g., from file upload)
      if (newVal && this.selectedCuiFilterConcepts.length === 0) {
        this.syncPillsFromCuiText()
      }
    },
    'formData.name'() {
      if (this.validationErrors.name) {
        delete this.validationErrors.name
      }
    },
    'formData.dataset'() {
      if (this.validationErrors.dataset) {
        delete this.validationErrors.dataset
      }
    },
    'formData.model_service_url'() {
      if (this.validationErrors.model_service_url) {
        delete this.validationErrors.model_service_url
      }
    },
    'formData.model_pack'() {
      // Clear pills when model pack changes to avoid confusion
      // User can re-select concepts with the new model pack
      if (!this.editingProject) {
        this.selectedCuiFilterConcepts = []
      }
      // Clear validation errors
      if (this.validationErrors.model_pack) {
        delete this.validationErrors.model_pack
      }
      // Clear model_config error when model_pack is set
      if (this.validationErrors.model_config && this.formData.model_pack) {
        delete this.validationErrors.model_config
      }
    },
    'formData.concept_db'() {
      if (this.validationErrors.concept_db) {
        delete this.validationErrors.concept_db
      }
      // Clear model_config error when both concept_db and vocab are set
      if (this.validationErrors.model_config && this.formData.concept_db && this.formData.vocab) {
        delete this.validationErrors.model_config
      }
    },
    'formData.vocab'() {
      if (this.validationErrors.vocab) {
        delete this.validationErrors.vocab
      }
      // Clear model_config error when both concept_db and vocab are set
      if (this.validationErrors.model_config && this.formData.concept_db && this.formData.vocab) {
        delete this.validationErrors.model_config
      }
    },
    'useBackupOption'() {
      // Clear model_config error when switching modes
      if (this.validationErrors.model_config) {
        delete this.validationErrors.model_config
      }
    },
    'formData.use_model_service'() {
      // Clear model_config error when switching modes
      if (this.validationErrors.model_config) {
        delete this.validationErrors.model_config
      }
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/variables.scss';
@import '@/styles/admin.scss';

.project-admin-view {
  padding: 30px;
  max-width: 1400px;
  margin: 0 auto;
  background: var(--color-background);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 100px);
  height: calc(100vh - 100px);
  overflow: hidden;
}

.project-admin-header {
  border-bottom: 2px solid var(--color-border);
  flex-shrink: 0;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
  }

  .header-actions {
    display: flex;
    gap: 10px;
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

// Project Form Section (Full Screen)
.project-form-section {
  background: white;
  border-radius: 12px;
  padding: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;

  .form-header {
    padding: 8px 20px;
    border-bottom: 1px solid var(--color-border);
    background: linear-gradient(135deg, $primary 0%, darken($primary, 10%) 100%);
    color: white;
    display: flex;
    align-items: center;
    gap: 12px;
    border-radius: 12px 12px 0 0;
    flex-shrink: 0;

    .btn-back {
      background: rgba(255, 255, 255, 0.2);
      border: 1px solid rgba(255, 255, 255, 0.3);
      color: white;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 6px;
      transition: all 0.2s ease;
      font-weight: 500;
      font-size: 0.9rem;
      white-space: nowrap;

      &:hover {
        background: rgba(255, 255, 255, 0.3);
        transform: translateX(-2px);
      }

      svg {
        font-size: 0.9rem;
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
    overflow: hidden;
    padding: 0;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .project-form {
    padding: 0;
    max-width: 1400px;
    margin: 0 auto;
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }

  .form-sections-wrapper {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    min-height: 0;
    padding: 20px;
    background: #f8f9fa;
  }

  .form-section {
    margin-bottom: 24px;
    padding: 20px;
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    flex-shrink: 0;

    &:last-child {
      margin-bottom: 0;
    }

    h4 {
      margin-bottom: 16px;
      margin-top: 0;
      color: var(--color-heading);
      font-size: 1.05rem;
      font-weight: 600;
      padding-bottom: 12px;
      border-bottom: 1px solid #f0f0f0;
    }

    &.form-section-horizontal {
      .form-row {
        display: flex;
        gap: 20px;
        align-items: flex-end;
        flex-wrap: wrap;

        .form-group-inline {
          flex: 1;
          min-width: 200px;
          margin-bottom: 0;
        }

        // Align checkboxes with inputs
        .checkbox-group.form-group-inline {
          align-self: flex-end;
          margin-bottom: 0;
          padding-bottom: 0;
        }
      }

      .backup-options {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid #f0f0f0;
      }
    }
  }

  .form-group {
    margin-bottom: 16px;

    label {
      display: block;
      margin-bottom: 6px;
      font-weight: 500;
      color: var(--color-heading);
      font-size: 0.9rem;
    }

    &.form-group-inline {
      margin-bottom: 0;
    }

    .form-control {
      width: 100%;
      padding: 8px 12px;
      border: 1px solid #d0d0d0;
      border-radius: 8px;
      font-size: 0.9rem;
      transition: all 0.2s ease;
      background: white;
      box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.02);

      &:hover {
        border-color: #b0b0b0;
      }

      &:focus {
        outline: none;
        border-color: $primary;
        box-shadow: 0 0 0 3px rgba(0, 114, 206, 0.1), inset 0 1px 2px rgba(0, 0, 0, 0.02);
      }

      &:disabled {
        background-color: #f5f5f5;
        border-color: #e0e0e0;
        cursor: not-allowed;
        opacity: 0.7;
      }

      &::placeholder {
        color: #999;
        opacity: 0.7;
      }
    }

    // Ensure select elements have consistent styling
    select.form-control {
      cursor: pointer;
      background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%23343a40' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3e%3c/svg%3e");
      background-repeat: no-repeat;
      background-position: right 8px center;
      background-size: 16px 12px;
      padding-right: 32px;
    }

    textarea.form-control {
      resize: vertical;
      min-height: 80px;
      font-family: inherit;
      line-height: 1.5;
      border-radius: 8px;
    }

    select[multiple].form-control {
      min-height: 120px;
      padding: 8px;
      border-radius: 8px;
      option {
        padding: 6px 8px;
      }
    }

    input[type="file"].form-control,
    .file-input {
      padding: 8px;
      cursor: pointer;
      border: 1px solid #d0d0d0;
      border-radius: 8px;
      background: white;
      display: block;
      width: 100%;
      min-height: 38px;

      &:hover {
        border-color: #b0b0b0;
      }

      &::file-selector-button {
        padding: 6px 14px;
        margin-right: 12px;
        border: 1px solid #d0d0d0;
        border-radius: 6px;
        background: #f8f9fa;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 0.85rem;
        display: inline-block;
        visibility: visible;
        opacity: 1;

        &:hover {
          background: #e9ecef;
          border-color: #b0b0b0;
        }
      }

      // Ensure the file input text is visible
      &::before {
        content: '';
        display: inline-block;
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
    margin-bottom: 12px;

    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      padding: 8px 0;
      transition: all 0.2s ease;
      margin-bottom: 0;
      min-height: 36px; // Match input height for alignment

      &:hover {
        opacity: 0.8;
      }

      .checkbox-input {
        margin: 0;
        width: 18px;
        height: 18px;
        cursor: pointer;
        accent-color: $primary;
        flex-shrink: 0;
        border: 1px solid #d0d0d0;
        border-radius: 3px;
      }

      .checkbox-text {
        flex: 1;
        font-weight: 400;
        color: var(--color-text);
        font-size: 0.9rem;
        line-height: 1.4;
      }
    }

    &.form-group-inline {
      margin-bottom: 0;
      align-self: flex-end;
      padding-bottom: 0;
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
    gap: 12px;
    margin-top: auto;
    padding: 16px 20px;
    border-top: 1px solid var(--color-border);
    flex-shrink: 0;
    background: white;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
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
    max-height: calc(100vh - 150px);

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
      padding: 0;
    }

    .form-sections-wrapper {
      padding: 16px;
    }

    .form-section {
      margin-bottom: 20px;
      padding: 16px;

      h4 {
        font-size: 1rem;
        margin-bottom: 12px;
        padding-bottom: 10px;
      }

      .form-row {
        flex-direction: column;
        gap: 16px;

        .form-group-inline {
          min-width: 100%;
          margin-bottom: 0;
        }

        .checkbox-group.form-group-inline {
          align-self: flex-start;
        }
      }
    }

    .form-group {
      margin-bottom: 14px;

      label {
        font-size: 0.9rem;
        margin-bottom: 6px;
      }

      .form-control {
        padding: 8px 10px;
      }
    }

    .checkbox-grid {
      grid-template-columns: 1fr;
    }

    .cui-filter-row {
      flex-direction: column;
      gap: 16px;

      .cui-filter-picker,
      .cui-file-picker {
        flex: 1 1 100%;
        max-width: 100%;
      }
    }
  }
}

</style>
