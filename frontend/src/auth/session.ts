import { isCognitoAuthEnabled } from './config'

export async function getAuthorizationHeaders(): Promise<Record<string, string>> {
  if (!isCognitoAuthEnabled) {
    return {}
  }

  const { fetchAuthSession } = await import('aws-amplify/auth')
  const session = await fetchAuthSession()
  const accessToken = session.tokens?.accessToken?.toString()

  if (!accessToken) {
    return {}
  }

  return {
    Authorization: `Bearer ${accessToken}`,
  }
}
