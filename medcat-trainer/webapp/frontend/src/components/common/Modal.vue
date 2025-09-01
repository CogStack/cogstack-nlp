<template>
  <transition name="modal">
    <div class="modal-mask" @click="close">
      <div class="modal-wrapper">
        <div class="modal-container" @click.stop>
          <font-awesome-icon v-if="closable" icon="times" class="close" @click="close"></font-awesome-icon>
          <div class="modal-header">
            <slot name="header">
            </slot>
          </div>

          <div class="modal-body">
            <slot name="body">
            </slot>
          </div>

          <div class="modal-footer">
            <slot name="footer">
            </slot>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script>

export default {
  name: 'Modal',
  emits: ['modal:close'],
  props: {
    closable: Boolean
  },
  methods: {
    close () {
      this.$emit('modal:close')
    }
  }
}

</script>

<style lang="scss">
.close {
  opacity: 0.5;
  float: right;
  font-size: 1.5rem;

  :hover {
    opacity: 0.75;
    cursor: pointer;
  }
}

.modal-mask {
  position: fixed;
  z-index: 9998;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, .5);
  display: table;
  transition: opacity .3s ease;
}

.modal-wrapper {
  display: table-cell;
  vertical-align: middle;
}

.modal-container {
  width: 550px;
  margin: 0 auto;
  padding: 10px 15px;
  background-color: #fff;
  border-radius: 2px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .33);
  transition: all .3s ease;
  font-family: Helvetica, Arial, sans-serif;
}

.modal-header div {
  width: 100%;
}

.modal-header h3 {
  margin-top: 0;
  text-align: left;
  margin-left: 0;
}

.modal-header h4 {
  display: inline-block;
  margin-left: 0;
}

.modal-body {
  margin: 20px 0;
  overflow-y: auto;
  max-height: 550px;
}

.modal-footer {
  display: flex !important;
  justify-content: center !important;
}

.modal-default-button {
  float: right;
}

.modal-content {
  border: 0;
}

.modal-enter {
  opacity: 0;
}

.modal-leave-active {
  opacity: 0;
}

.modal-enter .modal-container,
.modal-leave-active .modal-container {
  -webkit-transform: scale(1.1);
  transform: scale(1.1);
}

</style>
