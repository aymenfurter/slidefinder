targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Whether the slidefinder container app already exists')
param slidefinderExists bool = false

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Principal type of user or app')
param principalType string = 'User'

// Tags that should be applied to all resources.
// Note that 'azd-service-name' tags should be applied separately to service host resources.
var tags = {
  'azd-env-name': environmentName
}

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  scope: rg
  name: 'resources'
  params: {
    location: location
    tags: tags
    principalId: principalId
    principalType: principalType
    slidefinderExists: slidefinderExists
  }
}

// Outputs for azd
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_RESOURCE_SLIDEFINDER_ID string = resources.outputs.AZURE_RESOURCE_SLIDEFINDER_ID
output AZURE_CONTAINER_APP_ENVIRONMENT_NAME string = resources.outputs.AZURE_CONTAINER_APP_ENVIRONMENT_NAME
output AZURE_CONTAINER_APP_NAME string = resources.outputs.AZURE_CONTAINER_APP_NAME
output SERVICE_SLIDEFINDER_URI string = resources.outputs.SERVICE_SLIDEFINDER_URI
output AZURE_AI_SEARCH_ENDPOINT string = resources.outputs.AZURE_AI_SEARCH_ENDPOINT
output AZURE_AI_SEARCH_NAME string = resources.outputs.AZURE_AI_SEARCH_NAME
output AZURE_OPENAI_ENDPOINT string = resources.outputs.AZURE_OPENAI_ENDPOINT
output AZURE_OPENAI_DEPLOYMENT string = resources.outputs.AZURE_OPENAI_DEPLOYMENT
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = resources.outputs.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
