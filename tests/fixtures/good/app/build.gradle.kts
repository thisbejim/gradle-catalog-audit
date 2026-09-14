plugins { alias(libs.plugins.kotlin.jvm) }

dependencies {
    implementation(libs.kotlin.stdlib)
    testImplementation(libs.bundles.test)
}

val kotlinVersion = libs.versions.kotlin.get()
