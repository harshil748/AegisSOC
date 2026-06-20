{{/*
Common name prefix for all aegis resources.
*/}}
{{- define "aegis.fullname" -}}
{{- default "aegis" .Values.nameOverride -}}
{{- end -}}

{{/*
Standard labels applied to every resource.
*/}}
{{- define "aegis.labels" -}}
app.kubernetes.io/part-of: aegissoc
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/*
Convert a services.<key> map key (e.g. graph_builder) to a k8s-safe
resource name suffix (graph-builder).
*/}}
{{- define "aegis.svcName" -}}
{{- printf "aegis-%s" (. | replace "_" "-") -}}
{{- end -}}
