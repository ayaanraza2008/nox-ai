package ai.nox.companion

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.util.concurrent.atomic.AtomicBoolean

class LocationService : Service(), LocationListener {
    private val apiBase = "https://nox-ai-vcqx.onrender.com"
    private val channelId = "nox_location_sharing"
    private val running = AtomicBoolean(false)
    private lateinit var locationManager: LocationManager
    private val handler = Handler(Looper.getMainLooper())
    private var sharingActive = false
    private var lastUploadAt = 0L

    private val statusPoll = object : Runnable {
        override fun run() {
            if (!running.get()) return
            Thread {
                try {
                    val token = getSharedPreferences("nox_location", MODE_PRIVATE).getString("device_token", null)
                        ?: throw ApiFailure(401, "Device is not enrolled")
                    val status = api("/api/location/mobile/status", "GET", null, token)
                    val active = status.optBoolean("sharing_enabled", false)
                    handler.post {
                        if (!running.get()) return@post
                        if (active) {
                            startLocationUpdates()
                            updateNotification("Location sharing enabled by account owner")
                        } else {
                            stopLocationUpdates()
                            updateNotification("Paused — waiting for owner consent in NOX")
                        }
                    }
                } catch (e: ApiFailure) {
                    if (e.status == 401) {
                        handler.post {
                            stopLocationUpdates()
                            updateNotification("Device access revoked — service stopped")
                            stopSelf()
                        }
                    } else {
                        handler.post { updateNotification("Offline — retrying connection") }
                    }
                } catch (_: Exception) {
                    handler.post { updateNotification("Offline — retrying connection") }
                } finally {
                    handler.postDelayed(this, 30_000L)
                }
            }.start()
        }
    }

    override fun onCreate() {
        super.onCreate()
        locationManager = getSystemService(LOCATION_SERVICE) as LocationManager
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(7103, notification("Checking NOX sharing permission"))
        if (running.compareAndSet(false, true)) handler.post(statusPoll)
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        running.set(false)
        handler.removeCallbacksAndMessages(null)
        stopLocationUpdates()
        super.onDestroy()
    }

    @Suppress("MissingPermission")
    private fun startLocationUpdates() {
        if (sharingActive) return
        val fine = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (!fine && !coarse) {
            updateNotification("Location permission missing — open NOX companion")
            return
        }
        sharingActive = true
        try {
            if (fine && locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 60_000L, 25f, this, Looper.getMainLooper())
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 60_000L, 50f, this, Looper.getMainLooper())
            }
            val last = listOfNotNull(
                runCatching { locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER) }.getOrNull(),
                runCatching { locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER) }.getOrNull()
            ).maxByOrNull { it.time }
            if (last != null) onLocationChanged(last)
        } catch (_: SecurityException) {
            sharingActive = false
            updateNotification("Location permission unavailable")
        } catch (_: Exception) {
            updateNotification("GPS unavailable — waiting for a location fix")
        }
    }

    private fun stopLocationUpdates() {
        sharingActive = false
        runCatching { locationManager.removeUpdates(this) }
    }

    override fun onLocationChanged(location: Location) {
        if (!sharingActive) return
        val now = System.currentTimeMillis()
        if (now - lastUploadAt < 5_000L) return
        lastUploadAt = now
        val token = getSharedPreferences("nox_location", MODE_PRIVATE).getString("device_token", null) ?: return
        val body = JSONObject()
            .put("latitude", location.latitude)
            .put("longitude", location.longitude)
            .put("accuracy_m", location.accuracy.toDouble())
            .put("captured_at", Instant.ofEpochMilli(location.time).toString())
        Thread {
            try {
                api("/api/location/update", "POST", body, token)
                handler.post { updateNotification("Sharing location • accuracy ±" + location.accuracy.toInt() + " m") }
            } catch (e: ApiFailure) {
                if (e.status == 403) {
                    handler.post {
                        stopLocationUpdates()
                        updateNotification("Paused — owner consent is inactive")
                    }
                } else {
                    handler.post { updateNotification("Offline — last update may be stale") }
                }
            } catch (_: Exception) {
                handler.post { updateNotification("Offline — last update may be stale") }
            }
        }.start()
    }

    private data class ApiFailure(val status: Int, override val message: String) : Exception(message)

    private fun api(path: String, method: String, body: JSONObject?, token: String): JSONObject {
        val connection = URL(apiBase + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 10_000
        connection.readTimeout = 12_000
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("X-NOX-Location-Token", token)
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        connection.disconnect()
        if (code !in 200..299) throw ApiFailure(code, "NOX location API returned HTTP $code")
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "NOX location sharing", NotificationManager.IMPORTANCE_LOW)
            channel.description = "Visible status for consent-based NOX location sharing"
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun notification(message: String): Notification {
        val open = PendingIntent.getActivity(this, 7103, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or if (Build.VERSION.SDK_INT >= 23) PendingIntent.FLAG_IMMUTABLE else 0)
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        return builder.setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentTitle("NOX AI • Location sharing")
            .setContentText(message)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(message: String) {
        getSystemService(NotificationManager::class.java).notify(7103, notification(message))
    }
}
