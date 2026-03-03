# UstaBul Mobile (iOS + Android)

Bu klasor artik native `android/` ve `ios/` proje dosyalari ile hazirdir.
Bu uygulama bir `WebView shell` olarak calisir ve website'i mobil uygulama icinde acar.

## Hemen calistir

```bash
cd mobile_app
flutter pub get
flutter run --dart-define=SITE_URL=https://your-domain.com
```

Yerelde Android emulator icin varsayilan backend adresi:

`http://10.0.2.2:8000`

## Build (release)

Android AAB:

```bash
flutter build appbundle --release --dart-define=SITE_URL=https://your-domain.com
```

iOS release (unsigned, macOS):

```bash
flutter build ios --release --no-codesign --dart-define=SITE_URL=https://your-domain.com
```

## Android signing

1. `mobile_app/android/key.properties.example` dosyasini `key.properties` olarak kopyala.
2. Degerleri kendi upload keystore bilgilerinle doldur.
3. Keystore dosyasini `mobile_app/android/keystore/release-keystore.jks` konumuna koy.

Not: `key.properties` ve keystore dosyalari `.gitignore` ile dislanmistir.

## Push notification (FCM + APNs)

Android:

- `mobile_app/android/app/google-services.json`

iOS:

- `mobile_app/ios/Runner/GoogleService-Info.plist`
- Apple Developer hesabinda APNs key olusturup Firebase Console'a bagla.

Uygulama token kaydi endpoint'i:

- `POST /mobile/api/v1/devices/register/`

## GitHub Actions

Repo icine iki workflow eklendi:

- `.github/workflows/mobile-android-release.yml`
- `.github/workflows/mobile-ios-build.yml`

Opsiyonel secret'lar:

- `MOBILE_SITE_URL`
- `ANDROID_GOOGLE_SERVICES_JSON_BASE64`
- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEY_PROPERTIES_BASE64`
- `IOS_GOOGLE_SERVICE_INFO_PLIST_BASE64`

`mobile-v*` tag'i ile push yapinca build artifact uretilir.

## Cihaz ici davranis

- Uygulama acilisinda `SITE_URL` adresi yuklenir.
- Back tusu WebView gecmisinde geri gider.
- Site icindeki giris/oturum akislari aynen web ile calisir.
