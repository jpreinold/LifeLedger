export const authMode = import.meta.env.VITE_AUTH_MODE === 'cognito' ? 'cognito' : 'local'
export const isCognitoAuthEnabled = authMode === 'cognito'

const cognitoRegion = import.meta.env.VITE_COGNITO_REGION
const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID
const userPoolClientId = import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID

export async function configureAuth() {
  if (!isCognitoAuthEnabled) {
    return
  }

  const missingConfig = [
    ['VITE_COGNITO_REGION', cognitoRegion],
    ['VITE_COGNITO_USER_POOL_ID', userPoolId],
    ['VITE_COGNITO_USER_POOL_CLIENT_ID', userPoolClientId],
  ].filter(([, value]) => !value)

  if (missingConfig.length > 0) {
    throw new Error(`Missing Cognito configuration: ${missingConfig.map(([key]) => key).join(', ')}`)
  }

  const { Amplify } = await import('aws-amplify')
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: {
          email: true,
        },
      },
    },
  })
}
