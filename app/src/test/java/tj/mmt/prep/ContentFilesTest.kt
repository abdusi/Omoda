package tj.mmt.prep

import org.junit.Assert.*
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class ContentFilesTest {
    private fun zip(name: String, text: String): ByteArray {
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { it.putNextEntry(ZipEntry(name)); it.write(text.toByteArray()); it.closeEntry() }
        return bytes.toByteArray()
    }

    @Test fun rejectsZipTraversalWithoutWritingOutsideStaging() {
        val root = Files.createTempDirectory("omoda-test").toFile()
        try {
            val stage = java.io.File(root, "stage").also { it.mkdirs() }
            assertThrows(IllegalArgumentException::class.java) {
                ContentFiles.unpack(ByteArrayInputStream(zip("../escaped", "bad")), stage, 3, 1)
            }
            assertFalse(java.io.File(root, "escaped").exists())
        } finally { root.deleteRecursively() }
    }

    @Test fun rejectsExpandedSizeLargerThanManifest() {
        val root = Files.createTempDirectory("omoda-test").toFile()
        try {
            assertThrows(IllegalArgumentException::class.java) {
                ContentFiles.unpack(ByteArrayInputStream(zip("bank.json", "too large")), root, 2, 1)
            }
        } finally { root.deleteRecursively() }
    }

    @Test fun rejectsTruncatedPackageAndAllowsCancellation() {
        val root = Files.createTempDirectory("omoda-test").toFile()
        try {
            assertThrows(IllegalArgumentException::class.java) {
                ContentFiles.unpack(ByteArrayInputStream(zip("bank.json", "x")), root, 2, 1)
            }
            assertThrows(java.util.concurrent.CancellationException::class.java) {
                ContentFiles.unpack(ByteArrayInputStream(zip("bank.json", "x")), root, 1, 1) {
                    throw java.util.concurrent.CancellationException()
                }
            }
        } finally { root.deleteRecursively() }
    }

    @Test fun rejectsAbsoluteAndWindowsPaths() {
        val root = Files.createTempDirectory("omoda-test").toFile()
        try {
            listOf("/etc/file", "C:/file", "questions\\file", "questions/../file", ".").forEach {
                assertThrows(IllegalArgumentException::class.java) { ContentFiles.child(root, it) }
            }
        } finally { root.deleteRecursively() }
    }
}
