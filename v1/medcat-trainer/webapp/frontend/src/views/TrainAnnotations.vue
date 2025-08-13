<template>
  <div @click="selectRelation(null)" class="container-fluid app-container">
    <div class="app-header">
      <div class="project-name">
        <h4>{{ project === null ? '' : project.name }}</h4>
      </div>

      <div class="meta">
        <h5 class="file-name-heading" v-if="((docs || {}).length || 0) > 0">
          <span class="file-name">{{ (currentDoc || {}).name }}</span>
          <span class="divider">|</span>
          <span class="files-remaining">{{ totalDocs - (project !== null ? project.validated_documents.length : 0) }} Remaining</span>
        </h5>
        <button class="btn btn-default" @click="summaryModal = true">
          <font-awesome-icon icon="list-alt" class="summary-icon"></font-awesome-icon>
        </button>
        <button class="btn btn-default" @click="helpModal = true">
          <font-awesome-icon icon="question-circle" class="help-icon"></font-awesome-icon>
        </button>
        <button class="btn btn-default" @click="resetModal = true">
          <font-awesome-icon icon="undo" class="undo-icon"></font-awesome-icon>
        </button>
      </div>
    </div>

    <div class="app-main">
      <document-summary :projId="(project || {}).id" :docs="docs" :moreDocs="nextDocSetUrl !== null"
                        :validatedDocIds="(project || {}).validated_documents"
                        :preparedDocIds="(project || {}).prepared_documents"
                        :selectedDocId="currentDoc !== null ? currentDoc.id : null" :loadingDoc="loadingMsg !== null"
                        @request:nextDocSet="fetchDocuments()" @request:loadDoc="loadDoc"></document-summary>
      <splitpanes class="default-theme">
        <pane size="70" min-size="20">
          <div class="main-viewport">
            <clinical-text :loading="loadingMsg" :text="currentDoc !== null ? currentDoc.text : null"
                           :current-ent="currentEnt" :ents="ents" :task-name="taskName" :task-values="taskValues"
                           :addAnnos="true" :current-rel-start-ent="(currentRel || {}).start_entity"
                           :current-rel-end-ent="(currentRel || {}).end_entity"
                           @select:concept="selectEntity" @select:addSynonym="addSynonym"
                           @pick:concept="conceptPickerState" @remove:newAnno="removeNewAnno"></clinical-text>
            <div class="task-nav-bar">
              <nav-bar class="nav" :ents="ents" :currentEnt="currentEnt" @select:next="next"
                       @select:back="back"></nav-bar>
              <task-bar class="tasks" :taskLocked="taskLocked" :ents="ents" :altSearch="altSearch"
                        :submitLocked="docToSubmit !== null" :terminateEnabled="(project || {}).terminate_available"
                        :irrelevantEnabled="(project || {}).irrelevant_available"
                        :conceptSelection="conceptSynonymSelection"
                        @select:remove="markRemove" @select:correct="markCorrect"
                        @select:kill="markKill" @select:alternative="toggleAltSearch"
                        @select:irrelevant="markIrrelevant" @submit="submitDoc"></task-bar>
            </div>
          </div>
        </pane>
        <pane size="15" min-size="10">
          <div class="sidebar-container">
            <transition name="slide-left">
              <div>
                <concept-summary v-if="!conceptSynonymSelection && !hasRelations" :selectedEnt="currentEnt"
                                 :altSearch="altSearch"
                                 :project="project" :searchFilterDBIndex="searchFilterDBIndex"
                                 @select:altConcept="markAlternative"
                                 @select:alternative="toggleAltSearch"
                                 @updated:entityComment="markEntity(false)"
                                 class="concept-summary"></concept-summary>
                <v-tabs v-if="!conceptSynonymSelection && hasRelations" v-model="tab">
                  <v-tab :value="'concept'">Concept</v-tab>
                  <v-tab :value="'relation'">Relation</v-tab>
                  <v-tab title="Relations" v-if="hasRelations && docId">
                  </v-tab>
                </v-tabs>
                <v-tabs-window v-if="!conceptSynonymSelection && hasRelations" v-model="tab">
                  <v-tabs-window-item :value="'concept'">
                    <concept-summary :selectedEnt="currentEnt" :altSearch="altSearch"
                                     :project="project" :searchFilterDBIndex="searchFilterDBIndex"
                                     @select:altConcept="markAlternative" @select:alternative="toggleAltSearch"
                                     class="concept-summary"></concept-summary>
                  </v-tabs-window-item>
                  <v-tabs-window-item :value="'relation'">
                    <relation-annotation-task-container :available-relations="project.relations"
                                                        :project-id="project.id"
                                                        :document-id="docId" :selected-entity="currentEnt"
                                                        :curr-relation="currentRel" @selected:relation="selectRelation">
                    </relation-annotation-task-container>
                  </v-tabs-window-item>
                </v-tabs-window>
              </div>
            </transition>
            <transition name="slide-left">
              <meta-annotation-task-container v-if="metaAnnotate" :model-pack-set="!!project.model_pack"
                                              :taskIDs="hasMetaTasks"
                                              :selectedEnt="currentEnt">
              </meta-annotation-task-container>
            </transition>
            <transition name="slide-left">
              <add-annotation v-if="conceptSynonymSelection" :selection="conceptSynonymSelection"
                              :project="project" :documentId="currentDoc.id" :searchFilterDBIndex="searchFilterDBIndex"
                              @request:addAnnotationComplete="addAnnotationComplete"
                              class="add-annotation"></add-annotation>
            </transition>
          </div>
        </pane>
      </splitpanes>
    </div>

    <modal v-if="helpModal" class="help-modal" :closable="true" @modal:close="helpModal = false">
      <template #header>
        <h3>{{ project.name }} Annotation Help</h3>
      </template>
      <template #body>
        <div class="help-modal-body">
          <div class="concept-filter-search">
            <div class="project-filter-title">
              Project Concepts Annotated:
            </div>
            <concept-filter :cuis="project.cuis" :cdb_id="project.concept_db"></concept-filter>
          </div>

          <v-expansion-panels>
            <v-expansion-panel v-if="project.annotation_guideline_link" title="Annotation Guidelines">
              <v-expansion-panel-text>
                Link to guideline <a :href="'' + project.annotation_guideline_link + ''">here</a>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel title="Keyboard Shortcuts">
              <v-expansion-panel-text>
                <table class="table">
                  <thead>
                  <tr>
                    <th>Shortcut Key</th>
                    <th>Key Name</th>
                    <th>Description</th>
                  </tr>
                  </thead>
                  <tbody>
                  <tr>
                    <td>
                      <font-awesome-icon icon="arrow-up"></font-awesome-icon>
                    </td>
                    <td>Up Arrow</td>
                    <td>Previous Document</td>
                  </tr>
                  <tr>
                    <td>
                      <font-awesome-icon icon="arrow-down"></font-awesome-icon>
                    </td>
                    <td>Down Arrow</td>
                    <td>Next Document</td>
                  </tr>
                  <tr>
                    <td>
                      <font-awesome-icon icon="arrow-left"></font-awesome-icon>
                    </td>
                    <td>Left Arrow</td>
                    <td>Previous Concept</td>
                  </tr>
                  <tr>
                    <td>
                      <font-awesome-icon icon="arrow-right"></font-awesome-icon>
                      or space
                    </td>
                    <td>Right Arrow or Space bar</td>
                    <td>Next Concept</td>
                  </tr>
                  <tr>
                    <td>
                      <font-awesome-icon icon="level-down-alt" :transform="{ rotate: 90 }"></font-awesome-icon>
                    </td>
                    <td>Enter Key</td>
                    <td>Submit / Submit Confirm (on submit summary)</td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>1 Key</td>
                    <td>Correct</td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>2 Key</td>
                    <td>Incorrect</td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>3 Key (if set on your project)</td>
                    <td>Terminate</td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>4 Key</td>
                    <td>Alternative</td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>5 Key (if set on your project)</td>
                    <td>Irrelevant</td>
                  </tr>
                  </tbody>
                </table>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel title="Experimental Features">
              <v-expansion-panel-text>
                <button class="btn btn-primary" :disabled="resubmittingAllDocs" @click="submitAll">
                  <span v-if="!resubmittingAllDocs">Re-Submit All Validated Documents</span>
                  <span v-if="resubmittingAllDocs">Submitting...</span>
                </button>
                <transition name="alert"><span v-if="resubmitSuccess" class="alert alert-info">Successfully Re-submitted</span>
                </transition>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>
      </template>
      <template #footer>
        <button class="btn btn-primary" @click="helpModal = false">Close</button>
      </template>
    </modal>

    <modal v-if="errors.modal" @modal:close="errors.modal = false" class="error-modal">
      <template #header>
        <h3 slot="header" class="text-danger">Error: {{ errors.message }}</h3>
      </template>
      <template #body>
        <div class="error-body">
          <p v-if="errors.description.length > 0">{{ errors.description }}</p>
          <p v-if="errors.stacktrace">Full Error:</p>
          <p v-if="errors.stacktrace" class="error-stacktrace">{{ errors.stacktrace }}</p>
        </div>
      </template>
      <template #footer>
        <a href="/">
          <button class="btn btn-primary">MedCATtrainer Home</button>
        </a>
      </template>
    </modal>

    <modal v-if="projectCompleteModal" @modal:close="projectCompleteModal = false">
      <template #header>
        <h3 class="text-success">Project Annotations Complete</h3>
      </template>
      <template #body>
        <p>Exit this window to review annotations or return to the project selection screen</p>
      </template>
      <template #footer>
        <a href="/">
          <button class="btn btn-primary">MedCATtrainer Home</button>
        </a>
      </template>
    </modal>

    <modal v-if="docToSubmit" :closable="true" @modal:close="docToSubmit=null" class="summary-modal">
      <template #header>
        <h3>Submit Document</h3>
      </template>
      <template #body>
        <div slot="body">
          <annotation-summary :annos="ents" :currentDoc="currentDoc"
                              :taskIDs="hasMetaTasks" :searchFilterDBIndex="searchFilterDBIndex"
                              @select:AnnoSummaryConcept="selectEntityFromSummary"></annotation-summary>
        </div>
      </template>
      <template #footer>
        <button class="btn btn-primary" :disabled="submitConfirmedLoading" @click="submitConfirmed()">
          <span v-if="!submitConfirmedLoading">Confirm</span>
          <span v-if="submitConfirmedLoading">
            Submitting Document
            <font-awesome-icon icon="spinner" spin></font-awesome-icon>
          </span>
        </button>
      </template>
    </modal>

    <modal v-if="summaryModal" :closable="true" @modal:close="summaryModal = false" class="summary-modal">
      <template #header>
        <h3>Annotation Summary</h3>
      </template>
      <template #body>
        <annotation-summary :annos="ents" :currentDoc="currentDoc"
                            :taskIDs="(project || {}).tasks || []"
                            @select:AnnoSummaryConcept="selectEntityFromSummary"></annotation-summary>
      </template>
    </modal>

    <modal v-if="resetModal" :closable="true" @modal:close="resetModal = false" class="reset-modal">
      <template #header>
        <h3>Reset Document</h3>
      </template>

      <template #body>
        <div>
          <p class="text-center">Confirm reset of document annotations</p>
          <p class="text-center">This will clear all current annotations in this document</p>
        </div>
      </template>

      <template #footer>
        <button class="btn btn-primary" @click="confirmReset">Confirm</button>
      </template>
    </modal>
  </div>
</template>

<script>
import _ from 'lodash'

import ConceptSummary from '@/components/common/ConceptSummary.vue'
import DocumentSummary from '@/components/common/DocumentSummary.vue'
import Modal from '@/components/common/Modal.vue'
import ClinicalText from '@/components/common/ClinicalText.vue'
import NavBar from '@/components/common/NavBar.vue'
import TaskBar from '@/components/anns/TaskBar.vue'
import AddAnnotation from '@/components/anns/AddAnnotation.vue'
import MetaAnnotationTaskContainer from '@/components/usecases/MetaAnnotationTaskContainer.vue'
import RelationAnnotationTaskContainer from '@/components/usecases/RelationAnnotationTaskContainer.vue'
import AnnotationSummary from '@/components/common/AnnotationSummary.vue'
import ConceptFilter from "@/components/common/ConceptFilter.vue"
import {Splitpanes, Pane} from 'splitpanes'

const TASK_NAME = 'Concept Annotation'
const CONCEPT_CORRECT = 'Correct'
const CONCEPT_REMOVED = 'Deleted'
const CONCEPT_KILLED = 'Killed'
const CONCEPT_ALTERNATIVE = 'Alternative'
const CONCEPT_IRRELEVANT = 'Irrelevant'

const TASK_VALUES = [CONCEPT_CORRECT, CONCEPT_REMOVED, CONCEPT_KILLED, CONCEPT_ALTERNATIVE, CONCEPT_IRRELEVANT]

let LOAD_NUM_DOC_PAGES = 10 // 100 docs per page, 1000 documents

export default {
  name: 'TrainAnnotations',
  components: {
    ConceptFilter,
    ConceptSummary,
    DocumentSummary,
    Modal,
    ClinicalText,
    NavBar,
    TaskBar,
    AddAnnotation,
    MetaAnnotationTaskContainer,
    RelationAnnotationTaskContainer,
    AnnotationSummary,
    Splitpanes,
    Pane,
  },
  props: {
    projectId: {
      required: true
    },
    docId: {
      required: false
    }
  },
  computed: {
    hasRelations() {
      return ((this.project || {}).relations || []).length > 0
    },
    hasMetaTasks() {
      return (this.project || {}).tasks || []
    }
  },
  data() {
    return {
      docs: null,
      docIds: null,
      docIdsToDocs: null,
      totalDocs: 0,
      nextDocSetUrl: null,
      nextEntSetUrl: null,
      taskLocked: false,
      taskName: TASK_NAME,
      taskValues: TASK_VALUES,
      project: null,
      searchFilterDBIndex: null,
      ents: null,
      currentDoc: null,
      currentEnt: null,
      currentRel: null,
      loadingMsg: null,
      resubmittingAllDocs: false,
      resubmitSuccess: false,
      helpModal: false,
      projectCompleteModal: false,
      resetModal: false,
      conceptPickerOpen: true,
      errors: {
        modal: false,
        message: '',
        description: '',
        stacktrace: ''
      },
      summaryModal: false,
      docToSubmit: null,
      submitConfirmedLoading: false,
      altSearch: false,
      conceptSynonymSelection: null,
      metaAnnotate: false,
      tab: null
    }
  },
  created() {
    this.fetchAnnoConf()
  },
  methods: {
    fetchAnnoConf() {
      this.$http.get(`/api/anno-conf/`).then(resp => {
        LOAD_NUM_DOC_PAGES = resp.data['LOAD_NUM_DOC_PAGES'] || LOAD_NUM_DOC_PAGES
        this.fetchData()
      })
    },
    fetchData() {
      this.$http.get(`/api/project-annotate-entities/?id=${this.projectId}`).then(resp => {
        if (resp.data.count === 0) {
          this.errors.modal = true
          this.errors.message = `No project found for project ID: ${this.$route.params.projectId}`
        } else {
          this.project = resp.data.results[0]
          this.fetchCDBSearchIndex()
          const loadedDocs = () => {
            this.docIds = this.docs.map(d => d.id)
            this.docIdsToDocs = Object.assign({}, ...this.docs.map(item => ({[item['id']]: item})))
            const docIdRoute = Number(this.$route.params.docId)
            if (docIdRoute) {
              while (!this.docs.map(d => d.id).includes(docIdRoute)) {
                this.fetchDocuments(0, loadedDocs)
              }
              this.loadDoc(this.docIdsToDocs[docIdRoute])
            } else {
              // find first unvalidated doc.
              const ids = _.difference(this.docIds, this.project.validated_documents)
              if (ids.length > 0) {
                this.loadDoc(this.docIdsToDocs[ids[0]])
              } else {
                // no unvalidated docs and no next doc URL. Go back to first doc
                this.loadDoc(this.docs[0])
              }
            }
          }
          this.fetchDocuments(0, loadedDocs)
        }
      })
    },
    fetchDocuments(numPagesLoaded, finishedLoading) {
      let params = this.nextDocSetUrl === null ? `?dataset=${this.project.dataset}`
          : `?${this.nextDocSetUrl.split('?').slice(-1)[0]}`

      this.$http.get(`/api/documents/${params}`).then(resp => {
        if (resp.data.results.length > 0) {
          this.docs = resp.data.previous === null ? resp.data.results : this.docs.concat(resp.data.results)
          this.totalDocs = resp.data.count
          this.nextDocSetUrl = resp.data.next

          if (this.nextDocSetUrl && numPagesLoaded < LOAD_NUM_DOC_PAGES) {
            this.fetchDocuments(numPagesLoaded + 1, finishedLoading)
          } else {
            if (finishedLoading) {
              finishedLoading()
            }
          }
        }
      }).catch(err => {
        console.error(err)
        // use error modal to show errors?
      })
      return finishedLoading
    },
    fetchCDBSearchIndex() {
      if (this.project.cdb_search_filter.length > 0) {
        this.$http.get(`/api/concept-dbs/${this.project.cdb_search_filter[0]}/`).then(resp => {
          if (resp.data) {
            this.searchFilterDBIndex = `${resp.data.name}_id_${this.project.cdb_search_filter}`
          }
        })
      }
    },
    loadDoc(doc) {
      this.currentDoc = doc
      if (String(this.$route.params.docId) !== String(doc.id)) {
        this.$router.replace({
          name: this.$route.name,
          params: {
            projectId: this.$route.params.projectId,
            docId: doc.id
          }
        })
      }
      this.currentEnt = null
      this.prepareDoc()
    },
    prepareDoc () {
      if (this.project.prepared_documents.includes(this.currentDoc.id)) {
        this.fetchEntities()
      } else {
        this.loadingMsg = "Loading MedCAT model..."
        this.$http.get(`/api/cache-model/${this.project.id}/`).then(_ => {
          this.loadingMsg = "Preparing Document..."
          let payload = {
            project_id: this.project.id,
            document_ids: [this.currentDoc.id]
          }
          this.$http.post('/api/prepare-documents/', payload).then(_ => {
            // assuming a 200 is fine here.
            if (!this.project.prepared_documents.includes(this.currentDoc.id)) {
              this.project.prepared_documents.push(this.currentDoc.id)
            }
            this.fetchEntities()
          }).catch(err => {
            this.errors.modal = true
            if (err.response) {
              this.errors.message = err.response.data.message || 'Internal Server Error.'
              this.errors.description = err.response.data.description || ''
              this.errors.stacktrace = err.response.data.stacktrace
            }
          })
        }).catch(e => {
          this.errors.modal = true
          this.errors.description = e.response?.data?.message || 'Internal server error - cannot load MedCAT model. Contact your MedCAT admin quoting this project ID'
          this.errors.message = 'Failed to load MedCAT Model'
        })
      }
    },
    fetchEntities(selectedEntId) {
      let params = this.nextEntSetUrl === null ? `?project=${this.projectId}&document=${this.currentDoc.id}`
          : `?${this.nextEntSetUrl.split('?').slice(-1)[0]}`
      this.$http.get(`/api/annotated-entities/${params}`).then(resp => {
        let useAssignedVal = !this.project.require_entity_validation ||
            this.project.validated_documents.indexOf(this.currentDoc.id) !== -1

        const ents = resp.data.results.map(e => {
          e.assignedValues = {}
          e.assignedValues[TASK_NAME] = null
          if (useAssignedVal || e.validated) {
            let taskVal = CONCEPT_CORRECT
            if (e.deleted) {
              taskVal = CONCEPT_REMOVED
            } else if (e.killed) {
              taskVal = CONCEPT_KILLED
            } else if (e.alternative) {
              taskVal = CONCEPT_ALTERNATIVE
            } else if (e.irrelevant) {
              taskVal = CONCEPT_IRRELEVANT
            }
            e.assignedValues[TASK_NAME] = taskVal
          }
          return e
        })
        if (resp.data.previous === null) {
          this.ents = ents
        } else {
          this.ents = this.ents.concat(ents)
        }
        this.nextEntSetUrl = resp.data.next
        if (this.nextEntSetUrl) {
          this.fetchEntities(selectedEntId)
        } else {
          this.ents = _.orderBy(this.ents, ['start_ind'], ['asc'])
          this.currentEnt = selectedEntId ? this.ents[this.ents.map(e => e.id).indexOf(selectedEntId)]
              : this.ents[0]
          this.metaAnnotate = this.currentEnt && (this.currentEnt.assignedValues[TASK_NAME] === CONCEPT_ALTERNATIVE ||
              this.currentEnt.assignedValues[TASK_NAME] === CONCEPT_CORRECT)
          this.loadingMsg = null
          if (this.$route.query.annoStart && this.$route.query.annoEnd) {
            const ent = _.find(this.ents, e => {
              return Number(this.$route.query.annoStart) === e.start_ind &
                  Number(this.$route.query.annoEnd) === e.end_ind
            })
            if (ent) {
              this.currentEnt = ent
            }
          }
        }
      })
    },
    selectEntityFromSummary(entIdx) {
      this.docToSubmit = null
      this.summaryModal = false
      this.selectEntity(entIdx)
    },
    selectEntity(entIdx) {
      this.currentEnt = this.ents[entIdx]
      this.conceptSynonymSelection = null
      this.metaAnnotate = this.currentEnt.assignedValues[TASK_NAME] === CONCEPT_ALTERNATIVE ||
          this.currentEnt.assignedValues[TASK_NAME] === CONCEPT_CORRECT
    },
    selectRelation(rel) {
      this.currentRel = rel
    },
    setStatus(status) {
      this.currentEnt.validated = 1
      // reset statuses in case this is a re-annotation.
      this.currentEnt.correct = 0
      this.currentEnt.killed = 0
      this.currentEnt.alternative = 0
      this.currentEnt.deleted = 0
      this.currentEnt.irrelevant = 0
      this.currentEnt[status] = 1
    },
    markCorrect() {
      if (this.currentEnt) {
        this.currentEnt.assignedValues[TASK_NAME] = CONCEPT_CORRECT
        this.setStatus('correct')
        this.markEntity(this.project.tasks.length === 0)
        this.metaAnnotate = this.project.tasks.length > 0
      }
    },
    markEntity(moveToNext) {
      if (this.currentEnt) {
        this.taskLocked = true
        this.$http.put(`/api/annotated-entities/${this.currentEnt.id}/`, this.currentEnt).then(_ => {
          if (moveToNext) {
            if (this.ents.slice(-1)[0].id !== this.currentEnt.id) {
              this.next()
            } else {
              this.currentEnt = null
            }
          }
          this.taskLocked = false
        })
      }
    },
    markRemove(kill) {
      if (this.currentEnt) {
        this.currentEnt.assignedValues[TASK_NAME] = kill ? CONCEPT_KILLED : CONCEPT_REMOVED
        if (kill) {
          this.setStatus('killed')
        } else {
          this.setStatus('deleted')
        }
        this.markEntity(true)
        this.metaAnnotate = false
      }
    },
    toggleAltSearch(choice) {
      this.altSearch = choice
    },
    markKill() {
      this.markRemove(true)
    },
    markAlternative(item) {
      this.altSearch = false
      this.taskLocked = true
      this.$http.post(`/api/get-create-entity/`, {label: item.cui}).then(resp => {
        this.currentEnt.assignedValues[TASK_NAME] = CONCEPT_ALTERNATIVE
        this.currentEnt.entity = resp.data.entity_id
        this.setStatus('alternative')
        this.markEntity(this.project.tasks.length === 0)
        this.metaAnnotate = this.project.tasks.length > 0
        let i = this.ents.indexOf(this.currentEnt)
        this.currentEnt = JSON.parse(JSON.stringify(this.currentEnt))
        this.ents[i] = this.currentEnt
      })
      this.currentEnt.cui = item.cui
    },
    markIrrelevant() {
      this.currentEnt.assignedValues[TASK_NAME] = CONCEPT_IRRELEVANT
      this.setStatus('irrelevant')
      this.markEntity(true)
      this.metaAnnotate = false
    },
    addAnnotationComplete(addedAnnotationId) {
      this.conceptSynonymSelection = null
      if (addedAnnotationId) {
        this.$http.get(`/api/annotated-entities/${addedAnnotationId}/`).then(resp => {
          let newEnt = resp.data
          newEnt.assignedValues = {}
          newEnt.assignedValues[TASK_NAME] = CONCEPT_CORRECT
          this.ents = null
          this.currentEnt = null
          this.fetchEntities(newEnt.id)
        })
      }
    },
    removeNewAnno(i) {
      let entToRemove = this.ents[i]
      this.$http.delete(`/api/annotated-entities/${entToRemove.id}/`).then(_ => {
        if (i === this.ents.length - 1) {
          this.back()
        } else {
          this.next()
        }
        this.ents.splice(i, 1)
      })
    },
    addSynonym(selection) {
      this.conceptSynonymSelection = null
      let that = this
      window.setTimeout(function () {
        that.conceptSynonymSelection = selection
        that.metaAnnotate = false
      }, 50)
    },
    conceptPickerState(val) {
      this.conceptPickerOpen = val
    },
    next() {
      this.selectEntity(this.ents.indexOf(this.currentEnt) + 1)
    },
    back() {
      this.selectEntity(this.ents.indexOf(this.currentEnt) - 1)
    },
    submitDoc(docId) {
      if (this.docToSubmit === null) {
        const annoUpdates = []
        if (!this.project.require_entity_validation) {
          this.ents = this.ents.map(ent => {
            ent.validated = 1
            if (!(ent.killed || ent.alternative || ent.deleted || ent.irrelevant)) {
              ent.correct = 1
            }
            annoUpdates.push(this.$http.put(`/api/annotated-entities/${ent.id}/`, ent))
            return ent
          })
        }
        let that = this
        if (annoUpdates.length > 1) {
          Promise.all(annoUpdates).then(_ => {
            that.confirmSubmitListenerAdd()
            that.docToSubmit = docId
          })
        } else {
          this.confirmSubmitListenerAdd()
          this.docToSubmit = docId
        }
      }
    },
    submitConfirmed() {
      this.confirmSubmitListenerRemove()
      this.submitConfirmedLoading = true
      this.$http.get(`/api/project-annotate-entities/?id=${this.projectId}`).then(resp => {
        // refresh project validated documents as multiple users may be submitting. Mitigates but
        // does not solve a potential inconsistent validated_documents state seen.
        let proj = resp.data.results[0]
        if (proj.validated_documents.indexOf(this.currentDoc.id) === -1) {
          proj.validated_documents = this.project.validated_documents.concat(this.currentDoc.id)
        }
        this.project = proj
        this.fetchCDBSearchIndex()
        this.$http.put(`/api/project-annotate-entities/${this.projectId}/`, this.project).then(() => {
          let payload = {
            project_id: this.project.id,
            document_id: this.currentDoc.id
          }
          this.$http.post(`/api/submit-document/`, payload).then(() => {
            this.docToSubmit = null
            this.submitConfirmedLoading = false
            if (this.currentDoc.id !== this.docIds.slice(-1)[0].id ||
                this.project.validated_documents.length !== this.docs.length) {
              const newDocId = this.docIds[this.docIds.indexOf(this.currentDoc.id) + 1]
              if (!newDocId) {
                this.projectCompleteModal = true
              } else {
                this.loadDoc(this.docIdsToDocs[newDocId])
              }
            }
          }, (err) => {
            this.submitConfirmedLoading = false
            this.docToSubmit = false
            this.errors.modal = true
            this.errors.message = err.response.data
          })
        })
      })
    },
    submitAll() {
      let subPromises = []
      for (const vDoc of this.project.validated_documents) {
        const payload = {
          project_id: this.project.id,
          document_id: vDoc
        }
        subPromises.push(this.$http.post(`/api/submit-document/`, payload))
        this.resubmittingAllDocs = true
        this.loadingMsg = "Submitting document annotations..."
        Promise.all(subPromises).then(_ => {
          this.resubmitSuccess = true
          this.loadingMsg = null
          this.resubmittingAllDocs = false
          const that = this
          setTimeout(function () {
            that.resubmitSuccess = false
          }, 10000)
        }).catch(() => {
          this.resubmittingAllDocs = true
          this.loadingMsg = null
          this.errors.modal = true
          this.errors.message = 'Failure re-submitting all validated documents: Refresh Project'
        })
      }
    },
    keydown(e) {
      if (e.keyCode === 13 && this.docToSubmit && !this.submitConfirmedLoading) {
        this.submitConfirmed()
      } else if (e.keyCode === 27 && this.docToSubmit) {
        this.docToSubmit = null
      }
    },
    confirmSubmitListenerRemove() {
      window.removeEventListener('keydown', this.keydown)
    },
    confirmSubmitListenerAdd() {
      window.addEventListener('keydown', this.keydown)
    },
    confirmReset() {
      this.loadingMsg = "Resetting document annotations..."
      const payload = {
        project_id: this.project.id,
        document_ids: [this.currentDoc.id],
        force: true
      }
      this.$http.post('/api/prepare-documents/', payload).then(_ => {
        this.fetchEntities()
        this.resetModal = false
        this.loadingMsg = null
      }).catch(err => {
        this.resetModal = false
        this.errors.modal = true
        if (err.response) {
          this.errors.message = err.response.data.message || 'Internal Server Error.'
          this.errors.description = err.response.data.description || ''
          this.errors.stacktrace = err.response.data.stacktrace
        }
      })
    }
  },
  beforeDestroy() {
    this.confirmSubmitListenerRemove()
  }
}
</script>

<style scoped lang="scss">

$app-header-height: 60px;

.app-header {
  display: flex;
  flex-direction: row;
  flex: 0 0 $app-header-height;
  line-height: $app-header-height;
  font-size: 20px;
  padding: 0 15px;
}

.Pane {
  position: static !important;
}

.project-name {
  flex: 1 1 auto;
  color: $text-highlight;
}

.help-icon, .summary-icon, .undo-icon {
  color: $text;
  font-size: 22px;
}

.summary {
  padding-left: 20px
}

.app-header h4 {
  display: inline-block;
}

.help-heading {
  border-bottom: 1px solid transparent;

  &:hover {
    border-bottom: 1px solid $color-1;
  }
}

.concept-filter-search {
  padding: 5px 0;
}

.project-filter-title {
  margin-bottom: 10px;
}

.meta {
  flex: 1 1 auto;
  text-align: right;
}

.file-name-heading {
  display: inline-block;
  padding-left: 20px;
}

.file-name {
  display: inline-block;
  position: relative;
  top: 5px;
  font-size: 22px;
  max-width: 500px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.files-remaining {
  font-size: 22px;
}

.app-container {
  display: flex;
  height: calc(100% - #{$app-header-height});
  flex-direction: column;
  padding: 5px;
}

.app-main {
  display: flex;
  flex: 1 1 auto;
  overflow: hidden;
  height: 100%;
}

.viewport-container {
  height: calc(100% - 56px);
}

.main-viewport {
  height: 100%;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
}

.nav {
  width: 95px;
  display: inline-block
}

.tasks {
  width: calc(100% - 95px);
  display: inline-block;
}

.sidebar-container {
  background-color: var(--bs-body-bg);
  height: 100%;
  display: flex;
  justify-content: space-between;
  flex-direction: column;
  padding: 5px;

  .add-annotation {
    width: 100%;
    flex: 1 1 auto;
  }
}

.task-nav-bar {
  background-color: var(--bs-body-bg);
  padding: 5px 5px 0 5px;
}

.slide-left-enter-active {
  transition: all .5s ease;
}

.slide-left-enter, .slide-left-leave-to {
  position: relative;
  transform: translateX(50px);
  transition: all .2s ease;
  opacity: 0;
}

.divider {
  opacity: 0.5;
  padding: 0 5px;
}

.summary-title {
  padding-bottom: 10px;
  font-size: 17px;
}

.error-stacktrace {
  white-space: pre-wrap;
}

</style>
