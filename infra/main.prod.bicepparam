using './main.bicep'

param location = 'japaneast'
param azureOpenAiLocation = location
param environmentName = 'prod'
param appName = 'ctxledger'

param imageTag = 'latest'

param postgresVersion = '16'
param postgresSkuName = 'Standard_D8s_v3'
param postgresStorageSizeGB = 512
param postgresHighAvailabilityEnabled = true

param containerCpu = 2
param containerMemory = '4Gi'
param minReplicas = 2
param maxReplicas = 6
param externalIngressEnabled = true
param targetPort = 8080
param mcpHttpPath = '/mcp'

param enableDebugEndpoints = false
param logLevel = 'info'
param logStructured = true

param dbConnectTimeoutSeconds = 5
param dbStatementTimeoutMs = 30000
param dbSchemaName = 'public'
param dbPoolMinSize = 2
param dbPoolMaxSize = 20
param dbPoolTimeoutSeconds = 5

param dbAgeEnabled = true
param dbAgeGraphName = 'ctxledger_memory'

param embeddingEnabled = true
param embeddingProvider = 'custom_http'
param embeddingExecutionMode = 'postgres_azure_ai'
param embeddingModel = 'text-embedding-3-small'
param embeddingDimensions = 1536
param embeddingBaseUrl = ''
param embeddingApiKey = ''
param azureEmbeddingMode = 'postgres_azure_ai'
param azureOpenAiApiVersion = '2024-10-21'
param azureOpenAiAuthMode = 'auto'
param azureOpenAiSubscriptionKey = ''

param postgresAllowedExtensions = 'vector,azure_ai,age'
param bootstrapEnsureAge = true
param bootstrapWaitTimeoutSeconds = 300
param bootstrapWaitIntervalSeconds = 5
param bootstrapValidateEmbeddings = true

param enableUserAssignedIdentity = true

param mcpAuthMode = 'custom_header'
param mcpAuthHeaderName = 'X-Auth-Request-Access-Token'

param tags = {
  owner: 'ctxledger'
  environment: 'prod'
  workload: 'mcp'
  deploymentPattern: 'large'
  aiProvider: 'azure-openai'
  embeddingMode: 'postgres_azure_ai'
  azureOpenAiAuthMode: 'auto'
  dataClassification: 'internal'
  criticality: 'production'
  mcpAuthMode: 'custom_header'
  mcpAuthHeaderName: 'X-Auth-Request-Access-Token'
}
