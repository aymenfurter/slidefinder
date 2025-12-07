@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}

@description('Whether the slidefinder container app already exists')
param slidefinderExists bool = false

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Principal type of user or app')
param principalType string = 'User'

@description('Location for Azure OpenAI resources')
@allowed(['australiaeast', 'eastus2', 'francecentral', 'japaneast', 'norwayeast', 'swedencentral', 'uksouth', 'westus'])
param azureOpenAILocation string = 'eastus2'

@description('Name of the OpenAI model to deploy')
param openAIModelName string = 'gpt-4.1-mini'

@description('Version of the OpenAI model to deploy')
param openAIModelVersion string = '2025-04-14'

@description('OpenAI model deployment type')
@allowed(['Standard', 'GlobalStandard'])
param openAIModelDeploymentType string = 'GlobalStandard'

@description('OpenAI model deployment capacity (tokens per minute in thousands)')
param openAIModelCapacity int = 50

@description('Name of the OpenAI embedding model to deploy')
param embeddingModelName string = 'text-embedding-ada-002'

@description('Version of the OpenAI embedding model to deploy')
param embeddingModelVersion string = '2'

@description('OpenAI embedding model deployment type')
@allowed(['Standard', 'GlobalStandard'])
param embeddingModelDeploymentType string = 'Standard'

@description('OpenAI embedding model deployment capacity (tokens per minute in thousands)')
param embeddingModelCapacity int = 50

@description('Azure AI Search index name')
param searchIndexName string = 'slidefinder'

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)

// ============================================================================
// Azure AI Search
// ============================================================================
resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: '${abbrs.searchSearchServices}${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
  }
}

// ============================================================================
// Azure OpenAI Service
// ============================================================================
resource openAIService 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${abbrs.cognitiveServicesAccounts}openai-${resourceToken}'
  location: azureOpenAILocation
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${abbrs.cognitiveServicesAccounts}openai-${resourceToken}'
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// ============================================================================
// Azure OpenAI Model Deployment
// ============================================================================
resource openAIDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAIService
  name: openAIModelName
  sku: {
    name: openAIModelDeploymentType
    capacity: openAIModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: openAIModelName
      version: openAIModelVersion
    }
    raiPolicyName: 'Microsoft.Default'
  }
}

// ============================================================================
// Azure OpenAI Embedding Model Deployment
// ============================================================================
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAIService
  name: embeddingModelName
  dependsOn: [openAIDeployment]
  sku: {
    name: embeddingModelDeploymentType
    capacity: embeddingModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
  }
}

// ============================================================================
// Monitoring (Log Analytics + Application Insights)
// ============================================================================
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}

// ============================================================================
// Container Registry
// ============================================================================
module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    publicNetworkAccess: 'Enabled'
    roleAssignments: [
      {
        principalId: slidefinderIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId(
          'Microsoft.Authorization/roleDefinitions',
          '7f951dda-4ed3-4680-a7ca-43fe172d538d'
        )
      }
    ]
  }
}

// ============================================================================
// Container Apps Environment
// ============================================================================
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.4.5' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
  }
}

// ============================================================================
// User Assigned Identity for Container App
// ============================================================================
module slidefinderIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'slidefinderidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}slidefinder-${resourceToken}'
    location: location
  }
}

// ============================================================================
// Fetch existing container image (if app exists)
// ============================================================================
module slidefinderFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'slidefinder-fetch-image'
  params: {
    exists: slidefinderExists
    name: 'slidefinder'
  }
}

// ============================================================================
// Container App - Slidefinder
// ============================================================================
module slidefinder 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'slidefinder'
  params: {
    name: 'slidefinder'
    ingressTargetPort: 7004
    ingressExternal: true
    ingressTransport: 'http'
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList: [
        {
          name: 'azure-ai-search-key'
          value: searchService.listAdminKeys().primaryKey
        }
        {
          name: 'azure-openai-key'
          value: openAIService.listKeys().key1
        }
      ]
    }
    containers: [
      {
        image: slidefinderFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('1.0')
          memory: '2.0Gi'
        }
        env: [
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: slidefinderIdentity.outputs.clientId
          }
          {
            name: 'AZURE_SEARCH_ENDPOINT'
            value: 'https://${searchService.name}.search.windows.net'
          }
          {
            name: 'AZURE_SEARCH_API_KEY'
            secretRef: 'azure-ai-search-key'
          }
          {
            name: 'AZURE_SEARCH_INDEX_NAME'
            value: searchIndexName
          }
          {
            name: 'AZURE_OPENAI_ENDPOINT'
            value: openAIService.properties.endpoint
          }
          {
            name: 'AZURE_OPENAI_API_KEY'
            secretRef: 'azure-openai-key'
          }
          {
            name: 'AZURE_OPENAI_DEPLOYMENT'
            value: openAIDeployment.name
          }
          {
            name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
            value: embeddingDeployment.name
          }
          {
            name: 'AZURE_OPENAI_API_VERSION'
            value: '2024-10-21'
          }
          {
            name: 'PORT'
            value: '7004'
          }
          {
            name: 'HOST'
            value: '0.0.0.0'
          }
        ]
      }
    ]
    managedIdentities: {
      systemAssigned: false
      userAssignedResourceIds: [slidefinderIdentity.outputs.resourceId]
    }
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: slidefinderIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'slidefinder' })
  }
}

// ============================================================================
// Role Assignments for Container App Identity
// ============================================================================

// Search Index Data Contributor role for the container app identity
resource containerAppSearchIndexDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, slidefinder.name, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  properties: {
    principalId: slidefinderIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  }
}

// Search Service Contributor role for the container app identity
resource containerAppSearchServiceContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, slidefinder.name, '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  properties: {
    principalId: slidefinderIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  }
}

// ============================================================================
// Role Assignments for User (if principalId provided)
// ============================================================================

// Search Index Data Contributor role for user
resource userSearchIndexDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  }
}

// Search Service Contributor role for user
resource userSearchServiceContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  }
}

// ============================================================================
// Outputs
// ============================================================================
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_SLIDEFINDER_ID string = slidefinder.outputs.resourceId
output AZURE_CONTAINER_APP_ENVIRONMENT_NAME string = containerAppsEnvironment.name
output AZURE_CONTAINER_APP_NAME string = slidefinder.name
output SERVICE_SLIDEFINDER_URI string = 'https://${slidefinder.outputs.fqdn}'
output AZURE_TENANT_ID string = subscription().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output SLIDEFINDER_IDENTITY_PRINCIPAL_ID string = slidefinderIdentity.outputs.principalId
output AZURE_AI_SEARCH_ENDPOINT string = 'https://${searchService.name}.search.windows.net'
output AZURE_AI_SEARCH_NAME string = searchService.name
output AZURE_OPENAI_ENDPOINT string = openAIService.properties.endpoint
output AZURE_OPENAI_DEPLOYMENT string = openAIDeployment.name
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingDeployment.name
