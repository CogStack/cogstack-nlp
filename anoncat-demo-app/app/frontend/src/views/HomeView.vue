<template>
  <v-container fluid class="viewport-container">
    <v-row no-gutters class="viewport">
      <v-col class="col" cols="12" lg="4">
        <div class="col-container">
          <div class="border">
            <v-textarea class="texts-height" :rows="isDesktop ? 32 : 10" label="Input Text" variant="solo-filled" v-model="inputText" clearable>
            </v-textarea>
          </div>
        </div>
      </v-col>
      <v-col class="col" cols="12" lg="4">
        <div class="col-container centered">
          <img src="../assets/logo.png" class="image-size center-logo" />
          <div class="button-group">
            <v-btn @click="deidentify" color="light-blue">Deidentify</v-btn>
            <v-checkbox class="redact-check" label="Redact" v-model="redact"></v-checkbox>
            <v-btn @click="fillExampleText" color="purple">Use Example</v-btn>
          </div>
        </div>
      </v-col>
      <v-col class="col" cols="12" lg="4">
        <div class="col-container">
          <div class="border">
            <div class="output-text">
              <span v-if="outputText === ''">Deidentification output</span>
              {{outputText}}
            </div>
          </div>
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import {EXAMPLE_TEXT} from "@/consts/texts";
import axios from "axios";

export default {
  name: 'HomeView',
  data () {
    return {
      inputText: '',
      redact: false,
      outputText: '',
      isDesktop: window.innerWidth >= 1280
    }
  },
  mounted() {
    window.addEventListener('resize', this.handleResize)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.handleResize)
  },
  methods: {
    deidentify () {
      const payload = {text: this.inputText, redact: this.redact}
      const headers = {}
      axios.post('/api/deidentify/', payload).then(resp => {
        this.outputText = resp.data.output_text
      })
    },
    fillExampleText () {
      this.inputText = EXAMPLE_TEXT
    },
    handleResize() {
      this.isDesktop = window.innerWidth >= 1280
    }
  }
}
</script>

<style scoped>
.viewport-container {
  padding: 0 3px;
  overflow-y: auto;
  margin-top: 0;
}

.viewport {
  height: calc(100vh - 95px);
  padding-top: 10px;
}

.col {
  height: 100%;
}

.image-size {
  width: 200px;
  height: auto;
}

.col-container {
  border: 10px solid var(--vt-c-text-dark-2);
  height: 100%;
}

.texts-height {
  height: 100%;
}

.texts-height :deep(.v-input__control),
.texts-height :deep(.v-field),
.texts-height :deep(.v-field__field),
.texts-height :deep(textarea) {
  height: 100%;
}

.centered {
  text-align: center;
  padding-top: 50px;

  div {
    padding: 20px;
  }
}

.border {
  box-shadow: 0 1px 6px rgba(0, 0, 0, .2);
  height: 100%;
}

.output-text {
  overflow-y: auto;
  white-space: pre-wrap;
  padding: 5px;
  font-size: 11pt;
  height: 100%;
}

.redact-check {
  margin-left: 30px;
}

/* Responsive adjustments for mobile/tablet (stacked layout) */
@media (max-width: 767px) {
  .viewport-container {
    padding-top: 10px;
    height: calc(100vh - 120px);
    overflow-y: auto;
  }

  .viewport {
    height: auto;
    min-height: 100%;
    padding-top: 0;
  }

  .col {
    height: auto;
    min-height: auto;
  }

  .col-container {
    height: auto;
    min-height: auto;
    border: 5px solid var(--vt-c-text-dark-2);
    margin-bottom: 5px;
  }

  .border {
    height: auto;
  }

  .texts-height {
    height: auto;
    min-height: auto;
  }

  .texts-height :deep(.v-input__control),
  .texts-height :deep(.v-field),
  .texts-height :deep(.v-field__field),
  .texts-height :deep(textarea) {
    height: auto;
  }

  .output-text {
    min-height: 200px;
    height: auto;
  }

  .centered {
    padding: 8px;
    min-height: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    gap: 6px;
    position: relative;
  }

  .centered::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image: url('../assets/logo.png');
    background-repeat: no-repeat;
    background-position: center center;
    background-size: 120px auto;
    opacity: 0.1;
    z-index: 0;
  }

  .centered .image-size {
    display: none;
  }

  .centered > div {
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
    align-items: stretch;
    position: relative;
    z-index: 1;
  }

  .centered div {
    padding: 0 !important;
  }

  .centered .button-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .centered .button-group > .v-btn {
    width: 100%;
  }

  .centered .button-group > .v-btn:first-child {
    order: 1;
  }

  .centered .button-group > .v-btn:last-child {
    order: 2;
  }

  .centered .redact-check {
    margin: 0;
    order: 3;
  }

  .image-size {
    width: 120px;
  }
}

@media (min-width: 768px) and (max-width: 1023px) {
  .viewport-container {
    padding-top: 10px;
    height: calc(100vh - 130px);
    overflow-y: auto;
  }

  .viewport {
    height: auto;
    min-height: 100%;
    padding-top: 0;
  }

  .col {
    height: auto;
    min-height: auto;
  }

  .col-container {
    height: auto;
    min-height: auto;
    border: 10px solid var(--vt-c-text-dark-2);
    margin-bottom: 5px;
  }

  .border {
    height: auto;
    max-height: 400px;
  }

  .texts-height {
    height: auto;
    min-height: auto;
    max-height: 400px;
  }

  .texts-height :deep(.v-input__control),
  .texts-height :deep(.v-field),
  .texts-height :deep(.v-field__field),
  .texts-height :deep(textarea) {
    height: auto;
    max-height: 400px;
  }

  .output-text {
    min-height: 200px;
    height: auto;
  }

  .centered {
    padding: 15px;
    min-height: auto;
    display: grid;
    grid-template-columns: auto 1fr auto;
    grid-template-rows: auto auto;
    gap: 10px;
    align-items: center;
  }

  .centered div {
    padding: 0 !important;
  }

  .centered .image-size {
    grid-column: 1;
    grid-row: 1 / 3;
    width: 100px;
    margin: 0;
  }

  .centered > div {
    grid-column: 2 / 4;
    grid-row: 1 / 3;
    padding: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    gap: 10px;
    align-items: center;
  }

  .centered .button-group > .v-btn:first-child {
    grid-column: 1;
    grid-row: 1;
    max-width: 200px;
  }

  .centered .button-group > .v-btn:last-child {
    grid-column: 2;
    grid-row: 1;
    max-width: 200px;
  }

  .centered .redact-check {
    grid-column: 1 / 3;
    grid-row: 2;
    margin: 0;
    justify-self: start;
  }

  .image-size {
    width: 120px;
  }
}

@media (min-width: 1024px) and (max-width: 1279px) {
  .viewport-container {
    padding-top: 10px;
    height: calc(100vh - 95px);
    overflow-y: auto;
  }

  .viewport {
    height: auto;
    min-height: 100%;
    padding-top: 0;
  }

  .col {
    height: auto;
    min-height: auto;
  }

  .col-container {
    height: auto;
    border: 10px solid var(--vt-c-text-dark-2);
    margin-bottom: 5px;
  }

  .border {
    height: auto;
    max-height: 400px;
  }

  .texts-height {
    height: auto;
    min-height: auto;
    max-height: 400px;
  }

  .texts-height :deep(.v-input__control),
  .texts-height :deep(.v-field),
  .texts-height :deep(.v-field__field),
  .texts-height :deep(textarea) {
    height: auto;
    max-height: 400px;
  }

  .output-text {
    min-height: 200px;
    height: auto;
    max-height: 400px;
  }

  .centered {
    padding: 15px;
    min-height: auto;
    display: grid;
    grid-template-columns: auto 1fr auto;
    grid-template-rows: auto auto;
    gap: 10px;
    align-items: center;
  }

  .centered .image-size {
    grid-column: 1;
    grid-row: 1 / 3;
    width: 120px;
    margin: 0;
  }

  .centered > div {
    grid-column: 2 / 4;
    grid-row: 1 / 3;
    padding: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    gap: 10px;
    align-items: center;
  }

  .centered .button-group > .v-btn:first-child {
    grid-column: 1;
    grid-row: 1;
    max-width: 200px;
  }

  .centered .button-group > .v-btn:last-child {
    grid-column: 2;
    grid-row: 1;
    max-width: 200px;
  }

  .centered .redact-check {
    grid-column: 1 / 3;
    grid-row: 2;
    margin: 0;
    justify-self: start;
  }
}

</style>