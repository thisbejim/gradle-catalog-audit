plugins {
    alias(libs.plugins.plugnis.tool)
    val x = libs.findLibrary("does-not-exist")
}
