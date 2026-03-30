targetScope = 'resourceGroup'

@description('Primary Azure region for the large deployment resources.')
param location string = resourceGroup().location

@description('Azure region used for the Azure OpenAI account and model deployment. This can differ from the primary resource group location when model availability requires it.')
param azureOpenAiLocation string = location

@description('Short environment name used in resource naming, such as dev, staging, or prod.')
@allowed([
  'dev'
  'staging'
  'prod'
])
param environmentName string = 'dev'

@description('Base application name used in resource naming.')
param appName string = 'ctxledger'

@description('Container image tag to deploy from Azure Container Registry.')
param imageTag string = 'latest'

@description('Azure Container Apps environment name.')
param containerAppsEnvironmentName string = '${appName}-${environmentName}-aca-env'

@description('Azure Container Registry name. Must be globally unique and use only alphanumeric characters.')
param containerRegistryName string = take('${toLower(replace(appName, '-', ''))}${toLower(replace(environmentName, '-', ''))}acr', 50)

@description('Azure Container App name for the ctxledger MCP server.')
param containerAppName string = '${appName}-${environmentName}'

@description('Azure OpenAI account name.')
param azureOpenAiAccountName string = take('${toLower(replace(appName, '-', ''))}${toLower(replace(environmentName, '-', ''))}openai', 64)

@description('Custom subdomain used by Azure OpenAI. Must be globally unique.')
param azureOpenAiCustomSubdomain string = take('${toLower(replace(appName, '-', ''))}${toLower(replace(environmentName, '-', ''))}openai', 64)

@description('Azure OpenAI embedding deployment name.')
param azureOpenAiEmbeddingDeploymentName string = 'embeddings'

@description('Azure OpenAI embedding model name.')
param azureOpenAiEmbeddingModelName string = 'text-embedding-3-small'

@description('Azure OpenAI embedding model version.')
param azureOpenAiEmbeddingModelVersion string = '1'

@description('Azure OpenAI SKU name.')
param azureOpenAiSkuName string = 'S0'

@description('Azure OpenAI capacity units for the embedding deployment.')
@minValue(1)
param azureOpenAiDeploymentCapacity int = 30

@description('Azure OpenAI authentication mode used by PostgreSQL azure_ai bootstrap.')
@allowed([
  'auto'
  'subscription_key'
  'managed_identity'
])
param azureOpenAiAuthMode string = 'auto'

@secure()
@description('Azure OpenAI subscription key used when azureOpenAiAuthMode is subscription_key.')
param azureOpenAiSubscriptionKey string = ''

@description('Comma-separated PostgreSQL extension allowlist for Flexible Server.')
param postgresAllowedExtensions string = 'vector,azure_ai,age'

@description('Whether the bootstrap script should ensure the age extension exists.')
param bootstrapEnsureAge bool = true

@description('Maximum time in seconds for the bootstrap script to wait for PostgreSQL readiness.')
@minValue(30)
param bootstrapWaitTimeoutSeconds int = 300

@description('Interval in seconds between PostgreSQL readiness checks during bootstrap.')
@minValue(1)
param bootstrapWaitIntervalSeconds int = 5

@description('Whether the bootstrap script should validate Azure OpenAI embedding creation after configuration.')
param bootstrapValidateEmbeddings bool = true

@description('Azure Database for PostgreSQL Flexible Server name.')
param postgresServerName string = take('${toLower(replace(appName, '-', ''))}${toLower(replace(environmentName, '-', ''))}psql', 63)

@description('Database name used by ctxledger.')
param postgresDatabaseName string = 'ctxledger'

@description('Administrator login name for PostgreSQL Flexible Server.')
param postgresAdminLogin string = take('${toLower(replace(appName, '-', ''))}${toLower(replace(environmentName, '-', ''))}admin', 63)

@secure()
@description('Administrator password for PostgreSQL Flexible Server. Leave empty to auto-generate a deterministic deployment-time value.')
param postgresAdminPassword string = ''

var effectivePostgresAdminPassword = empty(postgresAdminPassword)
  ? guid(subscription().subscriptionId, resourceGroup().id, appName, environmentName, 'postgres-admin-password')
  : postgresAdminPassword

@description('PostgreSQL major version for Flexible Server.')
@allowed([
  '16'
  '17'
])
param postgresVersion string = '16'

@description('PostgreSQL SKU name for Flexible Server.')
param postgresSkuName string = 'Standard_D2s_v3'

@description('PostgreSQL storage size in GiB.')
@minValue(32)
param postgresStorageSizeGB int = 128

@description('Whether high availability is enabled for PostgreSQL Flexible Server.')
param postgresHighAvailabilityEnabled bool = false

@description('Container CPU cores for the ctxledger app.')
@allowed([
  1
  2
  4
])
param containerCpu int = 1

@description('Container memory in GiB for the ctxledger app.')
@allowed([
  '1Gi'
  '2Gi'
  '4Gi'
  '8Gi'
])
param containerMemory string = '2Gi'

@description('Minimum replica count for the ctxledger Container App.')
@minValue(1)
param minReplicas int = 1

@description('Maximum replica count for the ctxledger Container App.')
@minValue(1)
param maxReplicas int = 3

@description('Whether external ingress is enabled for the ctxledger Container App.')
param externalIngressEnabled bool = true

@description('Container listening port for the ctxledger HTTP MCP endpoint.')
param targetPort int = 8080

@description('MCP endpoint path exposed by the application.')
param mcpHttpPath string = '/mcp'

@description('Whether debug endpoints are enabled in the deployed application.')
param enableDebugEndpoints bool = false

@description('Application log level.')
@allowed([
  'debug'
  'info'
  'warning'
  'error'
  'critical'
])
param logLevel string = 'info'

@description('Whether structured logging is enabled.')
param logStructured bool = true

@description('Database connection timeout in seconds.')
@minValue(1)
param dbConnectTimeoutSeconds int = 5

@description('Optional PostgreSQL statement timeout in milliseconds. Use 0 to omit the setting.')
@minValue(0)
param dbStatementTimeoutMs int = 0

@description('Database schema name used by ctxledger.')
param dbSchemaName string = 'public'

@description('Minimum PostgreSQL connection pool size per replica.')
@minValue(0)
param dbPoolMinSize int = 1

@description('Maximum PostgreSQL connection pool size per replica.')
@minValue(1)
param dbPoolMaxSize int = 10

@description('PostgreSQL connection pool acquisition timeout in seconds.')
@minValue(1)
param dbPoolTimeoutSeconds int = 5

@description('Whether Apache AGE support is enabled in the application configuration.')
param dbAgeEnabled bool = true

@description('Apache AGE graph name used by ctxledger.')
param dbAgeGraphName string = 'ctxledger_memory'

@description('Whether embedding support is enabled.')
param embeddingEnabled bool = true

@description('Embedding provider for ctxledger. Azure large deployments should prefer Azure OpenAI-compatible usage.')
@allowed([
  'disabled'
  'local_stub'
  'openai'
  'voyageai'
  'cohere'
  'custom_http'
])
param embeddingProvider string = 'custom_http'

@description('Embedding execution mode used by the application runtime.')
@allowed([
  'app_generated'
  'postgres_azure_ai'
])
param embeddingExecutionMode string = 'postgres_azure_ai'

@description('Embedding model name.')
param embeddingModel string = 'text-embedding-3-small'

@description('Embedding vector dimensions.')
@minValue(1)
param embeddingDimensions int = 1536

@description('Base URL used when the application performs direct Azure OpenAI-compatible embedding calls.')
param embeddingBaseUrl string = ''

@secure()
@description('Optional credential material for direct application-side Azure OpenAI-compatible embedding calls. Leave empty when PostgreSQL-side azure_ai is the only embedding path.')
param embeddingApiKey string = ''

@description('Preferred Azure embedding execution mode for deployment planning. postgres_azure_ai is the intended large-pattern default.')
@allowed([
  'postgres_azure_ai'
  'application_azure_openai'
  'disabled'
])
param azureEmbeddingMode string = 'postgres_azure_ai'

@description('Explicit Azure OpenAI API version for direct application-side Azure OpenAI-compatible calls.')
param azureOpenAiApiVersion string = '2024-10-21'

@description('Whether to enable a user-assigned managed identity on the Container App.')
param enableUserAssignedIdentity bool = true

@description('Name of the user-assigned managed identity created for bootstrap and deployment operations.')
param userAssignedIdentityName string = '${appName}-${environmentName}-bootstrap-id'

@description('Authentication rendering mode for generated MCP client snippet artifacts.')
@allowed([
  'none'
  'bearer_header'
  'custom_header'
])
param mcpAuthMode string = 'none'

@description('Header name used for generated MCP client snippet artifacts when mcpAuthMode is custom_header.')
param mcpAuthHeaderName string = 'Authorization'

@description('Additional tags applied to all resources created by this template.')
param tags object = {}

var normalizedAppName = toLower(replace(appName, '-', ''))
var normalizedEnvironmentName = toLower(replace(environmentName, '-', ''))
var baseTags = union(tags, {
  'app': appName
  'environment': environmentName
  'deployment-pattern': 'large'
  'managed-by': 'bicep'
  'system': 'ctxledger'
  'ai-provider': 'azure-openai'
  'embedding-mode': azureEmbeddingMode
  'mcp-auth-mode': mcpAuthMode
})

var postgresSkuTier = startsWith(postgresSkuName, 'Standard_') ? 'GeneralPurpose' : 'Burstable'
var postgresVersionedDatabaseName = '${postgresServerName}/${postgresDatabaseName}'
var registryLoginServer = '${containerRegistryName}.azurecr.io'
var containerImageRepository = normalizedAppName
var placeholderContainerImage = 'mcr.microsoft.com/k8se/quickstart:latest'
var containerImage = placeholderContainerImage
var postgresHost = '${postgresServerName}.postgres.database.azure.com'
var postgresAdminPrincipal = '${postgresAdminLogin}'
var postgresConnectionString = 'postgresql://${postgresAdminPrincipal}:${postgresAdminPassword}@${postgresHost}:5432/${postgresDatabaseName}?sslmode=require'
var dbStatementTimeoutValue = dbStatementTimeoutMs > 0 ? string(dbStatementTimeoutMs) : ''
var userAssignedIdentityResourceId = userAssignedIdentity.id
var userAssignedIdentityMap = enableUserAssignedIdentity
  ? {
      '${userAssignedIdentityResourceId}': {}
    }
  : {}
var identityType = enableUserAssignedIdentity
  ? 'UserAssigned'
  : 'SystemAssigned'
var azureOpenAiEndpoint = 'https://${azureOpenAiCustomSubdomain}.openai.azure.com'
var effectiveEmbeddingBaseUrl = !empty(embeddingBaseUrl) ? embeddingBaseUrl : azureOpenAiEndpoint
var directAzureOpenAiEnabled = azureEmbeddingMode == 'application_azure_openai'
var postgresAzureAiEnabled = azureEmbeddingMode == 'postgres_azure_ai'
var effectiveAzureOpenAiAuthMode = azureOpenAiAuthMode == 'auto'
  ? 'managed_identity'
  : azureOpenAiAuthMode
var postgresManagedIdentityEnabled = effectiveAzureOpenAiAuthMode == 'managed_identity'


resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-${environmentName}-logs'
  location: location
  tags: baseTags
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: containerRegistryName
  location: location
  tags: baseTags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    adminUserEnabled: false
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      trustPolicy: {
        type: 'Notary'
        status: 'disabled'
      }
      retentionPolicy: {
        days: 7
        status: 'disabled'
      }
      exportPolicy: {
        status: 'enabled'
      }
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
    encryption: {
      status: 'disabled'
    }
    dataEndpointEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'AzureServices'
    networkRuleBypassAllowedForTasks: false
    zoneRedundancy: 'Disabled'
    anonymousPullEnabled: false
    roleAssignmentMode: 'LegacyRegistryPermissions'
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: baseTags
  properties: {}
}



resource userAssignedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (enableUserAssignedIdentity) {
  name: userAssignedIdentityName
  location: location
  tags: baseTags
}

resource azureOpenAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: azureOpenAiAccountName
  location: azureOpenAiLocation
  tags: baseTags
  kind: 'OpenAI'
  sku: {
    name: azureOpenAiSkuName
  }
  properties: {
    customSubDomainName: azureOpenAiCustomSubdomain
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: azureOpenAiAuthMode == 'managed_identity'
  }
}

resource azureOpenAiEmbeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  name: '${azureOpenAiAccount.name}/${azureOpenAiEmbeddingDeploymentName}'
  sku: {
    name: 'Standard'
    capacity: azureOpenAiDeploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: azureOpenAiEmbeddingModelName
      version: azureOpenAiEmbeddingModelVersion
    }
    raiPolicyName: 'Microsoft.Default'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresServerName
  location: location
  tags: baseTags
  identity: postgresManagedIdentityEnabled ? {
    type: 'SystemAssigned'
  } : null
  sku: {
    name: postgresSkuName
    tier: postgresSkuTier
  }
  properties: {
    version: postgresVersion
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: effectivePostgresAdminPassword
    storage: {
      storageSizeGB: postgresStorageSizeGB
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    highAvailability: {
      mode: postgresHighAvailabilityEnabled ? 'ZoneRedundant' : 'Disabled'
    }
    maintenanceWindow: {
      customWindow: 'Disabled'
      dayOfWeek: 0
      startHour: 0
      startMinute: 0
    }
    createMode: 'Default'
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  name: postgresVersionedDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
  dependsOn: [
    postgresServer
  ]
}

resource postgresFirewallAllowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  name: '${postgresServer.name}/allow-azure-services'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
  dependsOn: [
    postgresServer
  ]
}

resource postgresAllowedExtensionsConfig 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  name: '${postgresServer.name}/azure.extensions'
  properties: {
    value: postgresAllowedExtensions
    source: 'user-override'
  }
  dependsOn: [
    postgresServer
  ]
}

resource postgresManagedIdentityOpenAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (postgresManagedIdentityEnabled) {
  name: guid(azureOpenAiAccount.id, postgresServer.id, 'CognitiveServicesOpenAIUser')
  scope: azureOpenAiAccount
  properties: {
    principalId: postgresServer.identity.principalId
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    )
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    azureOpenAiAccount
    postgresServer
  ]
}



resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableUserAssignedIdentity) {
  name: guid(containerRegistry.id, userAssignedIdentity.id, 'AcrPull')
  scope: containerRegistry
  properties: {
    principalId: userAssignedIdentity.properties.principalId
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    userAssignedIdentity
    containerRegistry
  ]
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output CONTAINER_IMAGE_REPOSITORY string = containerImageRepository
output CONTAINER_IMAGE_REFERENCE string = containerImage
output CONTAINER_APP_NAME string = containerAppName
output POSTGRES_SERVER_FQDN string = postgresHost
output POSTGRES_DATABASE_NAME string = postgresDatabaseName
output AZURE_OPENAI_ENDPOINT string = azureOpenAiEndpoint
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME string = azureOpenAiEmbeddingDeploymentName
output AZURE_EMBEDDING_MODE string = azureEmbeddingMode
output MCP_AUTH_MODE string = mcpAuthMode
output MCP_AUTH_HEADER_NAME string = mcpAuthHeaderName
output AZURE_OPENAI_EFFECTIVE_AUTH_MODE string = effectiveAzureOpenAiAuthMode
output LOG_ANALYTICS_WORKSPACE_NAME string = logAnalyticsWorkspace.name
output notes array = [
  'This template provisions Azure-side prerequisites for the ctxledger large deployment pattern.'
  'Container App creation and update are intentionally handled during azd deploy rather than in the Bicep provision phase.'
  'PostgreSQL extension allowlisting is provisioned here, while azure_ai/bootstrap and schema bootstrap are expected to run from the azd postprovision workflow.'
  'Validate pgvector availability before accepting the environment.'
  'This template allowlists PostgreSQL extensions through the azure.extensions server parameter and provisions the Azure-side prerequisites for PostgreSQL azure_ai integration.'
  'Generated MCP handoff artifacts can be aligned with the current auth posture through MCP_AUTH_MODE and MCP_AUTH_HEADER_NAME.'
  'Validate azure_ai availability and configure PostgreSQL to use Azure OpenAI directly where practical.'
  'Validate Apache AGE support explicitly; do not assume managed PostgreSQL parity with the local Docker image.'
  'Azure large deployments should use Azure OpenAI instead of carrying forward the small pattern direct OpenAI posture.'
  'The standard azd remoteBuild flow is expected to build and deploy the real application image after provisioning completes.'
]
