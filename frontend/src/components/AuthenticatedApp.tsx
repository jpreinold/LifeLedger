import { Authenticator } from '@aws-amplify/ui-react'
import '@aws-amplify/ui-react/styles.css'
import type { ReactNode } from 'react'

import { ReminderApp } from '../App'

interface AuthenticatedAppProps {
  updateToast: ReactNode
}

export default function AuthenticatedApp({ updateToast }: AuthenticatedAppProps) {
  return (
    <>
      <Authenticator hideSignUp>
        {({ signOut, user }) => (
          <ReminderApp onSignOut={signOut} userLabel={user?.signInDetails?.loginId ?? user?.username} />
        )}
      </Authenticator>
      {updateToast}
    </>
  )
}
