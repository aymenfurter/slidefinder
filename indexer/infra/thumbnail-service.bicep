// Thumbnail Service Azure Container Apps Deployment
// Deploys a scalable thumbnail generation microservice

@description('The location for all resources')
param location string = resourceGroup().location

@description('Tags for resources')
param tags object = {}

@description('Name of the Container App Environment')
param containerAppEnvName string

@description('Name of the Container Registry')
param containerRegistryName string

@description('Image name for the thumbnail service')
param imageName string = 'thumbnail-service'

@description('Image tag')
param imageTag string = 'latest'

@description('Minimum number of replicas')
@minValue(0)
@maxValue(30)
param minReplicas int = 2

@description('Maximum number of replicas')
@minValue(1)
@maxValue(30)
param maxReplicas int = 10

// Reference existing Container App Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppEnvName
}

// Reference existing Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

// User Assigned Identity for the thumbnail service
resource thumbnailServiceIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-thumbnail-service'
  location: location
  tags: tags
}

// ACR Pull role assignment for the identity
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, thumbnailServiceIdentity.id, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: containerRegistry
  properties: {
    principalId: thumbnailServiceIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

// Thumbnail Service Container App
resource thumbnailService 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'thumbnail-service'
  location: location
  tags: union(tags, { 'azd-service-name': 'thumbnail-service' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${thumbnailServiceIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: thumbnailServiceIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'thumbnail-service'
          image: '${containerRegistry.properties.loginServer}/${imageName}:${imageTag}'
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'PORT'
              value: '8080'
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '1'  // Each container handles 1 request at a time
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPullRoleAssignment
  ]
}

// Outputs
output serviceUrl string = 'https://${thumbnailService.properties.configuration.ingress.fqdn}'
output serviceName string = thumbnailService.name
output identityPrincipalId string = thumbnailServiceIdentity.properties.principalId
