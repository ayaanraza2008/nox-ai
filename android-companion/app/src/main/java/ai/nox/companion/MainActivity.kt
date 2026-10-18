package ai.nox.companion

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import android.widget.Toast
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

class MainActivity : Activity() {
    private val apiBase = "https://nox-ai-vcqx.onrender.com"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleLaunchRequest(intent)
    }

    override fun onResume() {
        super.onResume()
        getSharedPreferences("nox_pairing", MODE_PRIVATE).edit().putBoolean("activity_visible", true).apply()
    }

    override fun onPause() {
        getSharedPreferences("nox_pairing", MODE_PRIVATE).edit().putBoolean("activity_visible", false).apply()
        super.onPause()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleLaunchRequest(intent)
    }

    private fun handleLaunchRequest(request: Intent?) {
        val uri = request?.data
        val query = uri?.getQueryParameter("query")?.trim().orEmpty()
        if (uri?.scheme == "nox" && uri.host == "launch" && query.isNotBlank()) {
            showAppPicker(query)
        } else {
            showPairingHome()
        }
    }

    private fun showPairingHome() {
        val prefs = getSharedPreferences("nox_pairing", MODE_PRIVATE)
        val session = prefs.getString("session_id", null)
        val token = prefs.getString("device_token", null)
        if (!session.isNullOrBlank() && !token.isNullOrBlank()) {
            startPairingService()
            AlertDialog.Builder(this)
                .setTitle("NOX Device Pairing")
                .setMessage("This Android device is paired with NOX. The foreground service will keep reconnecting while enabled. Android may show a notification instead of opening apps automatically when NOX is in the background.")
                .setPositiveButton("Pair another session") { _, _ -> showPairCodeDialog() }
                .setNegativeButton("Close", null)
                .setNeutralButton("Disconnect") { _, _ -> disconnectPairing() }
                .show()
        } else {
            showPairCodeDialog()
        }
    }

    private fun showPairCodeDialog() {
        val input = EditText(this).apply {
            hint = "Six-digit code from NOX website"
            inputType = InputType.TYPE_CLASS_NUMBER
            filters = arrayOf(android.text.InputFilter.LengthFilter(6))
        }
        AlertDialog.Builder(this)
            .setTitle("Pair with NOX")
            .setMessage("Create a pairing code in the NOX website's Device Pairing panel, then enter it here within five minutes.")
            .setView(input)
            .setPositiveButton("Pair device") { _, _ ->
                val code = input.text.toString().trim()
                if (code.length != 6 || code.any { it !in '0'..'9' }) {
                    Toast.makeText(this, "Enter a valid six-digit pairing code.", Toast.LENGTH_LONG).show()
                } else {
                    joinPairing(code)
                }
            }
            .setNegativeButton("Cancel") { _, _ -> finish() }
            .setOnCancelListener { finish() }
            .show()
    }

    private fun joinPairing(code: String) {
        Thread {
            try {
                val body = JSONObject().put("code", code).put("device_name", "NOX Android Companion")
                val connection = URL("$apiBase/api/pairing/join").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 12000
                connection.readTimeout = 12000
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                val status = connection.responseCode
                val stream = if (status in 200..299) connection.inputStream else connection.errorStream
                val text = stream.bufferedReader().use { it.readText() }
                connection.disconnect()
                if (status !in 200..299) throw IllegalStateException("Pairing failed (HTTP $status). Create a fresh code and try again.")
                val result = JSONObject(text)
                getSharedPreferences("nox_pairing", MODE_PRIVATE).edit()
                    .putString("session_id", result.getString("session_id"))
                    .putString("device_id", result.getString("device_id"))
                    .putString("device_token", result.getString("device_token"))
                    .apply()
                runOnUiThread {
                    startPairingService()
                    Toast.makeText(this, "Paired with NOX. Keep the NOX notification enabled.", Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this, e.message ?: "Could not pair with NOX.", Toast.LENGTH_LONG).show() }
            }
        }.start()
    }

    private fun startPairingService() {
        val service = Intent(this, PairingService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(service) else startService(service)
    }

    private fun disconnectPairing() {
        stopService(Intent(this, PairingService::class.java))
        getSharedPreferences("nox_pairing", MODE_PRIVATE).edit().clear().apply()
        Toast.makeText(this, "This Android device has been disconnected from NOX.", Toast.LENGTH_LONG).show()
    }

    private data class LaunchableApp(val label: String, val packageName: String)

    @Suppress("DEPRECATION")
    private fun getLaunchableApps(): List<LaunchableApp> {
        val query = Intent(Intent.ACTION_MAIN, null).addCategory(Intent.CATEGORY_LAUNCHER)
        return packageManager.queryIntentActivities(query, PackageManager.MATCH_ALL)
            .mapNotNull { info ->
                val activityInfo = info.activityInfo ?: return@mapNotNull null
                if (activityInfo.packageName == packageName || !activityInfo.exported) return@mapNotNull null
                val label = info.loadLabel(packageManager)?.toString()?.trim().orEmpty()
                if (label.isBlank()) return@mapNotNull null
                LaunchableApp(label, activityInfo.packageName)
            }
            .distinctBy { it.packageName }
            .sortedBy { it.label.lowercase(Locale.ROOT) }
    }

    private fun normalize(value: String): String =
        java.text.Normalizer.normalize(value.lowercase(Locale.ROOT), java.text.Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9]"), "")

    private fun showAppPicker(query: String) {
        val allApps = getLaunchableApps()
        val q = normalize(query)
        val matching = if (q.isBlank()) emptyList() else allApps.filter {
            val name = normalize(it.label)
            name == q || name.contains(q) || q.contains(name)
        }
        if (matching.size == 1) {
            launch(matching.first())
            return
        }
        val options = (if (matching.isNotEmpty()) matching else allApps).take(150)
        if (options.isEmpty()) {
            Toast.makeText(this, "No launchable apps were found.", Toast.LENGTH_LONG).show()
            finish()
            return
        }
        val title = when {
            q.isBlank() -> "Choose an app to open"
            matching.isEmpty() -> "No match for \"$query\" — choose an app"
            else -> "More than one app matches \"$query\""
        }
        AlertDialog.Builder(this)
            .setTitle(title)
            .setItems(options.map { it.label }.toTypedArray()) { _, which -> launch(options[which]) }
            .setNegativeButton("Cancel") { _, _ -> finish() }
            .setOnCancelListener { finish() }
            .show()
    }

    private fun launch(app: LaunchableApp) {
        try {
            val launchIntent = packageManager.getLaunchIntentForPackage(app.packageName)
            if (launchIntent == null) {
                Toast.makeText(this, "Android did not provide a launch action for " + app.label + ".", Toast.LENGTH_LONG).show()
            } else {
                startActivity(launchIntent)
            }
        } catch (_: Exception) {
            Toast.makeText(this, "Could not open " + app.label + ".", Toast.LENGTH_LONG).show()
        } finally {
            finish()
        }
    }
}
