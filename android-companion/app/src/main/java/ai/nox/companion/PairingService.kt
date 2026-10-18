package ai.nox.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.IBinder
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.Normalizer
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

class PairingService : Service() {
    private val running = AtomicBoolean(false)
    private var worker: Thread? = null
    private val apiBase = "https://nox-ai-vcqx.onrender.com"
    private val channelId = "nox_pairing"

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(7102, notification("NOX paired control is running", null))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (running.compareAndSet(false, true)) {
            worker = Thread({ pollLoop() }, "nox-pairing-poll").also { it.isDaemon = true; it.start() }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        running.set(false)
        worker?.interrupt()
        super.onDestroy()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "NOX paired device control", NotificationManager.IMPORTANCE_DEFAULT)
            channel.description = "Shows actions received from your paired NOX devices"
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun notification(message: String, pendingIntent: PendingIntent?): Notification {
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(this, channelId) else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        builder.setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("NOX AI")
            .setContentText(message)
            .setOngoing(pendingIntent == null)
        if (pendingIntent != null) builder.setContentIntent(pendingIntent).setAutoCancel(true)
        return builder.build()
    }

    private fun api(path: String, method: String = "GET", body: JSONObject? = null, token: String): JSONObject {
        val connection = URL(apiBase + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 12000
        connection.readTimeout = 12000
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("X-NOX-Device-Token", token)
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val response = stream.bufferedReader().use { it.readText() }
        connection.disconnect()
        if (code !in 200..299) throw IllegalStateException("NOX relay returned HTTP $code")
        return JSONObject(response)
    }

    private fun pollLoop() {
        while (running.get()) {
            try {
                val prefs = getSharedPreferences("nox_pairing", MODE_PRIVATE)
                val sessionId = prefs.getString("session_id", null)
                val token = prefs.getString("device_token", null)
                if (!sessionId.isNullOrBlank() && !token.isNullOrBlank()) {
                    val sid = URLEncoder.encode(sessionId, "UTF-8")
                    api("/api/pairing/status?session_id=$sid", token = token)
                    val item = api("/api/pairing/commands/next?session_id=$sid", token = token).optJSONObject("command")
                    if (item != null) {
                        val commandId = item.optString("command_id")
                        val command = item.optString("command")
                        val result = runCommand(command).first
                        val resultQuery = URLEncoder.encode(result.toString(), "UTF-8")
                        val resultPath = "/api/pairing/commands/" + URLEncoder.encode(commandId, "UTF-8") + "/result?result=" + resultQuery
                        api(resultPath, "POST", token = token)
                    }
                }
            } catch (_: Exception) {
                // Keep credentials and retry after temporary network failure.
            }
            try { Thread.sleep(5000) } catch (_: InterruptedException) { break }
        }
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value.lowercase(Locale.ROOT), Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9]"), "")

    private fun runCommand(raw: String): Pair<JSONObject, Intent?> {
        val command = raw.trim()
        if (command.isBlank() || command.length > 1000) return JSONObject().put("status", "rejected").put("message", "Invalid command.") to null
        val install = Regex("^(?:install|download and install)\\s+(.+)$", RegexOption.IGNORE_CASE).find(command)
        val search = Regex("^(?:please\\s+)?(?:search(?:\\s+the\\s+web)?(?:\\s+for)?|google par|google|find online|internet par)\\s+(.+?)(?:\\s+(?:on|using)\\s+(google|youtube|bing))?$", RegexOption.IGNORE_CASE).find(command)
        val intent: Intent?
        if (install != null) {
            val appName = install.groupValues[1].trim()
            intent = if (appName.isBlank()) null else Intent(
                Intent.ACTION_VIEW,
                Uri.parse("https://play.google.com/store/search?q=" + Uri.encode(appName) + "&c=apps")
            )
        } else if (search != null) {
            val query = search.groupValues[1].replace(Regex("^(?:par|for)\\s+", RegexOption.IGNORE_CASE), "").replace(Regex("\\s+(?:search\\s*)?(?:karo|kar do|please)$", RegexOption.IGNORE_CASE), "").trim()
            val engine = search.groupValues[2].ifBlank { "google" }.lowercase(Locale.ROOT)
            val base = when (engine) {
                "youtube" -> "https://www.youtube.com/results?search_query="
                "bing" -> "https://www.bing.com/search?q="
                else -> "https://www.google.com/search?q="
            }
            intent = Intent(Intent.ACTION_VIEW, Uri.parse(base + Uri.encode(query)))
        } else {
            val target = command.replace(Regex("^(?:please\\s+)?(?:open|launch|start|visit|go to|khol|kholo|khul|chalao|chalu karo|खोलो|खोल|चलाओ)\\s+", RegexOption.IGNORE_CASE), "")
                .replace(Regex("\\s+(?:please|khol|kholo|open|launch|खोलो|खोल)$", RegexOption.IGNORE_CASE), "").trim()
                .replace(Regex("^(?:app|application)\\s+", RegexOption.IGNORE_CASE), "").trim()
            intent = findAppIntent(target) ?: knownWebsiteIntent(target)
        }
        if (intent == null) return JSONObject().put("status", "not_found").put("message", "No matching launchable app or supported website for: $command") to null
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val visible = getSharedPreferences("nox_pairing", MODE_PRIVATE).getBoolean("activity_visible", false)
        return try {
            if (visible) {
                startActivity(intent)
                JSONObject().put("status", "launch_requested").put("message", if (install != null) "Opened Google Play search. Choose the official app and complete installation in Android." else "Opened from paired NOX command.")
            } else {
                val pending = PendingIntent.getActivity(this, command.hashCode(), intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or if (Build.VERSION.SDK_INT >= 23) PendingIntent.FLAG_IMMUTABLE else 0)
                getSystemService(NotificationManager::class.java).notify(command.hashCode(), notification("Tap to run: $command", pending))
                JSONObject().put("status", "notification_sent").put("message", if (install != null) "Tap the notification to open Google Play search; Android requires you to choose and install the app." else "Tap the notification to open this app while NOX is in the background.")
            }
        } catch (e: Exception) {
            JSONObject().put("status", "error").put("message", e.message ?: "Android could not launch the requested target.")
        } to intent
    }

    @Suppress("DEPRECATION")
    private fun findAppIntent(target: String): Intent? {
        val q = normalize(target)
        if (q.isBlank()) return null
        val launcher = Intent(Intent.ACTION_MAIN, null).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = packageManager.queryIntentActivities(launcher, PackageManager.MATCH_ALL).mapNotNull { info ->
            val activity = info.activityInfo ?: return@mapNotNull null
            if (activity.packageName == packageName || !activity.exported) return@mapNotNull null
            val label = info.loadLabel(packageManager)?.toString()?.trim().orEmpty()
            if (label.isBlank()) null else Triple(label, activity.packageName, normalize(label))
        }.distinctBy { it.second }
        val aliases = mapOf(
            "vscode" to "visualstudiocode", "code" to "visualstudiocode",
            "chrome" to "googlechrome", "yt" to "youtube", "wa" to "whatsapp"
        )
        val query = aliases[q] ?: q
        val matches = apps.filter { it.third == query || it.third.startsWith(query) || query.startsWith(it.third) }
        // A single command should not show a chooser for routine launches: exact label first,
        // otherwise select the closest normalized label, with a stable alphabetical fallback.
        val selected = matches.firstOrNull { it.third == query }
            ?: matches.minByOrNull { candidate ->
                kotlin.math.abs(candidate.third.length - query.length)
            }
        return selected?.let { packageManager.getLaunchIntentForPackage(it.second) }
    }

    private fun knownWebsiteIntent(target: String): Intent? {
        val url = when (target.lowercase(Locale.ROOT)) {
            "youtube" -> "https://www.youtube.com/"
            "google" -> "https://www.google.com/"
            "gmail" -> "https://mail.google.com/"
            "github" -> "https://github.com/"
            "instagram" -> "https://www.instagram.com/"
            "whatsapp", "whatsapp web" -> "https://web.whatsapp.com/"
            "facebook" -> "https://www.facebook.com/"
            "chatgpt" -> "https://chatgpt.com/"
            "netflix" -> "https://www.netflix.com/"
            "amazon" -> "https://www.amazon.in/"
            "prime video", "amazon prime" -> "https://www.primevideo.com/"
            "spotify" -> "https://open.spotify.com/"
            "discord" -> "https://discord.com/app"
            "telegram" -> "https://web.telegram.org/"
            "pinterest" -> "https://www.pinterest.com/"
            "stackoverflow" -> "https://stackoverflow.com/"
            "google docs" -> "https://docs.google.com/"
            "google drive" -> "https://drive.google.com/"
            "google maps" -> "https://maps.google.com/"
            "google photos" -> "https://photos.google.com/"
            "google meet" -> "https://meet.google.com/"
            "outlook" -> "https://outlook.live.com/"
            "twitter", "x" -> "https://x.com/"
            "threads" -> "https://www.threads.net/"
            "twitch" -> "https://www.twitch.tv/"
            "play store", "google play" -> "https://play.google.com/store"
            else -> if (target.matches(Regex("^https?://[^\\s]+$", RegexOption.IGNORE_CASE))) target else null
        } ?: return null
        return Intent(Intent.ACTION_VIEW, Uri.parse(url))
    }
}
