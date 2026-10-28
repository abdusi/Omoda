package tj.mmt.prep

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ExamComponentsTest {
    @Test fun componentBHasExactlyTheThreeOfficialSubjectsInEachCluster() {
        val expected = listOf(
            listOf("tajik", "b_math", "b_physics"),
            listOf("tajik", "b_math", "b_geography"),
            listOf("tajik", "b_literature", "b_english"),
            listOf("tajik", "b_history", "b_english"),
            listOf("tajik", "b_biology", "b_chemistry"))
        val b = examComponents.single { it.id == "B" }
        assertEquals(9, b.grade)
        assertEquals(expected, b.clusters.map { it.subjectIds })
        assertEquals((1..5).toList(), b.clusters.map { it.id })
        b.clusters.forEach { cluster ->
            assertEquals(listOf("Б1", "Б2", "Б3"), cluster.subjectIds.map { b.subjectCode(cluster, it) })
        }
    }

    @Test fun componentsShareOnlyTheOfficialTajikBankAndUseOnlyEnglishAsForeignLanguage() {
        val a = examComponents.single { it.id == "A" }
        val b = examComponents.single { it.id == "B" }
        val aIds = a.clusters.flatMap { it.subjectIds }.toSet()
        val bIds = b.clusters.flatMap { it.subjectIds }.toSet()
        assertEquals(setOf("tajik"), aIds.intersect(bIds))
        assertTrue(a.clusters.all { it.subjectIds.size == 4 })
        assertTrue(b.clusters.all { it.subjectIds.size == 3 })
        assertEquals(18, (aIds + bIds).size)
        assertTrue(subjects.filter { it.id !in setOf("english", "b_english") }
            .none { it.id.contains("french") || it.id.contains("german") || it.id.contains("arabic") })
        assertNotEquals(subjects.first { it.id == "math" }, subjects.first { it.id == "b_math" })
    }

    private fun componentsJson(): JSONArray = JSONArray().apply {
        examComponents.forEach { component ->
            put(JSONObject().put("id", component.id).put("grade", component.grade)
                .put("clusters", JSONArray().apply {
                    component.clusters.forEach { group ->
                        put(JSONObject().put("id", group.id).put("subjects", JSONArray(group.subjectIds)))
                    }
                }))
        }
    }

    @Test fun v2Accepts18QuestionEnglishBankButRejectsCrossComponentCatalogMappings() {
        val hash = "b".repeat(64)
        val release = BankRelease("b_english", hash, 2026, 18, "banks/b_english/" + hash + "/", hash, hash, 1000, 2000)
        val catalog = JSONObject().put("schema", 2).put("year", 2026)
            .put("subjects", JSONArray().put(release.json())).put("components", componentsJson())
        assertEquals(18, ContentCatalog.parse(catalog.toString()).banks["b_english"]!!.count)
        assertEquals(release, BankRelease.parse(release.json()))
        catalog.getJSONArray("components").getJSONObject(1).getJSONArray("clusters")
            .getJSONObject(0).put("subjects", JSONArray(listOf("tajik", "math", "physics")))
        assertThrows(IllegalArgumentException::class.java) { ContentCatalog.parse(catalog.toString()) }
    }

    @Test fun legacyCatalogCannotAdvertiseBSubjects() {
        val hash = "b".repeat(64)
        val release = BankRelease("b_math", hash, 2026, 25, "banks/b_math/" + hash + "/", hash, hash, 1000, 2000)
        val catalog = JSONObject().put("schema", 1).put("year", 2026).put("subjects", JSONArray().put(release.json()))
        assertThrows(IllegalArgumentException::class.java) { ContentCatalog.parse(catalog.toString()) }
    }
}
