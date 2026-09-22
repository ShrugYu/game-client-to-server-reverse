/*
 * 证书固定(Pinning)绕过 —— 仅用于自测/已授权目标
 * 用法: frida -U -f <package> -l frida_bypass_ssl.js
 *       frida -p <pid> -l frida_bypass_ssl.js
 */
Java.perform(function () {
    // 1) 通用 TrustManager
    try {
        var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
        var TrustManager = Java.registerClass({
            name: 'com.research.TrustAll',
            implements: [X509TrustManager],
            methods: {
                checkClientTrusted: function () {},
                checkServerTrusted: function () {},
                getAcceptedIssuers: function () { return []; }
            }
        });
        var SSLContext = Java.use('javax.net.ssl.SSLContext');
        var ctx = SSLContext.getInstance('TLS');
        ctx.init(null, [TrustManager.$new()], null);
        var SSLSocketFactory = Java.use('javax.net.ssl.SSLSocketFactory');
        var factory = ctx.getSocketFactory();
        SSLContext.init.overload('[Ljavax.net.ssl.KeyManager;',
            '[Ljavax.net.ssl.TrustManager;', 'java.security.SecureRandom')
            .implementation = function (k, t, s) {
                this.init(k, [TrustManager.$new()], s);
            };
        console.log('[+] TrustManager bypass installed');
    } catch (e) { console.log('[-] TrustManager: ' + e); }

    // 2) OkHttp CertificatePinner
    try {
        var Pinner = Java.use('okhttp3.CertificatePinner');
        Pinner.check.overload('java.lang.String', 'java.util.List').implementation = function () {
            console.log('[+] OkHttp pinner bypass: ' + arguments[0]);
        };
    } catch (e) { console.log('[-] OkHttp: ' + e); }

    // 3) 常见自研校验函数（按需替换类名/方法名）
    var hooks = [
        ['javax.net.ssl.HttpsURLConnection', 'setDefaultHostnameVerifier'],
        ['android.net.http.X509TrustManagerExtensions', 'checkServerTrusted']
    ];
    hooks.forEach(function (h) {
        try {
            var C = Java.use(h[0]);
            if (C[h[1]]) C[h[1]].implementation = function () { return true; };
            console.log('[+] hooked ' + h[0] + '.' + h[1]);
        } catch (e) {}
    });
});

// 4) Native 层（libssl / BoringSSL）
try {
    var SSL_CTX_set_verify = Module.findExportByName(null, 'SSL_CTX_set_verify');
    if (SSL_CTX_set_verify) {
        Interceptor.replace(SSL_CTX_set_verify, new NativeCallback(function () {
            return;
        }, 'void', ['pointer', 'int', 'pointer']));
        console.log('[+] native SSL_CTX_set_verify bypass');
    }
} catch (e) { console.log('[-] native: ' + e); }