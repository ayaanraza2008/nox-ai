package ai.nox.companion

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import java.text.Normalizer
import java.util.Locale

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleLaunchRequest(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleLaunchRequest(intent)
    }

    private fun handleLaunchRequest(request: Intent?) {
        showAppPicker(request?.data?.getQueryParameter("query")?.trim().orEmpty())
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
        Normalizer.normalize(value.lowercase(Locale.ROOT), Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9]"), "")

    private fun showAppPicker(query: String) {
        val allApps = getLaunchableApps()
        val q = normalize(query)
        val matching = if (q.isBlank()) emptyList() else allApps.filter {
            val name = normalize(it.label)
            name == q || name.contains(q) || q.contains(name)
        }

        // A clear, unique match launches directly. Ambiguous or unknown commands show a chooser.
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
