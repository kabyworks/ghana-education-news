package com.edulens360.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class FeedNotifyWorker extends Worker {
    public static final String CHANNEL_ID = "edulens_new_stories";
    public static final String PREFS = "edulens.notify";
    public static final String KEY_LAST_ID = "last_story_id";
    public static final String EXTRA_OPEN_URL = "open_url";
    private static final String NOTIFY_URL = "https://edulens360.com/data/notify.json";
    private static final int NOTIFICATION_ID = 3601;

    public FeedNotifyWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            ensureChannel(getApplicationContext());
            JSONObject payload = fetchNotify();
            if (payload == null || payload.isNull("latest")) {
                return Result.success();
            }
            JSONObject latest = payload.getJSONObject("latest");
            int storyId = latest.getInt("id");
            String title = latest.optString("title", "New education story");
            String path = latest.optString("path", "");
            SharedPreferences prefs = getApplicationContext()
                    .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            int lastId = prefs.getInt(KEY_LAST_ID, -1);
            if (lastId < 0) {
                prefs.edit().putInt(KEY_LAST_ID, storyId).apply();
                return Result.success();
            }
            if (storyId == lastId) {
                return Result.success();
            }
            prefs.edit().putInt(KEY_LAST_ID, storyId).apply();
            String url = path.isEmpty()
                    ? MainActivity.HOME
                    : MainActivity.HOME + path;
            showNotification(title, url);
            return Result.success();
        } catch (Exception ignored) {
            return Result.retry();
        }
    }

    private JSONObject fetchNotify() throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(NOTIFY_URL).openConnection();
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(15000);
        connection.setRequestProperty("Cache-Control", "no-cache");
        connection.setRequestProperty("Pragma", "no-cache");
        connection.setRequestProperty("Accept", "application/json");
        try {
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                return null;
            }
            StringBuilder body = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    body.append(line);
                }
            }
            return new JSONObject(body.toString());
        } finally {
            connection.disconnect();
        }
    }

    private void showNotification(String title, String openUrl) {
        Context context = getApplicationContext();
        Intent open = new Intent(context, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        open.putExtra(EXTRA_OPEN_URL, openUrl);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pending = PendingIntent.getActivity(context, storyHash(openUrl), open, flags);
        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle("Edulens360")
                .setContentText(title)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(title))
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .setAutoCancel(true)
                .setContentIntent(pending);
        NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, builder.build());
    }

    private static int storyHash(String openUrl) {
        return openUrl == null ? 0 : openUrl.hashCode();
    }

    public static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "New stories",
                NotificationManager.IMPORTANCE_DEFAULT);
        channel.setDescription("Alerts when Edulens360 publishes a newer education story.");
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager != null) {
            manager.createNotificationChannel(channel);
        }
    }
}
