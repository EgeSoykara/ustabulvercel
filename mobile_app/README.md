# UstaBul Mobile (iOS + Android)

Bu klasor artik native `android/` ve `ios/` proje dosyalari ile hazirdir.
Bu uygulama bir `WebView shell` olarak calisir ve website'i mobil uygulama icinde acar.

## Hemen calistir

```bash
cd mobile_app
flutter pub get
flutter run --dart-define=SITE_URL=https://ustabul.onrender.com
```

Varsayilan adres:

`https://ustabul.onrender.com`

Yerelde Android emulator ile calismak istersen:

`flutter run --dart-define=SITE_URL=http://10.0.2.2:8000`

Yerelde iOS simulator ile calismak istersen:

`flutter run --dart-define=SITE_URL=http://127.0.0.1:8000`

Repo kokunden hazir script'ler:

- Canli site ile Android emulator: `powershell -ExecutionPolicy Bypass -File .\scripts\run_mobile_android_live.ps1`
- Local backend + Android emulator tek komut: `powershell -ExecutionPolicy Bypass -File .\scripts\run_local_backend_and_mobile_android.ps1`

## Build (release)

Android AAB:

```bash
flutter build appbundle --release --dart-define=SITE_URL=https://ustabul.onrender.com
```

Repo kokunden release script:

`powershell -ExecutionPolicy Bypass -File .\scripts\build_mobile_android_release.ps1`

iOS release (unsigned, macOS):

```bash
flutter build ios --release --no-codesign --dart-define=SITE_URL=https://ustabul.onrender.com
```

## Android signing

1. `mobile_app/android/key.properties.example` dosyasini `key.properties` olarak kopyala.
2. Degerleri kendi upload keystore bilgilerinle doldur.
3. Keystore dosyasini `mobile_app/android/keystore/release-keystore.jks` konumuna koy.
4. Ardindan repo kokunden `powershell -ExecutionPolicy Bypass -File .\scripts\build_mobile_android_release.ps1` komutunu calistir.

Not: `key.properties` ve keystore dosyalari `.gitignore` ile dislanmistir.
Release build artik signing eksikse bilincli olarak fail eder; debug signing fallback kaldirildi.

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

## App icon

Mobil app iconu icin ana kaynak:

`static/pwa/favicon-dark.svg`

Bu kaynaktan `mobile_app/assets/branding/app_icon.png` uretilip Android ve iOS icon setleri guncellenir.

Tek komut:

`powershell -ExecutionPolicy Bypass -File .\scripts\set_mobile_icon_from_favicon_dark.ps1`

Istersen yine dogrudan `mobile_app/assets/branding/app_icon.png` dosyasini 1024x1024 PNG ile degistirip su komutu da kullanabilirsin:

`powershell -ExecutionPolicy Bypass -File .\scripts\regenerate_mobile_app_icon.ps1`

Launch/splash assetlerini de ayni branding ile yenilemek istersen:

`powershell -ExecutionPolicy Bypass -File .\scripts\regenerate_mobile_launch_assets.ps1`

## Cihaz ici davranis

- Uygulama acilisinda `SITE_URL` adresi yuklenir.
- Back tusu WebView gecmisinde geri gider.
- `tel:`, `mailto:`, WhatsApp ve harici domain linkleri cihazdaki ilgili uygulamada acilir.
- Alt hizli islem cubugunda geri, ana sayfa, yenile ve mevcut sayfayi tarayicida ac secenekleri vardir.
- Site icindeki giris/oturum akislari aynen web ile calisir.
