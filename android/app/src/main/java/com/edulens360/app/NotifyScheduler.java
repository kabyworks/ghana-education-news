package com.edulens360.app;

import android.content.Context;

import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import java.util.concurrent.TimeUnit;

public final class NotifyScheduler {
    private static final String PERIODIC_NAME = "edulens-feed-notify";
    private static final String ONCE_NAME = "edulens-feed-notify-once";

    private NotifyScheduler() {
    }

    public static void ensureScheduled(Context context) {
        FeedNotifyWorker.ensureChannel(context);
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        PeriodicWorkRequest periodic = new PeriodicWorkRequest.Builder(
                FeedNotifyWorker.class, 30, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                periodic);
    }

    public static void checkNow(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        OneTimeWorkRequest once = new OneTimeWorkRequest.Builder(FeedNotifyWorker.class)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                ONCE_NAME,
                ExistingWorkPolicy.REPLACE,
                once);
    }
}
