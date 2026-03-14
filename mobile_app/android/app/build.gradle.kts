import java.io.FileInputStream
import java.util.Properties
import org.gradle.api.GradleException

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val keystoreProperties = Properties().apply {
    val propsFile = rootProject.file("key.properties")
    if (propsFile.exists()) {
        FileInputStream(propsFile).use { load(it) }
    }
}

val releaseStoreFilePath = keystoreProperties.getProperty("storeFile")?.trim().orEmpty()
val hasReleaseSigning =
    releaseStoreFilePath.isNotBlank() &&
        keystoreProperties.getProperty("storePassword")?.trim().isNullOrEmpty().not() &&
        keystoreProperties.getProperty("keyAlias")?.trim().isNullOrEmpty().not() &&
        keystoreProperties.getProperty("keyPassword")?.trim().isNullOrEmpty().not() &&
        rootProject.file(releaseStoreFilePath).exists()

android {
    namespace = "com.ustabul.mobile.ustabul_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        applicationId = "com.ustabul.mobile.ustabul_mobile"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (hasReleaseSigning) {
                storeFile = rootProject.file(releaseStoreFilePath)
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

flutter {
    source = "../.."
}

gradle.taskGraph.whenReady {
    val wantsReleaseBuild =
        allTasks.any { task ->
            val name = task.name.lowercase()
            name.contains("release") && (name.contains("bundle") || name.contains("assemble"))
        }

    if (wantsReleaseBuild && !hasReleaseSigning) {
        throw GradleException(
            "Android release signing eksik. " +
                "mobile_app/android/key.properties dosyasini ve release keystore'u ayarlamadan release build alinmaz."
        )
    }
}
