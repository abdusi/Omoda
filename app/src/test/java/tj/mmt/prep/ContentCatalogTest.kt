package tj.mmt.prep

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files

class ContentCatalogTest {
    private fun release(): JSONObject {
        val hash = "a".repeat(64)
        return JSONObject().put("id", "tajik").put("version", hash).put("year", 2026).put("count", 200)
            .put("path", "banks/tajik/" + hash + "/").put("bankSha256", hash).put("packSha256", hash)
            .put("packBytes", 1000).put("unpackedBytes", 2000)
    }

    @Test fun rejectsForeignPathsAndUnknownSubjects() {
        assertThrows(IllegalArgumentException::class.java) {
            BankRelease.parse(release().put("path", "https://other.example/pack.zip"))
        }
        assertThrows(IllegalArgumentException::class.java) { BankRelease.parse(release().put("id", "../secret")) }
        assertThrows(IllegalArgumentException::class.java) { BankRelease.parse(release().put("packBytes", 999999999)) }
    }

    @Test fun rejectsUnsupportedSchemaAndDuplicateSubjects() {
        val catalog = JSONObject().put("schema", 3).put("year", 2026).put("subjects", JSONArray().put(release()))
        assertThrows(IllegalArgumentException::class.java) { ContentCatalog.parse(catalog.toString()) }
        catalog.put("schema", 1).getJSONArray("subjects").put(release())
        assertThrows(IllegalArgumentException::class.java) { ContentCatalog.parse(catalog.toString()) }
    }

    @Test fun missingMediaAndDuplicateQuestionsCannotStartATest() {
        val root = Files.createTempDirectory("omoda-test").toFile()
        try {
            val fragment = JSONObject().put("text", "text").put("visual", true)
                .put("image", "questions/missing.webp").put("width", 10).put("height", 10)
                .put("sha256", "a".repeat(64))
            val array = JSONArray()
            repeat(25) { i ->
                array.put(JSONObject().put("id", "q-" + i).put("number", i + 1).put("page", 1).put("source", "source.pdf")
                    .put("prompt", fragment).put("options", JSONArray().put(fragment).put(fragment).put(fragment).put(fragment)).put("correct", 0))
            }
            assertThrows(IllegalArgumentException::class.java) { QuestionBank.parse(array.toString(), root, true) }
            array.getJSONObject(24).put("id", "q-0")
            assertThrows(IllegalArgumentException::class.java) { QuestionBank.parse(array.toString(), root, false) }
        } finally { root.deleteRecursively() }
    }
}
