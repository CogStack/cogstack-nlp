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
      <div v-if="activeTab === 'projects'">
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
                  class="btn btn-sm btn-action btn-clone"
                  @click="cloneProject(item)"
                  :title="'Clone ' + item.name">
                  <font-awesome-icon icon="copy"></font-awesome-icon>
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
            <div class="form-sections-wrapper">
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
                  <label>Local Model Pack</label>
                  <select v-model="formData.model_pack" class="form-control" :disabled="useBackupOption || formData.use_model_service">
                    <option :value="null">None</option>
                    <option v-for="mp in modelPacks" :key="mp.id" :value="mp.id">{{ mp.name }}</option>
                  </select>
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
                  <label>Remote Model Service URL</label>
                  <input v-model="formData.model_service_url" type="url" class="form-control" placeholder="http://medcat-service:8000" />
                  <small class="form-text text-muted">URL of the remote MedCAT service API (e.g., http://medcat-service:8000). Note: interim model training is not supported for remote model service projects.</small>
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
      <div v-if="activeTab === 'modelpacks'" class="admin-section">
        <div v-if="!showModelPackForm && !editingModelPack" class="list-section">
          <div class="section-header">
            <h3>Model Packs <span class="item-count">({{ modelPacks.length }})</span></h3>
          </div>
          <div v-if="modelPacks.length > 0" class="table-container">
            <v-data-table
              :items="modelPacks"
              :headers="modelPackHeaders"
              :hover="true"
              @click:row="selectModelPack"
              hide-default-footer
              :items-per-page="-1"
              class="admin-table"
              dense>
              <template #item.concept_db="{ item }">
                <span>{{ getConceptDbName(item.concept_db) }}</span>
              </template>
              <template #item.vocab="{ item }">
                <span>{{ getVocabName(item.vocab) }}</span>
              </template>
              <template #item.actions="{ item }">
                <div class="action-buttons" @click.stop>
                  <button class="btn btn-sm btn-action btn-edit" @click="editModelPack(item)" title="Edit">
                    <font-awesome-icon icon="edit"></font-awesome-icon>
                  </button>
                  <button class="btn btn-sm btn-action btn-delete" @click="confirmDeleteModelPack(item)" title="Delete">
                    <font-awesome-icon icon="trash"></font-awesome-icon>
                  </button>
                </div>
              </template>
            </v-data-table>
          </div>
          <div v-else class="empty-state">
            <h4>No Model Packs</h4>
            <p>Add a model pack to get started.</p>
          </div>
        </div>

        <!-- Model Pack Form -->
        <div v-else class="form-section">
          <div class="form-header">
            <button class="btn btn-back" @click="closeModelPackForm">
              <font-awesome-icon icon="arrow-left"></font-awesome-icon>
              <span>Back</span>
            </button>
            <h3>{{ editingModelPack ? 'Edit Model Pack' : 'Add Model Pack' }}</h3>
          </div>
          <div class="form-content">
            <form @submit.prevent="saveModelPack" class="admin-form">
              <div class="form-sections-wrapper">
                <div class="form-section form-section-horizontal">
                  <div class="form-group">
                    <label>Name *</label>
                    <input v-model="modelPackForm.name" type="text" class="form-control" required />
                  </div>
                  <div class="form-group">
                    <label>Model Pack File *</label>
                    <input type="file" @change="handleModelPackFileChange" accept=".zip" class="form-control" :required="!editingModelPack" />
                    <small class="form-text text-muted">Upload a .zip file containing the model pack</small>
                  </div>
                </div>
                <div class="form-section form-section-horizontal">
                  <div class="form-group">
                    <label>Concept DB</label>
                    <select v-model="modelPackForm.concept_db" class="form-control">
                      <option :value="null">None</option>
                      <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label>Vocabulary</label>
                    <select v-model="modelPackForm.vocab" class="form-control">
                      <option :value="null">None</option>
                      <option v-for="vocab in vocabs" :key="vocab.id" :value="vocab.id">{{ vocab.name }}</option>
                    </select>
                  </div>
                </div>
              </div>
              <div class="form-actions">
                <button type="button" class="btn btn-secondary" @click="closeModelPackForm">Cancel</button>
                <button type="submit" class="btn btn-primary" :disabled="saving">
                  <font-awesome-icon v-if="saving" icon="spinner" spin></font-awesome-icon>
                  <span>{{ saving ? 'Saving...' : 'Save' }}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <!-- End Model Packs Tab -->

      <!-- Datasets Tab -->
      <div v-if="activeTab === 'datasets'" class="admin-section">
        <div v-if="!showDatasetForm && !editingDataset" class="list-section">
          <div class="section-header">
            <h3>Datasets <span class="item-count">({{ datasets.length }})</span></h3>
          </div>
          <div v-if="datasets.length > 0" class="table-container">
            <v-data-table
              :items="datasets"
              :headers="datasetHeaders"
              :hover="true"
              @click:row="selectDataset"
              hide-default-footer
              :items-per-page="-1"
              class="admin-table"
              dense>
              <template #item.actions="{ item }">
                <div class="action-buttons" @click.stop>
                  <button class="btn btn-sm btn-action btn-edit" @click="editDataset(item)" title="Edit">
                    <font-awesome-icon icon="edit"></font-awesome-icon>
                  </button>
                  <button class="btn btn-sm btn-action btn-delete" @click="confirmDeleteDataset(item)" title="Delete">
                    <font-awesome-icon icon="trash"></font-awesome-icon>
                  </button>
                </div>
              </template>
            </v-data-table>
          </div>
          <div v-else class="empty-state">
            <h4>No Datasets</h4>
            <p>Add a dataset to get started.</p>
          </div>
        </div>

        <!-- Dataset Form -->
        <div v-else class="form-section">
          <div class="form-header">
            <button class="btn btn-back" @click="closeDatasetForm">
              <font-awesome-icon icon="arrow-left"></font-awesome-icon>
              <span>Back</span>
            </button>
            <h3>{{ editingDataset ? 'Edit Dataset' : 'Add Dataset' }}</h3>
          </div>
          <div class="form-content">
            <form @submit.prevent="saveDataset" class="admin-form">
              <div class="form-sections-wrapper">
                <div class="form-section form-section-horizontal">
                  <div class="form-group">
                    <label>Name *</label>
                    <input v-model="datasetForm.name" type="text" class="form-control" required />
                  </div>
                  <div class="form-group">
                    <label>Description</label>
                    <textarea v-model="datasetForm.description" class="form-control" rows="2"></textarea>
                  </div>
                </div>
                <div class="form-section">
                  <div class="form-group">
                    <label>Original File *</label>
                    <input type="file" @change="handleDatasetFileChange" accept=".csv,.xlsx" class="form-control" :required="!editingDataset" />
                    <small class="form-text text-muted">Upload a .csv or .xlsx file. Must contain 'name' and 'text' columns.</small>
                  </div>
                </div>
              </div>
              <div class="form-actions">
                <button type="button" class="btn btn-secondary" @click="closeDatasetForm">Cancel</button>
                <button type="submit" class="btn btn-primary" :disabled="saving">
                  <font-awesome-icon v-if="saving" icon="spinner" spin></font-awesome-icon>
                  <span>{{ saving ? 'Saving...' : 'Save' }}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <!-- End Datasets Tab -->

      <!-- Users Tab -->
      <div v-if="activeTab === 'users'" class="admin-section">
        <div v-if="!showUserForm && !editingUser" class="list-section">
          <div class="section-header">
            <h3>Users <span class="item-count">({{ users.length }})</span></h3>
          </div>
          <div v-if="users.length > 0" class="table-container">
            <v-data-table
              :items="users"
              :headers="userHeaders"
              :hover="true"
              @click:row="selectUser"
              hide-default-footer
              :items-per-page="-1"
              class="admin-table"
              dense>
              <template #item.is_staff="{ item }">
                <span class="badge" :class="item.is_staff ? 'badge-success' : 'badge-secondary'">
                  {{ item.is_staff ? 'Staff' : 'User' }}
                </span>
              </template>
              <template #item.is_superuser="{ item }">
                <span class="badge" :class="item.is_superuser ? 'badge-danger' : 'badge-secondary'">
                  {{ item.is_superuser ? 'Admin' : 'Regular' }}
                </span>
              </template>
              <template #item.actions="{ item }">
                <div class="action-buttons" @click.stop>
                  <button class="btn btn-sm btn-action btn-edit" @click="editUser(item)" title="Edit">
                    <font-awesome-icon icon="edit"></font-awesome-icon>
                  </button>
                </div>
              </template>
            </v-data-table>
          </div>
          <div v-else class="empty-state">
            <h4>No Users</h4>
            <p>Add a user to get started.</p>
          </div>
        </div>

        <!-- User Form -->
        <div v-else class="form-section">
          <div class="form-header">
            <button class="btn btn-back" @click="closeUserForm">
              <font-awesome-icon icon="arrow-left"></font-awesome-icon>
              <span>Back</span>
            </button>
            <h3>{{ editingUser ? 'Edit User' : 'Add User' }}</h3>
          </div>
          <div class="form-content">
            <form @submit.prevent="saveUser" class="admin-form">
              <div class="form-sections-wrapper">
                <div class="form-section form-section-horizontal">
                  <div class="form-group">
                    <label>Username *</label>
                    <input v-model="userForm.username" type="text" class="form-control" required />
                  </div>
                  <div class="form-group">
                    <label>Email</label>
                    <input v-model="userForm.email" type="email" class="form-control" />
                  </div>
                </div>
                <div v-if="!editingUser" class="form-section">
                  <div class="form-group">
                    <label>Password</label>
                    <input v-model="userForm.password" type="password" class="form-control" />
                    <small class="form-text text-muted">Note: Password cannot be set via API. Users should set their password through password reset or Django admin.</small>
                  </div>
                </div>
                <div class="form-section">
                  <div class="checkbox-grid">
                    <div class="form-group checkbox-group">
                      <label class="checkbox-label">
                        <input v-model="userForm.is_staff" type="checkbox" class="checkbox-input" />
                        <span class="checkbox-text">Staff</span>
                      </label>
                    </div>
                    <div class="form-group checkbox-group">
                      <label class="checkbox-label">
                        <input v-model="userForm.is_superuser" type="checkbox" class="checkbox-input" />
                        <span class="checkbox-text">Superuser (Admin)</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>
              <div class="form-actions">
                <button type="button" class="btn btn-secondary" @click="closeUserForm">Cancel</button>
                <button type="submit" class="btn btn-primary" :disabled="saving">
                  <font-awesome-icon v-if="saving" icon="spinner" spin></font-awesome-icon>
                  <span>{{ saving ? 'Saving...' : 'Save' }}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
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

export default {
  name: 'ProjectAdmin',
  components: {
    Modal,
    ConceptPicker
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
      modelPackForm: {
        name: '',
        model_pack: null,
        concept_db: null,
        vocab: null
      },
      // Dataset management
      showDatasetForm: false,
      editingDataset: null,
      datasetToDelete: null,
      datasetForm: {
        name: '',
        description: '',
        original_file: null
      },
      // User management
      showUserForm: false,
      editingUser: null,
      userForm: {
        username: '',
        email: '',
        password: '',
        is_staff: false,
        is_superuser: false
      },
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
      tableHeaders: [
        { title: 'Name', value: 'name' },
        { title: 'Description', value: 'description' },
        { title: 'Status', value: 'status' },
        { title: 'Dataset', value: 'dataset' },
        { title: 'Actions', value: 'actions', sortable: false }
      ],
      modelPackHeaders: [
        { title: 'Name', value: 'name' },
        { title: 'Concept DB', value: 'concept_db' },
        { title: 'Vocabulary', value: 'vocab' },
        { title: 'Actions', value: 'actions', sortable: false }
      ],
      datasetHeaders: [
        { title: 'Name', value: 'name' },
        { title: 'Description', value: 'description' },
        { title: 'Actions', value: 'actions', sortable: false }
      ],
      userHeaders: [
        { title: 'Username', value: 'username' },
        { title: 'Email', value: 'email' },
        { title: 'Staff', value: 'is_staff' },
        { title: 'Admin', value: 'is_superuser' },
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
    async saveProject() {
      this.saving = true
      try {
        const formDataToSend = new FormData()

        // Sync CUIs from pills before saving
        this.syncCuiTextFromPills()

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
            // Handle arrays - send empty array as empty (don't append anything for empty arrays)
            if (Array.isArray(this.formData[key]) && this.formData[key].length > 0) {
              this.formData[key].forEach(val => {
                if (val !== null && val !== undefined) {
                  formDataToSend.append(key, val)
                }
              })
            }
            // For empty arrays, don't send anything (backend will handle as empty)
          } else if (this.formData[key] !== null && this.formData[key] !== undefined) {
            // Convert null-like values to empty strings for optional fields
            const value = this.formData[key]
            // For boolean false, send as string 'false'
            if (typeof value === 'boolean') {
              formDataToSend.append(key, value.toString())
            } else {
              formDataToSend.append(key, value)
            }
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
    getConceptDbName(conceptDbId) {
      if (!conceptDbId) return 'N/A'
      const cdb = this.conceptDbs.find(c => c.id === (typeof conceptDbId === 'object' ? conceptDbId.id : conceptDbId))
      return cdb ? cdb.name : 'N/A'
    },
    getVocabName(vocabId) {
      if (!vocabId) return 'N/A'
      const vocab = this.vocabs.find(v => v.id === (typeof vocabId === 'object' ? vocabId.id : vocabId))
      return vocab ? vocab.name : 'N/A'
    },
    // Model Pack methods
    selectModelPack(event, { item }) {
      this.editModelPack(item)
    },
    editModelPack(modelPack) {
      this.editingModelPack = modelPack
      this.modelPackForm = {
        name: modelPack.name || '',
        model_pack: null,
        concept_db: modelPack.concept_db || null,
        vocab: modelPack.vocab || null
      }
      this.showModelPackForm = true
    },
    closeModelPackForm() {
      this.showModelPackForm = false
      this.editingModelPack = null
      this.modelPackForm = {
        name: '',
        model_pack: null,
        concept_db: null,
        vocab: null
      }
    },
    handleModelPackFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.modelPackForm.model_pack = file
      }
    },
    async saveModelPack() {
      this.saving = true
      try {
        const formData = new FormData()
        formData.append('name', this.modelPackForm.name)
        if (this.modelPackForm.model_pack) {
          formData.append('model_pack', this.modelPackForm.model_pack)
        }
        if (this.modelPackForm.concept_db) {
          formData.append('concept_db', this.modelPackForm.concept_db)
        }
        if (this.modelPackForm.vocab) {
          formData.append('vocab', this.modelPackForm.vocab)
        }

        if (this.editingModelPack) {
          await this.$http.put(
            `/api/modelpacks/${this.editingModelPack.id}/`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        } else {
          await this.$http.post(
            '/api/modelpacks/',
            formData,
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
      this.datasetForm = {
        name: dataset.name || '',
        description: dataset.description || '',
        original_file: null
      }
      this.showDatasetForm = true
    },
    closeDatasetForm() {
      this.showDatasetForm = false
      this.editingDataset = null
      this.datasetForm = {
        name: '',
        description: '',
        original_file: null
      }
    },
    handleDatasetFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.datasetForm.original_file = file
      }
    },
    async saveDataset() {
      this.saving = true
      try {
        const formData = new FormData()
        formData.append('name', this.datasetForm.name)
        formData.append('description', this.datasetForm.description || '')
        if (this.datasetForm.original_file) {
          formData.append('original_file', this.datasetForm.original_file)
        }

        if (this.editingDataset) {
          await this.$http.put(
            `/api/datasets/${this.editingDataset.id}/`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )
        } else {
          await this.$http.post(
            '/api/datasets/',
            formData,
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
      this.userForm = {
        username: user.username || '',
        email: user.email || '',
        password: '',
        is_staff: user.is_staff || false,
        is_superuser: user.is_superuser || false
      }
      this.showUserForm = true
    },
    closeUserForm() {
      this.showUserForm = false
      this.editingUser = null
      this.userForm = {
        username: '',
        email: '',
        password: '',
        is_staff: false,
        is_superuser: false
      }
    },
    async saveUser() {
      this.saving = true
      try {
        const data = {
          username: this.userForm.username,
          email: this.userForm.email || '',
          is_staff: this.userForm.is_staff,
          is_superuser: this.userForm.is_superuser
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
    'formData.model_pack'() {
      // Clear pills when model pack changes to avoid confusion
      // User can re-select concepts with the new model pack
      if (!this.editingProject) {
        this.selectedCuiFilterConcepts = []
        this.formData.cuis = ''
      }
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
  padding-bottom: 20px;
  border-bottom: 2px solid var(--color-border);

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

    &.btn-clone {
      color: $success;
      border-color: $success;

      &:hover {
        background-color: $success;
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
  border-radius: 12px;
  padding: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 180px);
  max-height: calc(100vh - 180px);

  .form-header {
    padding: 12px 20px;
    border-bottom: 1px solid var(--color-border);
    background: linear-gradient(135deg, $primary 0%, darken($primary, 10%) 100%);
    color: white;
    display: flex;
    align-items: center;
    gap: 12px;
    border-radius: 12px 12px 0 0;

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
    overflow: hidden;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .project-form {
    padding: 0;
    max-width: 1400px;
    margin: 0 auto;
    flex: 1;
    display: flex;
    flex-direction: column;
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

    .file-input {
      padding: 8px;
      cursor: pointer;
      border: 1px solid #d0d0d0;
      border-radius: 8px;
      background: white;

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

        &:hover {
          background: #e9ecef;
          border-color: #b0b0b0;
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

  // Concept Filtering Styles (from Demo.vue)
  .cui-filter-controls {
    margin: 0 0 16px 0;
    padding: 12px;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .cui-filter-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
    font-size: 0.9rem;
    cursor: pointer;
    font-weight: 400;
    color: var(--color-text);

    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      cursor: pointer;
      accent-color: $primary;
      border: 1px solid #d0d0d0;
    }
  }

  .cui-filter-paste-toggle {
    padding: 4px 8px;
    font-size: 0.85rem;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    background: white;
    transition: all 0.2s ease;

    &:hover {
      background: #f0f0f0;
      border-color: #b0b0b0;
    }
  }

  .cui-filter-row {
    display: flex;
    gap: 20px;
    align-items: flex-start;
    margin: 0 0 16px 0;
  }

  .cui-filter-picker {
    flex: 0 0 50%;
    max-width: 50%;
    padding: 12px;
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
  }

  .cui-file-picker {
    flex: 0 0 calc(50% - 20px);
    max-width: calc(50% - 20px);
    padding: 12px;
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;

    label {
      display: block;
      margin-bottom: 6px;
      font-weight: 500;
      color: var(--color-heading);
      font-size: 0.9rem;
    }

    .form-control {
      border: 1px solid #d0d0d0;
    }
  }

  .cui-pill-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 6px 0 10px 0;
  }

  .cui-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    border: 1px solid rgba(0, 0, 0, 0.15);
    background: rgba(13, 110, 253, 0.08);
    color: #0b5ed7;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 0.75rem;
    line-height: 1;
  }

  .cui-pill-text {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  }

  .cui-pill-remove {
    border: none;
    background: transparent;
    color: inherit;
    padding: 0;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    opacity: 0.7;
    transition: opacity 0.2s ease;

    &:hover {
      opacity: 1;
    }
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid var(--color-border);
    flex-shrink: 0;

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

// Tab Navigation Styles
.admin-tabs {
  display: flex;
  gap: 8px;
  margin: 20px 0;
  border-bottom: 2px solid var(--color-border);
  padding-bottom: 0;
}

.tab-button {
  padding: 12px 24px;
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
  margin-bottom: -2px;

  &:hover {
    color: var(--color-primary);
    background: rgba(0, 0, 0, 0.02);
  }

  &.active {
    color: var(--color-primary);
    border-bottom-color: var(--color-primary);
    font-weight: 600;
  }

  svg {
    font-size: 1rem;
  }
}

// Admin Section Styles (for Model Packs, Datasets, Users)
.admin-section {
  .list-section {
    .section-header {
      margin-bottom: 20px;

      h3 {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--color-heading);
        margin: 0;
      }

      .item-count {
        font-weight: 400;
        color: var(--color-text-secondary);
        font-size: 1rem;
      }
    }

    .table-container {
      background: white;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      overflow: hidden;
    }
  }

  .admin-table {
    .action-buttons {
      display: flex;
      gap: 6px;
      justify-content: flex-end;
    }
  }

  .form-section {
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    height: calc(100vh - 250px);
    min-height: 600px;
  }

  .admin-form {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;

    .form-sections-wrapper {
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
      min-height: 0;
      padding: 20px;
    }

    .form-actions {
      margin-top: auto;
      flex-shrink: 0;
      padding: 20px;
      border-top: 1px solid var(--color-border);
      display: flex;
      gap: 12px;
      justify-content: flex-end;
      background: var(--color-background-light);
    }
  }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);

  h4 {
    font-size: 1.25rem;
    color: var(--color-heading);
    margin-bottom: 8px;
  }

  p {
    color: var(--color-text-secondary);
    margin-bottom: 20px;
  }
}
</style>
