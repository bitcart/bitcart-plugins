<template>
  <v-row>
    <v-col class="px-3">
      <v-dialog v-model="showImportDialog" max-width="500px">
        <v-card>
          <v-card-title>Batch import</v-card-title>
          <v-card-text>
            <v-container>
              <v-row>
                <v-file-input
                  v-if="total === 0"
                  v-model="file"
                  :rules="fileRules"
                  label="CSV file"
                ></v-file-input>
                <div v-else class="text-h6">
                  Successfully imported {{ successful }}/{{ total }} entries
                </div>
              </v-row>
            </v-container>
          </v-card-text>
          <v-card-actions class="justify-center pb-5">
            <ManagementCommand
              v-if="total === 0"
              btn-text="Start importing"
              command-prefix="batchimport"
              :what="url"
              file-attr="file"
              class="pb-3"
              :file="true"
              :file-to-upload="file"
              :postprocess="postprocess"
            />
            <v-btn v-else color="primary" @click="showImportDialog = false">
              Close
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-btn color="primary" class="mr-2" @click="openImportDialog">
        Batch import
      </v-btn>
    </v-col>
  </v-row>
</template>

<script>
import ManagementCommand from "@/components/ManagementCommand"
export default {
  components: {
    ManagementCommand,
  },
  props: {
    url: {
      type: String,
      required: true,
    },
    triggerReload: {
      type: Function,
      required: true,
    },
  },
  data() {
    return {
      showImportDialog: false,
      file: null,
      loading: false,
      total: 0,
      successful: 0,
      fileRules: [
        (value) =>
          !value ||
          value.size < 50 * 1024 * 1024 ||
          "Import size should be less than 50 MB!",
        (value) => !value || value.type === "text/csv" || "File should be CSV",
      ],
    }
  },
  methods: {
    openImportDialog() {
      this.file = null
      this.total = 0
      this.successful = 0
      this.loading = false
      this.showImportDialog = true
    },
    importObjects() {
      this.loading = true
    },
    postprocess(data) {
      this.total = data.total
      this.successful = data.successful
      this.loading = false
      this.triggerReload()
    },
  },
}
</script>
