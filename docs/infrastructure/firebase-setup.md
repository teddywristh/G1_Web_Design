# Firebase setup

1. Create separate projects: `legal-ai-dev` and `legal-ai-prod`.
2. Enable Authentication, Firestore and Storage in each project.
3. Copy `.firebaserc.example` to `.firebaserc` and select the target project.
4. Deploy rules/indexes with `firebase deploy --only firestore,storage`.
5. Install Firebase CLI and run `firebase emulators:start` for local work.
6. In production use Cloud Run Application Default Credentials or Workload
   Identity. Never commit a service-account JSON file.

Configure the API from `apps/api/.env.example`; frontend code must never receive
Admin credentials.
