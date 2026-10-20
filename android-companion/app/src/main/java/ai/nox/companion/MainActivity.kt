package ai.nox.companion

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
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
            if (prefs.getBoolean("emergency_stopped", false)) {
                AlertDialog.Builder(this)
                    .setTitle("NOX Emergency Stop")
                    .setMessage("Background command polling and location service are stopped on this phone. Resume only when you are ready to allow paired NOX commands again.")
                    .setPositiveButton("Resume NOX") { _, _ ->
                        prefs.edit().putBoolean("emergency_stopped", false).apply()
                        startPairingService()
                        Toast.makeText(this, "NOX resumed by explicit action.", Toast.LENGTH_LONG).show()
                    }
                    .setNegativeButton("Disconnect paired control") { _, _ -> disconnectPairing() }
                    .setNeutralButton("Close") { _, _ -> finish() }
                    .show()
                return
            }
            startPairingService()
            AlertDialog.Builder(this)
                .setTitle("NOX Companion")
                .setMessage("Choose a pairing or location-sharing action. Location is only uploaded while you have granted Android permission and your NOX account has explicitly enabled a time-limited sharing session.")
                .setItems(arrayOf("Pair another session", "Location sharing options", "Disconnect paired control", "Close")) { _, which ->
                    when (which) {
                        0 -> showPairCodeDialog()
                        1 -> showLocationOptions()
                        2 -> disconnectPairing()
                    }
                }
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
            .setNeutralButton("Location sharing") { _, _ -> showLocationOptions() }
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

    private fun showLocationOptions() {
        val prefs = getSharedPreferences("nox_location", MODE_PRIVATE)
        val enrolled = !prefs.getString("device_token", null).isNullOrBlank()
        val choices = if (enrolled) arrayOf("Start / resume visible location service", "Stop location service", "Enroll another device", "Cancel")
            else arrayOf("Enroll this phone for location sharing", "Cancel")
        AlertDialog.Builder(this)
            .setTitle("NOX Location Sharing")
            .setMessage("Enrollment does not start sharing by itself. Your account must separately enable sharing, and Android location permission is required.")
            .setItems(choices) { _, which ->
                if (!enrolled) {
                    if (which == 0) showLocationCodeDialog()
                } else {
                    when (which) {
                        0 -> ensureLocationPermission("")
                        1 -> {
                            stopService(Intent(this, LocationService::class.java))
                            Toast.makeText(this, "Location service stopped on this phone.", Toast.LENGTH_LONG).show()
                        }
                        2 -> showLocationCodeDialog()
                    }
                }
            }
            .setNegativeButton("Close", null)
            .show()
    }

    private fun showLocationCodeDialog() {
        val input = EditText(this).apply {
            hint = "Six-digit location enrollment code"
            inputType = InputType.TYPE_CLASS_NUMBER
            filters = arrayOf(android.text.InputFilter.LengthFilter(6))
        }
        AlertDialog.Builder(this)
            .setTitle("Enroll this phone")
            .setMessage("In NOX web, sign in and open Features → Location Intelligence → Generate enrollment code. The code expires in five minutes and can be used once.")
            .setView(input)
            .setPositiveButton("Continue") { _, _ ->
                val code = input.text.toString().trim()
                if (code.length != 6 || code.any { it !in '0'..'9' }) {
                    Toast.makeText(this, "Enter the six-digit code.", Toast.LENGTH_LONG).show()
                } else {
                    ensureLocationPermission(code)
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun ensureLocationPermission(enrollmentCode: String) {
        val prefs = getSharedPreferences("nox_location", MODE_PRIVATE)
        prefs.edit().putString("pending_enrollment_code", enrollmentCode).apply()
        val fine = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (fine || coarse) {
            continueLocationSetup(enrollmentCode)
        } else {
            requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION), 7104)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != 7104) return
        val granted = grantResults.any { it == PackageManager.PERMISSION_GRANTED }
        val code = getSharedPreferences("nox_location", MODE_PRIVATE).getString("pending_enrollment_code", "").orEmpty()
        if (!granted) {
            Toast.makeText(this, "Location permission was not granted; no location will be collected.", Toast.LENGTH_LONG).show()
            return
        }
        continueLocationSetup(code)
    }

    private fun continueLocationSetup(enrollmentCode: String) {
        if (enrollmentCode.isBlank()) {
            showBackgroundLocationDisclosure { startLocationService() }
            return
        }
        Thread {
            try {
                val body = JSONObject()
                    .put("code", enrollmentCode)
                    .put("label", "NOX Android • " + Build.MODEL.take(40))
                    .put("platform", "android")
                val connection = URL("$apiBase/api/location/mobile/enroll").openConnection() as HttpURLConnection
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
                if (status !in 200..299) throw IllegalStateException("Enrollment failed (HTTP $status). Generate a new code and retry.")
                val result = JSONObject(text)
                getSharedPreferences("nox_location", MODE_PRIVATE).edit()
                    .putString("device_id", result.getString("device_id"))
                    .putString("device_token", result.getString("device_token"))
                    .remove("pending_enrollment_code")
                    .apply()
                runOnUiThread {
                    AlertDialog.Builder(this)
                        .setTitle("Location device enrolled")
                        .setMessage("This phone is registered but sharing remains OFF until you enable it in NOX web. If you start the visible service, GPS is requested only after your account enables sharing. Android may limit background updates; choose Allow all the time in app settings if available.")
                        .setPositiveButton("Start visible service") { _, _ -> showBackgroundLocationDisclosure { startLocationService() } }
                        .setNeutralButton("Background permission settings") { _, _ -> openAppSettings() }
                        .setNegativeButton("Not now", null)
                        .show()
                }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this, e.message ?: "Could not enroll this phone.", Toast.LENGTH_LONG).show() }
            }
        }.start()
    }

    private fun showBackgroundLocationDisclosure(onContinue: () -> Unit) {
        AlertDialog.Builder(this)
            .setTitle("Background location disclosure")
            .setMessage("NOX shows an ongoing notification while the location service runs. Coordinates are uploaded only while sharing is enabled and unexpired in your NOX account. You can stop the service here or revoke sharing in the web dashboard. Battery saver, network loss, GPS settings, or Android may delay updates.")
            .setPositiveButton("Continue") { _, _ -> onContinue() }
            .setNeutralButton("App permission settings") { _, _ -> openAppSettings() }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun openAppSettings() {
        startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, android.net.Uri.parse("package:$packageName")))
    }

    private fun startLocationService() {
        val service = Intent(this, LocationService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(service) else startService(service)
        Toast.makeText(this, "NOX location service started. Sharing still requires account-owner consent.", Toast.LENGTH_LONG).show()
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
