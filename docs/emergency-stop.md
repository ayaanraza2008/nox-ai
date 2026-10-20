# NOX AI Emergency Stop — implementation scope

## Hosted dashboard and backend

The dashboard exposes a persistent emergency-stop control through \`/api/emergency-stop\` and a separate explicit \`POST /api/emergency-stop/resume\` action. State is scoped to the resolved NOX account/browser owner to prevent one visitor from stopping unrelated users on a shared hosted service.

The latch is persisted in the same task database used by \`TaskManager\`. New queued research tasks, agent-swarm jobs, safe-tool executions, and remote-browser commands/confirmations are blocked while the latch is set. The stop endpoint latches the state before cancelling queued/running task workers, agent-swarm jobs, and the current browser session. Cancelled work is not automatically requeued. Status polling reports any task/browser work still observed as active, and the UI only offers Resume when the API reports the stop has completed.

Use a configured durable PostgreSQL database for hosted persistence. SQLite fallback uses \`NOX_TASK_DB\`; on hosts with ephemeral filesystems, that file may not survive a redeploy. The API reports this limitation instead of claiming cross-deploy durability.

## Windows local companion

The local companion has an independent fail-closed stop latch. It blocks mutating local API requests with HTTP 423 while stopped and pauses its paired command relay. On Windows, optional notification-area controls are provided through pystray/Pillow when installed. Resume is always a separate user action. The local latch is stored in the current user's Local AppData by default.

The hosted dashboard cannot reliably reach the local HTTP companion from an HTTPS page in every browser because mixed-content and local-network protections vary. Consequently, the dashboard and local companion latches are not yet a distributed atomic stop controller; use the tray's stop control to stop the local companion and the dashboard control to stop hosted tasks. This is explicitly surfaced in the companion README.

## Platform limitations

- **Android:** the existing companion foreground service and location service are OS-managed. This change does not add a remote emergency-stop command to every Android service or promise unrestricted background execution. A local stop in Android still needs a supported notification/activity action and service-specific cancellation wiring.
- **iOS:** no unrestricted always-on agent or always-listening microphone is claimed. Background work must use supported system APIs and user-approved actions.
- **Browser:** hosted Playwright actions for the current browser session are stopped through the existing browser adapter. Browser extensions and other browser profiles are not controlled by this server process.
- **External side effects:** an already-sent message, completed file transfer, or request accepted by a remote service cannot necessarily be recalled. NOX reports cancellation/cleanup state and does not claim such side effects were undone.
- **Process safety:** no unrelated OS processes are killed. The current backend task queue and agent swarm use cooperative asyncio cancellation; operations that ignore cancellation can remain pending and must not be presented as fully stopped.

## Verification

Run the repository CI workflow. Unit tests cover persisted latch behavior, rejection of new work while stopped, explicit resume, task-store recreation, cancellation of a running async task, and fail-closed behavior when the local latch file is corrupt. Physical device and cross-process integration tests are still required before claiming end-to-end stop coverage for USB/Wi-Fi/Bluetooth, Android, iOS, or arbitrary browser extensions.
