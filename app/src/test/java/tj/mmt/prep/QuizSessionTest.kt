package tj.mmt.prep

import org.junit.Assert.*
import org.junit.Test
import kotlin.random.Random

class QuizSessionTest {
    private val pool = (1..200).map { "q-$it" }
    @Test fun `draws 25 unique questions and creates fresh draws`() {
        val a = QuizSession.start(pool, Random(42))
        val b = QuizSession.start(pool, Random(43))
        assertEquals(25, a.ids.size)
        assertEquals(25, a.ids.toSet().size)
        assertTrue(pool.containsAll(a.ids))
        assertNotEquals(a.ids, b.ids)
    }
    @Test fun `unanswered question cannot advance and answer cannot change`() {
        val initial = QuizSession.start(pool)
        assertEquals(initial, initial.next())
        val answered = initial.answer(2)
        assertEquals(answered, answered.answer(0))
        assertEquals(1, answered.next().index)
        assertEquals(-1, answered.next().selected)
    }
    @Test fun `scores all 25 without double counting and stops on final question`() {
        var session = QuizSession.start(pool)
        val keys = session.ids.associateWith { 1 }
        repeat(25) { i ->
            session = session.answer(if (i < 17) 1 else 0)
            if (i < 24) assertFalse(session.complete)
            session = session.next()
        }
        assertTrue(session.complete)
        assertEquals(17, session.score(keys))
        assertEquals(session, session.answer(1).next())
    }
    @Test fun `restored session keeps its order position and locked answer`() {
        val original = QuizSession.start(pool).answer(3).next().answer(1)
        val restored = QuizSession(original.ids.toList(), original.answers.toList(), original.index)
        assertEquals(original, restored)
        assertEquals(1, restored.selected)
        assertEquals(original, restored.answer(2))
    }
    @Test(expected = IllegalArgumentException::class) fun `rejects empty bank`() {
        QuizSession.start(emptyList())
    }
    @Test fun `B English uses all 18 unique questions and scores its actual length`() {
        val pool = (1..18).map { "b_english-" + it }
        var attempt = QuizSession.start(pool, Random(42))
        assertEquals(18, attempt.ids.size)
        assertEquals(pool.toSet(), attempt.ids.toSet())
        val correct = pool.associateWith { 2 }
        repeat(18) { index ->
            attempt = attempt.answer(if (index < 9) 2 else 0).next()
        }
        assertTrue(attempt.complete)
        assertEquals(9, attempt.score(correct))
        assertEquals(attempt, attempt.next())
    }
}
