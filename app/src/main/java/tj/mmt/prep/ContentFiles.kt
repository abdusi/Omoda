package tj.mmt.prep

import java.io.File
import java.io.InputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.zip.ZipInputStream

/** All content paths are relative, even when a downloaded catalog or ZIP is malformed. */
object ContentFiles {
    fun child(root: File, path: String): File {
        require(path.isNotBlank() && !path.startsWith("/") && !path.contains("\\") &&
            !path.contains(":") && path.split("/").none { it == ".." || it == "." })
        val child = File(root, path).canonicalFile
        require(child.toPath().startsWith(root.canonicalFile.toPath()) && child != root.canonicalFile)
        return child
    }

    fun sha256(file: File): String {
        val hash = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(32768)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                hash.update(buffer, 0, count)
            }
        }
        return hash.digest().joinToString("") { "%02x".format(it) }
    }

    fun replace(target: File, bytes: ByteArray) {
        target.parentFile!!.mkdirs()
        val temporary = File(target.parentFile, target.name + ".new")
        temporary.outputStream().use { it.write(bytes); it.fd.sync() }
        Files.move(temporary.toPath(), target.toPath(),
            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
    }

    fun unpack(input: InputStream, directory: File, maxBytes: Long, maxEntries: Int,
               checkCancelled: () -> Unit = {}) {
        require(maxBytes in 1..300_000_000 && maxEntries in 1..100_000)
        val names = mutableSetOf<String>()
        var total = 0L
        ZipInputStream(input).use { zip ->
            while (true) {
                checkCancelled()
                val entry = zip.nextEntry ?: break
                require(names.add(entry.name) && names.size <= maxEntries) { "Duplicate or excessive ZIP entries" }
                val file = child(directory, entry.name)
                if (entry.isDirectory) {
                    file.mkdirs()
                    continue
                }
                file.parentFile!!.mkdirs()
                file.outputStream().use { output ->
                    val buffer = ByteArray(32768)
                    while (true) {
                        checkCancelled()
                        val count = zip.read(buffer)
                        if (count < 0) break
                        total += count
                        require(total <= maxBytes) { "Package exceeds unpacked size" }
                        output.write(buffer, 0, count)
                    }
                }
                zip.closeEntry()
            }
        }
        require(total == maxBytes) { "Incomplete package" }
    }
}
