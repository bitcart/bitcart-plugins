<template>
  <v-card>
    <v-card-text>
      <auto-complete
        v-model="selectedCurrency"
        label="Currency"
        url="cryptos"
      />
      <v-text-field v-model="xpub" label="Xpub" />
      <v-text-field v-model="contract" label="Contract" />
      <div class="pb-5">
        <p class="text-h6">Additional xpub data</p>
        <list-edit v-model="additionalData" />
      </div>
      <v-autocomplete
        v-model="method"
        :loading="autoLoading"
        :items="items"
        :search-input.sync="autosearch"
        :rules="[rules.required]"
        label="Method"
        color="#90a4ae"
      >
      </v-autocomplete>
      <div class="pb-5">
        <p class="text-h6">Positional arguments</p>
        <list-edit v-model="args" :list-only="true" />
      </div>
      <div class="pb-5">
        <p class="text-h6">Keyword arguments</p>
        <list-edit v-model="kwargs" />
      </div>
      <v-btn color="primary" class="mb-2" @click="sendRequest">Send</v-btn>
      <v-divider />
      <code v-if="output" style="white-space: pre-wrap" v-text="output" />
      <v-progress-circular v-else-if="loading" indeterminate />
    </v-card-text>
  </v-card>
</template>

<script>
import AutoComplete from "@/components/AutoComplete.vue"
import ListEdit from "@/components/ListEdit"

export default {
  components: {
    AutoComplete,
    ListEdit,
  },
  layout: "admin",
  middleware: "superuserOnly",
  data() {
    return {
      selectedCurrency: "",
      xpub: "",
      contract: "",
      additionalData: {},
      method: "",
      args: [],
      kwargs: {},
      rules: this.$utils.rules,
      autosearch: "",
      autoLoading: false,
      items: [],
      output: "",
      loading: false,
    }
  },
  watch: {
    autosearch(val) {
      this.fetchData(val)
    },
    selectedCurrency(val) {
      this.fetchData(val)
    },
  },
  methods: {
    fetchData(val) {
      if (val === null || typeof val === "undefined") {
        val = ""
      }
      const url = `/cryptos/${this.selectedCurrency}/rpc`
      this.$axios.post(url, { method: "help", params: [] }).then((resp) => {
        this.items = resp.data.result
      })
    },
    sendRequest() {
      this.loading = true
      this.output = ""
      setTimeout(() => {
        const url = `/cryptos/${this.selectedCurrency}/rpc`
        this.$axios
          .post(url, {
            method: this.method,
            params: [
              ...this.args,
              {
                ...this.kwargs,
                xpub: {
                  xpub: this.xpub,
                  contract: this.contract,
                  ...this.additionalData,
                },
              },
            ],
          })
          .then((resp) => {
            this.output = resp.data.result || resp.data.error.message
            this.loading = false
          })
          .catch((e) => {
            this.loading = false
            this.output = "Error. Probably you didn't configure currency"
          })
      }, 300)
    },
  },
}
</script>
