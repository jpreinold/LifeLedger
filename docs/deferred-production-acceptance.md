# Deferred production acceptance

The following Phase 13 production acceptance remains unverified in this workspace. Phase 14 did not use unavailable credentials as a development blocker and does not claim these paths passed.

| Acceptance item | Implementation state | Why deferred | Risk | Later procedure | Phase 14 impact |
| --- | --- | --- | --- | --- | --- |
| Authenticated production E2E | Dedicated-account Playwright workflow exists. | No dedicated production credentials were used here. | Stale configuration or auth-only regression could remain. | Run the manual production workflow with the dedicated account and retain artifacts. | Capture routes/UI add authenticated paths to include in a later run. |
| Real GuardDuty document scan | S3 quarantine/finalizer and malware controls are implemented. | No real production upload/scan acceptance ran here. | Provider/event configuration could differ from local mocks. | Upload the benign fixture, observe GuardDuty and promotion, then clean it up. | No Phase 14 document capture was added. |
| Account export rehearsal | Export inventory and encrypted artifact path exist. | No production export was requested. | A permission or size issue may appear only live. | Export a dedicated account, verify archive contents/expiry, delete artifact. | Captures, proposals, clarifications, usage, and AI settings are newly registered. |
| Account deletion rehearsal | Resumable deletion and zero verification exist. | No production identity/data was authorized for deletion. | A new store or external cleanup could leave residue. | Populate a dedicated account, delete it, verify every inventory store and identity. | The assistant table is a new required zero-count store. |
| Reconciliation schedule observation | Scheduled retry/deep sweep and alarms are declared. | No live schedule window was observed. | IAM, metrics, or event configuration could be wrong. | Seed a safe repairable issue, observe detection/retry/metric/alarm and resolution. | Capture/proposal stuck and partial-state detectors are newly included. |
| Alarm verification | CloudWatch alarms exist from Phase 13. | No alarm was intentionally tripped. | Notifications could be misrouted. | Execute the operations runbook in a maintenance window. | Phase 14 safe metrics/alarm expansion should be verified with this work. |
