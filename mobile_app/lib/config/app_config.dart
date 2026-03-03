import 'package:flutter/foundation.dart';

class AppConfig {
  static const _siteUrlFromEnv = String.fromEnvironment('SITE_URL', defaultValue: '');
  static const _apiBaseUrlFromEnv = String.fromEnvironment('API_BASE_URL', defaultValue: '');

  // Override with:
  // flutter run --dart-define=SITE_URL=https://your-domain.com
  // Legacy fallback: --dart-define=API_BASE_URL=https://your-domain.com
  static String get siteUrl {
    if (_siteUrlFromEnv.isNotEmpty) {
      return _siteUrlFromEnv;
    }
    if (_apiBaseUrlFromEnv.isNotEmpty) {
      return _apiBaseUrlFromEnv;
    }

    if (kIsWeb) {
      return 'http://127.0.0.1:8000';
    }

    switch (defaultTargetPlatform) {
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
        return 'http://127.0.0.1:8000';
      default:
        return 'http://10.0.2.2:8000';
    }
  }

  static String get apiBaseUrl {
    if (_apiBaseUrlFromEnv.isNotEmpty) {
      return _apiBaseUrlFromEnv;
    }
    return siteUrl;
  }
}
