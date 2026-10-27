package tj.mmt.prep

import org.junit.Assert.*
import org.junit.Test

class ClusterCatalogTest {
    @Test fun `cluster one reuses math and science banks in exam order`() {
        val one = clusters.first { it.id == 1 }
        assertTrue(one.available)
        assertEquals(listOf("tajik", "math", "chemistry", "physics"), one.subjectIds)
        assertEquals(listOf("А1", "А2", "А3", "А4"), one.subjects.map { it.code })
        for (subject in one.subjects) assertSame(subjects.first { it.id == subject.id }, subject)
    }
    @Test fun `cluster three adds literature and reuses language and history banks`() {
        val three = clusters.first { it.id == 3 }
        assertTrue(three.available)
        assertEquals(listOf("tajik", "history", "literature", "english"), three.subjectIds)
        assertEquals(listOf("А1", "А2", "А3", "А4"), three.subjects.map { it.code })
        assertEquals("Адабиёти тоҷик", three.subjects[2].title)
        for (id in listOf("tajik", "history", "english")) {
            assertSame(clusters.first { it.id == 4 }.subjects.first { it.id == id }, three.subjects.first { it.id == id })
        }
    }
    @Test fun `cluster five has the supplied four subjects in exam order`() {
        val cluster = clusters.first { it.id == 5 }
        assertTrue(cluster.available)
        assertEquals(listOf("tajik", "biology", "chemistry", "physics"), cluster.subjects.map { it.id })
        assertEquals(listOf("А1", "А2", "А3", "А4"), cluster.subjects.map { it.code })
    }
    @Test fun `economics keeps its subjects and shares only Tajik with cluster five`() {
        val two = clusters.first { it.id == 2 }.subjectIds
        val five = clusters.first { it.id == 5 }.subjectIds
        assertEquals(listOf("tajik", "math", "geography", "english"), two)
        assertEquals(setOf("tajik"), two.toSet().intersect(five.toSet()))
        assertEquals(setOf(1, 2, 3, 4, 5), clusters.filter { it.available }.map { it.id }.toSet())
    }
    @Test fun `cluster four has the supplied subjects in exam order`() {
        val cluster = clusters.first { it.id == 4 }
        assertTrue(cluster.available)
        assertEquals(listOf("tajik", "history", "law", "english"), cluster.subjectIds)
        assertEquals(listOf("А1", "А2", "А3", "А4"), cluster.subjects.map { it.code })
    }
    @Test fun `cluster four reuses the same language subjects without duplicate banks`() {
        val two = clusters.first { it.id == 2 }
        val four = clusters.first { it.id == 4 }
        for (id in listOf("tajik", "english")) {
            assertSame(two.subjects.first { it.id == id }, four.subjects.first { it.id == id })
        }
        assertEquals(subjects.size, subjects.map { it.id }.toSet().size)
    }
}
