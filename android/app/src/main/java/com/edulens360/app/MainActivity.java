package com.edulens360.app;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Message;
import android.view.Gravity;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String HOME = "https://edulens360.com/";
    private FrameLayout root;
    private WebView webView;
    private int rendererCrashes;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        root = new FrameLayout(this);
        setContentView(root);
        paintSystemBars();
        nameTheTask();
        if (!attachWebView(savedInstanceState)) {
            showFallback();
        }
    }

    private boolean attachWebView(Bundle savedInstanceState) {
        try {
            WebView view = new WebView(this);
            WebSettings settings = view.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setUseWideViewPort(true);
            settings.setLoadWithOverviewMode(true);
            settings.setSupportMultipleWindows(true);
            settings.setJavaScriptCanOpenWindowsAutomatically(true);
            view.addJavascriptInterface(new ShareBridge(), "EdulensShare");
            view.setWebViewClient(new WebViewClient() {
                @Override
                public boolean shouldOverrideUrlLoading(WebView source, WebResourceRequest request) {
                    return false;
                }

                @Override
                public boolean onRenderProcessGone(WebView source, RenderProcessGoneDetail detail) {
                    rendererCrashes += 1;
                    detach(source);
                    if (rendererCrashes > 1) {
                        showFallback();
                    } else {
                        attachWebView(null);
                    }
                    return true;
                }
            });
            view.setWebChromeClient(new WebChromeClient() {
                @Override
                public boolean onCreateWindow(
                        WebView source, boolean isDialog, boolean isUserGesture, Message resultMsg) {
                    if (resultMsg == null || !(resultMsg.obj instanceof WebView.WebViewTransport)) {
                        return false;
                    }
                    WebView popup = new WebView(source.getContext());
                    popup.setWebViewClient(new WebViewClient() {
                        @Override
                        public boolean shouldOverrideUrlLoading(WebView popupView, WebResourceRequest request) {
                            if (webView != null && request != null && request.getUrl() != null) {
                                webView.loadUrl(request.getUrl().toString());
                            }
                            return true;
                        }
                    });
                    ((WebView.WebViewTransport) resultMsg.obj).setWebView(popup);
                    resultMsg.sendToTarget();
                    return true;
                }
            });
            root.addView(view, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT));
            webView = view;
            if (savedInstanceState != null) {
                view.restoreState(savedInstanceState);
            } else {
                view.loadUrl(HOME);
            }
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private void detach(WebView view) {
        if (view == null) {
            return;
        }
        if (webView == view) {
            webView = null;
        }
        ViewGroup parent = (ViewGroup) view.getParent();
        if (parent != null) {
            parent.removeView(view);
        }
        view.destroy();
    }

    private void showFallback() {
        if (webView != null) {
            detach(webView);
        }
        root.removeAllViews();
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setGravity(Gravity.CENTER);
        panel.setPadding(48, 48, 48, 48);
        TextView message = new TextView(this);
        message.setText("Edulens360 could not open its page in the app.");
        message.setGravity(Gravity.CENTER);
        Button open = new Button(this);
        open.setText("Open in the browser");
        open.setOnClickListener(ignored -> startActivity(
                new Intent(Intent.ACTION_VIEW, Uri.parse(HOME))));
        panel.addView(message);
        panel.addView(open);
        root.addView(panel, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private final class ShareBridge {
        @JavascriptInterface
        public void share(String title, String text, String url) {
            String subject = title == null || title.isEmpty() ? "Edulens360" : title;
            String body = text == null ? "" : text;
            if (url != null && !url.isEmpty()) {
                body = body.isEmpty() ? url : body + "\n" + url;
            }
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("text/plain");
            send.putExtra(Intent.EXTRA_SUBJECT, subject);
            send.putExtra(Intent.EXTRA_TEXT, body);
            startActivity(Intent.createChooser(send, "Share"));
        }
    }

    private void paintSystemBars() {
        Window window = getWindow();
        int green = Color.parseColor("#1C3D2E");
        window.setStatusBarColor(green);
        window.setNavigationBarColor(green);
    }

    private void nameTheTask() {
        try {
            int green = Color.parseColor("#1C3D2E");
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                setTaskDescription(new ActivityManager.TaskDescription.Builder()
                        .setLabel("Edulens360")
                        .setPrimaryColor(green)
                        .build());
            } else {
                setTaskDescription(new ActivityManager.TaskDescription("Edulens360", null, green));
            }
        } catch (Throwable ignored) {
            // Recents can keep the manifest label if this phone rejects the call.
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (webView != null) {
            webView.saveState(outState);
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }
}
