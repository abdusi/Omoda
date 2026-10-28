package tj.mmt.prep

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger

data class BankRelease(val id: String, val version: String, val year: Int, val count: Int, val path: String,
    val bankSha256: String, val packSha256: String, val packBytes: Long, val unpackedBytes: Long) {
    fun json(): JSONObject = JSONObject().put("id", id).put("version", version).put("year", year).put("count", count)
        .put("path", path).put("bankSha256", bankSha256).put("packSha256", packSha256)
        .put("packBytes", packBytes).put("unpackedBytes", unpackedBytes)

    companion object {
        fun parse(json: JSONObject): BankRelease {
            val release = BankRelease(json.getString("id"), json.getString("version"), json.getInt("year"), json.getInt("count"),
                json.getString("path"), json.getString("bankSha256"), json.getString("packSha256"),
                json.getLong("packBytes"), json.getLong("unpackedBytes"))
            require(subjects.any { it.id == release.id } && release.count in 25..10000)
            require(release.year in 2026..2100)
            require(listOf(release.version, release.bankSha256, release.packSha256)
                .all { it.matches(Regex("[a-f0-9]{64}")) })
            require(release.path == "banks/" + release.id + "/" + release.version + "/")
            require(release.packBytes in 1..150_000_000 && release.unpackedBytes in 1..300_000_000)
            return release
        }
    }
}

data class ContentCatalog(val year: Int, val banks: Map<String, BankRelease>) {
    companion object {
        fun parse(text: String): ContentCatalog {
            val json = JSONObject(text)
            require(json.getInt("schema") == 1)
            val array = json.getJSONArray("subjects")
            val entries = (0 until array.length()).map { BankRelease.parse(array.getJSONObject(it)) }
            require(entries.map { it.id }.distinct().size == entries.size && entries.isNotEmpty())
            val year = json.getInt("year")
            require(year in 2026..2100)
            return ContentCatalog(year, entries.associateBy { it.id })
        }
    }
}

/** Files are the local source of truth. Complete versions are installed before changing pointers. */
class ContentRepository(context: Context) {
    private val root = File(context.filesDir, "study").also { it.mkdirs() }
    private val bootstrap = context.assets.open("catalog.json").bufferedReader().use { it.readText() }
    private val base = BuildConfig.CONTENT_BASE_URL.trimEnd('/') + "/"
    private val catalogFile = File(root, "catalog.json")

    fun catalog(): ContentCatalog = runCatching { ContentCatalog.parse(catalogFile.readText()) }
        .getOrElse { ContentCatalog.parse(bootstrap) }

    suspend fun refresh(): ContentCatalog = withContext(Dispatchers.IO) {
        val context = currentCoroutineContext()
        val temporary = File(root, "catalog.download")
        try {
            fetch("catalog.json", temporary, 512_000, check = { context.ensureActive() })
            val text = temporary.readText()
            val catalog = ContentCatalog.parse(text)
            ContentFiles.replace(catalogFile, text.toByteArray(Charsets.UTF_8))
            catalog
        } finally { temporary.delete() }
    }

    private fun pointer(id: String): File {
        require(subjects.any { it.id == id })
        return File(root, "installed/" + id + ".json")
    }

    private fun bankDirectory(release: BankRelease): File =
        ContentFiles.child(root, "installed/" + release.id + "/" + release.version)

    fun installed(): Map<String, BankRelease> = subjects.mapNotNull { subject ->
        runCatching {
            val release = BankRelease.parse(JSONObject(pointer(subject.id).readText()))
            require(release.id == subject.id && File(bankDirectory(release), "complete").isFile)
            subject.id to release
        }.getOrNull()
    }.toMap()

    suspend fun install(release: BankRelease, progress: suspend (Int, Int) -> Unit) = withContext(Dispatchers.IO) {
        val context = currentCoroutineContext()
        val directory = bankDirectory(release)
        if (installed()[release.id]?.version == release.version) return@withContext
        require(root.usableSpace > release.packBytes + release.unpackedBytes + 5_000_000) { "Not enough storage" }
        val temporary = File(root, "temporary/" + UUID.randomUUID()).also { it.mkdirs() }
        try {
            progress(0, 1)
            val archive = File(temporary, "pack.zip")
            fetch(release.path + "pack.zip", archive, release.packBytes, release.packSha256,
                check = { context.ensureActive() })
            require(archive.length() == release.packBytes)
            val stage = File(temporary, "bank").also { it.mkdirs() }
            archive.inputStream().use {
                ContentFiles.unpack(it, stage, release.unpackedBytes.toLong(), release.count * 5 + 1) { context.ensureActive() }
            }
            validateBank(stage, release, allImages = true) { context.ensureActive() }
            File(stage, "complete").writeText(release.version)
            directory.parentFile!!.mkdirs()
            // A previous interrupted install has no pointer and can be replaced safely.
            if (directory.exists()) directory.deleteRecursively()
            Files.move(stage.toPath(), directory.toPath(), StandardCopyOption.ATOMIC_MOVE)
            ContentFiles.replace(pointer(release.id), release.json().toString().toByteArray(Charsets.UTF_8))
            directory.parentFile!!.listFiles()?.filter { it.isDirectory && it != directory }?.forEach { it.deleteRecursively() }
            progress(1, 1)
        } finally { temporary.deleteRecursively() }
    }

    suspend fun remove(id: String) = withContext(Dispatchers.IO) {
        pointer(id).delete()
        File(root, "installed/" + id).deleteRecursively()
    }

    suspend fun prepare(id: String, release: BankRelease?, online: Boolean,
                        progress: suspend (Int, Int) -> Unit): List<Question> = withContext(Dispatchers.IO) {
        val context = currentCoroutineContext()
        val temporary = File(root, "sessions/" + UUID.randomUUID()).also { it.mkdirs() }
        try {
            val selectedRelease = if (online) requireNotNull(release) else
                requireNotNull(installed()[id]) { "Subject is not downloaded" }
            require(selectedRelease.id == id)
            val bankFile = File(temporary, "bank.json")
            if (online) {
                fetch(selectedRelease.path + "bank.json", bankFile, 10_000_000, selectedRelease.bankSha256,
                    check = { context.ensureActive() })
            } else {
                File(bankDirectory(selectedRelease), "bank.json").copyTo(bankFile)
            }
            require(ContentFiles.sha256(bankFile) == selectedRelease.bankSha256) { "Bank checksum mismatch" }
            val raw = JSONArray(bankFile.readText())
            require(raw.length() == selectedRelease.count)
            // Validate IDs and keys before choosing a random sample.
            QuestionBank.parse(raw.toString(), temporary, checkImages = false)
            val chosen = (0 until raw.length()).shuffled().take(25).map { raw.getJSONObject(it) }
            val images = chosen.flatMap { question ->
                val options = question.getJSONArray("options")
                listOf(question.getJSONObject("prompt")) + (0 until options.length()).map { options.getJSONObject(it) }
            }.filter { it.getBoolean("visual") }.distinctBy { it.getString("image") }
            val done = AtomicInteger()
            val semaphore = Semaphore(4)
            progress(0, images.size.coerceAtLeast(1))
            coroutineScope {
                images.map { fragment ->
                    async {
                        semaphore.withPermit {
                            val downloadContext = currentCoroutineContext()
                            downloadContext.ensureActive()
                            val name = fragment.getString("image")
                            val target = ContentFiles.child(temporary, name)
                            if (online) {
                                fetch(selectedRelease.path + name, target, 5_000_000, fragment.getString("sha256"),
                                    check = { downloadContext.ensureActive() })
                            } else {
                                target.parentFile!!.mkdirs()
                                ContentFiles.child(bankDirectory(selectedRelease), name).copyTo(target)
                                require(ContentFiles.sha256(target) == fragment.getString("sha256"))
                            }
                            progress(done.incrementAndGet(), images.size.coerceAtLeast(1))
                        }
                    }
                }.awaitAll()
            }
            bankFile.writeText(JSONArray(chosen).toString())
            val questions = QuestionBank.parse(bankFile.readText(), temporary, checkImages = true)
            File(temporary, "release.json").writeText(selectedRelease.json().put("online", online)
                .put("sessionBankSha256", ContentFiles.sha256(bankFile)).toString())
            context.ensureActive()
            ContentFiles.replace(File(root, "session.txt"), temporary.name.toByteArray(Charsets.UTF_8))
            File(root, "sessions").listFiles()?.filter { it != temporary }?.forEach { it.deleteRecursively() }
            questions
        } catch (error: Exception) {
            temporary.deleteRecursively()
            throw error
        }
    }

    fun restoreQuestions(): List<Question> {
        val name = File(root, "session.txt").readText().trim()
        require(name.matches(Regex("[a-f0-9-]{36}")))
        val directory = ContentFiles.child(root, "sessions/" + name)
        val bank = File(directory, "bank.json")
        val metadata = JSONObject(File(directory, "release.json").readText())
        require(ContentFiles.sha256(bank) == metadata.getString("sessionBankSha256"))
        val questions = QuestionBank.parse(bank.readText(), directory, checkImages = true)
        questions.flatMap { listOf(it.prompt) + it.options }.filter { it.visual }.distinctBy { it.image }.forEach {
            require(ContentFiles.sha256(File(it.image)) == it.sha256)
        }
        return questions
    }

    private fun validateBank(directory: File, release: BankRelease, allImages: Boolean, check: () -> Unit) {
        val bank = File(directory, "bank.json")
        require(ContentFiles.sha256(bank) == release.bankSha256)
        val questions = QuestionBank.parse(bank.readText(), directory, checkImages = allImages)
        require(questions.size == release.count)
        questions.flatMap { listOf(it.prompt) + it.options }.filter { it.visual }.distinctBy { it.image }.forEach {
            check()
            require(ContentFiles.sha256(File(it.image)) == it.sha256) { "Image checksum mismatch" }
        }
    }

    private fun fetch(path: String, target: File, maximum: Long, sha: String? = null, check: () -> Unit) {
        ContentFiles.child(root, path.trimEnd('/')) // Validate the remote relative path too.
        val url = URL(base + path)
        require(url.protocol == "https")
        target.parentFile!!.mkdirs()
        val connection = url.openConnection() as HttpURLConnection
        connection.connectTimeout = 15_000
        connection.readTimeout = 30_000
        connection.instanceFollowRedirects = false
        connection.setRequestProperty("User-Agent", "Omoda/0.5")
        try {
            require(connection.responseCode == 200) { "HTTP " + connection.responseCode }
            require(connection.contentLengthLong <= maximum)
            connection.inputStream.use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(32768)
                    var size = 0L
                    while (true) {
                        check()
                        val count = input.read(buffer)
                        if (count < 0) break
                        size += count
                        require(size <= maximum) { "Download too large" }
                        output.write(buffer, 0, count)
                    }
                    output.fd.sync()
                }
            }
            if (sha != null) require(ContentFiles.sha256(target) == sha) { "Download checksum mismatch" }
        } finally { connection.disconnect() }
    }
}
