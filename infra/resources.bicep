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

// ============================================================================
// Microsoft Foundry (Azure AI Services) Parameters
// ============================================================================

@description('The name of the Azure AI Foundry resource')
@maxLength(9)
param aiServicesName string = 'foundry'

@description('The name of your Foundry project')
param projectName string = 'slidefinder-project'

@description('The description of your Foundry project')
param projectDescription string = 'Slidefinder AI project for slide search and deck building'

@description('The display name of your Foundry project')
param projectDisplayName string = 'Slidefinder Project'

@description('Location for Azure AI Foundry resources')
@allowed([
  'australiaeast'
  'canadaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'japaneast'
  'koreacentral'
  'norwayeast'
  'polandcentral'
  'southindia'
  'swedencentral'
  'switzerlandnorth'
  'uaenorth'
  'uksouth'
  'westus'
  'westus2'
  'westus3'
  'westeurope'
  'southeastasia'
  'brazilsouth'
  'germanywestcentral'
  'italynorth'
  'southafricanorth'
  'southcentralus'
])
param aiFoundryLocation string = 'eastus2'

@description('Name of the OpenAI model to deploy')
param openAIModelName string = 'gpt-4o'

@description('Version of the OpenAI model to deploy')
param openAIModelVersion string = '2024-11-20'

@description('OpenAI model deployment type')
@allowed(['Standard', 'GlobalStandard'])
param openAIModelDeploymentType string = 'GlobalStandard'

@description('OpenAI model deployment capacity (tokens per minute in thousands)')
param openAIModelCapacity int = 30

@description('Name of the OpenAI embedding model to deploy')
param embeddingModelName string = 'text-embedding-ada-002'

@description('Version of the OpenAI embedding model to deploy')
param embeddingModelVersion string = '2'

@description('OpenAI embedding model deployment type')
@allowed(['Standard', 'GlobalStandard'])
param embeddingModelDeploymentType string = 'Standard'

@description('OpenAI embedding model deployment capacity (tokens per minute in thousands)')
param embeddingModelCapacity int = 30

@description('Azure AI Search index name')
param searchIndexName string = 'slidefinder'

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)

// Create a unique AI Foundry account name using the same pattern as resourceToken
var aiFoundryAccountName = toLower('${aiServicesName}${resourceToken}')

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
// Microsoft Foundry (Azure AI Services Account)
// ============================================================================
#disable-next-line BCP081
resource aiFoundryAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiFoundryAccountName
  location: aiFoundryLocation
  tags: tags
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: toLower(aiFoundryAccountName)
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// ============================================================================
// Microsoft Foundry Project
// ============================================================================
#disable-next-line BCP081
resource aiFoundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiFoundryAccount
  name: projectName
  location: aiFoundryLocation
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: projectDescription
    displayName: projectDisplayName
  }
}

// ============================================================================
// OpenAI Model Deployment
// ============================================================================
#disable-next-line BCP081
resource openAIDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiFoundryAccount
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
  }
}

// ============================================================================
// Embedding Model Deployment
// ============================================================================
#disable-next-line BCP081
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiFoundryAccount
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

// Reference to the Application Insights created by the monitoring module
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: '${abbrs.insightsComponents}${resourceToken}'
  dependsOn: [monitoring]
}

// ============================================================================
// AI Foundry Connection to Application Insights
// ============================================================================
#disable-next-line BCP081
resource aiFoundryAppInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: 'appinsights-connection'
  parent: aiFoundryAccount
  properties: {
    category: 'AppInsights'
    target: applicationInsights.id
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: applicationInsights.properties.ConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsights.id
    }
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
          name: 'azure-ai-foundry-key'
          value: aiFoundryAccount.listKeys().key1
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
            value: aiFoundryAccount.properties.endpoint
          }
          {
            name: 'AZURE_OPENAI_API_KEY'
            secretRef: 'azure-ai-foundry-key'
          }
          {
            name: 'AZURE_AI_FOUNDRY_PROJECT'
            value: aiFoundryProject.name
          }
          {
            name: 'AZURE_AI_PROJECT_ENDPOINT'
            value: 'https://${aiFoundryAccountName}.services.ai.azure.com/api/projects/${projectName}'
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
// Role Assignments for Container App Identity - Azure AI Search
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

// Search Index Data Reader role for the container app identity
resource containerAppSearchIndexDataReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, slidefinder.name, '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  properties: {
    principalId: slidefinderIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
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
// Role Assignments for Container App Identity - Microsoft Foundry / AI Services
// ============================================================================

// Azure AI Developer role for the container app identity
resource containerAppAzureAIDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, slidefinder.name, '64702f94-c441-49e6-a78b-ef80e0188fee')
  properties: {
    principalId: slidefinderIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

// Cognitive Services User role for the container app identity
resource containerAppCognitiveServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, slidefinder.name, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  properties: {
    principalId: slidefinderIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

// Azure AI User role for the container app identity
resource containerAppAzureAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, slidefinder.name, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  properties: {
    principalId: slidefinderIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// ============================================================================
// Role Assignments for User - Azure AI Search (if principalId provided)
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

// Search Index Data Reader role for user
resource userSearchIndexDataReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
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
// Role Assignments for User - Microsoft Foundry / AI Services (if principalId provided)
// ============================================================================

// Azure AI Developer role for user
resource userAzureAIDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, '64702f94-c441-49e6-a78b-ef80e0188fee')
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

// Cognitive Services User role for user
resource userCognitiveServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

// Azure AI User role for user
resource userAzureAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
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
output AZURE_OPENAI_ENDPOINT string = aiFoundryAccount.properties.endpoint
output AZURE_OPENAI_DEPLOYMENT string = openAIDeployment.name
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingDeployment.name
output AZURE_AI_FOUNDRY_ACCOUNT_NAME string = aiFoundryAccount.name
output AZURE_AI_FOUNDRY_PROJECT_NAME string = aiFoundryProject.name
output AZURE_AI_PROJECT_ENDPOINT string = 'https://${aiFoundryAccountName}.services.ai.azure.com/api/projects/${projectName}'
