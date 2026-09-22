package com.rev.redirect;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.HashMap;
import java.util.Map;

/**
 * xposed-redirect —— 把游戏客户端的服务器，换成我们自建的服务端（Java/OkHttp 客户端）。
 *
 * 配置：/data/local/tmp/redirect_config.txt（adb push 进去即可，改完重启游戏生效）
 *  行格式：  原host=我们的host或IP
 *  可选：    PORT=新端口     （全局端口覆盖，不需要就不写）
 *
 * 覆盖范围：
 *  - okhttp3.Request$Builder.url(String)        （OkHttp 高层）
 *  - java.net.URL(String)                        （HttpURLConnection 等）
 *  - 若要 native/il2cpp 客户端 → 用 templates/frida-redirect.js（本模块管不到 native）。
 *
 * 说明：这是 skill「第三步 重定向」的落地手法之一；注入可能触发客户端保护。
 */
public class MainHook implements IXposedHookLoadPackage {

    private static final Map<String, String> HOST_MAP = new HashMap<>();
    private static int NEW_PORT = 0;
    private static boolean loaded = false;

    // 只对下面这些包名生效（留空 = 全部生效；建议按目标包名收紧）
    private static final String[] TARGET_PKGS = {
            // "com.example.game",
    };

    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam lp) {
        if (TARGET_PKGS.length > 0) {
            boolean hit = false;
            for (String p : TARGET_PKGS) if (p.equals(lp.packageName)) { hit = true; break; }
            if (!hit) return;
        }
        loadConfig();
        XposedBridge.log("[rdr] attach " + lp.packageName + " rules=" + HOST_MAP);

        hookOkHttp(lp.classLoader);
        hookJavaUrl(lp.classLoader);
    }

    /** 读配置（懒加载一次） */
    private static synchronized void loadConfig() {
        if (loaded) return;
        loaded = true;
        try (BufferedReader br = new BufferedReader(new FileReader("/data/local/tmp/redirect_config.txt"))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                if (line.startsWith("PORT=")) { NEW_PORT = Integer.parseInt(line.substring(5).trim()); continue; }
                int eq = line.indexOf('=');
                if (eq > 0) HOST_MAP.put(line.substring(0, eq).trim(), line.substring(eq + 1).trim());
            }
        } catch (Throwable t) {
            XposedBridge.log("[rdr] config read fail: " + t);
        }
    }

    /** 把 URL 里的原 host（和端口）替换成我们的 */
    private static String rewrite(String url) {
        if (url == null) return null;
        String out = url;
        for (Map.Entry<String, String> e : HOST_MAP.entrySet()) {
            String from = e.getKey(), to = e.getValue();
            if (out.contains(from)) out = out.replace(from, to);
        }
        if (NEW_PORT > 0) {
            // 简化处理：只改 http(s)://host:port 形式里的端口
            out = out.replaceAll("(?<=://[^/:]+):\\d+", ":" + NEW_PORT);
        }
        return out;
    }

    private void hookOkHttp(ClassLoader cl) {
        try {
            XposedHelpers.findAndHookMethod("okhttp3.Request$Builder", cl, "url",
                    String.class, new XC_MethodHook() {
                        @Override protected void beforeHookedMethod(MethodHookParam p) {
                            String u = (String) p.args[0], r = rewrite(u);
                            if (r != null && !r.equals(u)) { XposedBridge.log("[rdr] okhttp " + u + " -> " + r); p.args[0] = r; }
                        }
                    });
            XposedBridge.log("[rdr] okhttp hooked");
        } catch (Throwable t) {
            XposedBridge.log("[rdr] okhttp not present: " + t);
        }
    }

    private void hookJavaUrl(ClassLoader cl) {
        try {
            XposedHelpers.findAndHookConstructor("java.net.URL", cl, String.class, new XC_MethodHook() {
                @Override protected void beforeHookedMethod(MethodHookParam p) {
                    String u = (String) p.args[0], r = rewrite(u);
                    if (r != null && !r.equals(u)) p.args[0] = r;
                }
            });
            XposedBridge.log("[rdr] java.net.URL hooked");
        } catch (Throwable t) {
            XposedBridge.log("[rdr] URL hook fail: " + t);
        }
    }
}