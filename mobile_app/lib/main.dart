import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'config/brand_config.dart';
import 'screens/site_shell_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
  ]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: BrandConfig.background,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: BrandConfig.background,
    systemNavigationBarIconBrightness: Brightness.light,
    systemNavigationBarDividerColor: BrandConfig.background,
  ));
  runApp(const UstaBulMobileApp());
}

class UstaBulMobileApp extends StatelessWidget {
  const UstaBulMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'UstaBul',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: BrandConfig.background,
        colorScheme: const ColorScheme.dark(
          primary: BrandConfig.accent,
          secondary: BrandConfig.accent,
          surface: BrandConfig.surface,
        ),
        progressIndicatorTheme: const ProgressIndicatorThemeData(
          color: BrandConfig.accent,
          linearTrackColor: Color(0x3329B6D1),
        ),
      ),
      home: const SiteShellScreen(),
    );
  }
}
