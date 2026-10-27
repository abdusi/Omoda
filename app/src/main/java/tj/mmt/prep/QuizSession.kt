package tj.mmt.prep

import kotlin.random.Random

/** Immutable session: the first answer is final, and advancing requires an answer. */
data class QuizSession(val ids: List<String>, val answers: List<Int>, val index: Int = 0) {
    init {
        require(ids.size == 25 && ids.distinct().size == 25)
        require(answers.size == ids.size && answers.all { it in -1..3 })
        require(index in ids.indices)
        require(answers.take(index).all { it != -1 })
        require(answers.drop(index + 1).all { it == -1 })
    }
    val selected: Int get() = answers[index]
    val complete: Boolean get() = index == ids.lastIndex && selected != -1
    fun answer(option: Int): QuizSession {
        require(option in 0..3)
        if (selected != -1) return this
        return copy(answers = answers.toMutableList().also { it[index] = option })
    }
    fun next(): QuizSession {
        if (selected == -1 || index == ids.lastIndex) return this
        return copy(index = index + 1)
    }
    fun score(correct: Map<String, Int>): Int = ids.indices.count { answers[it] == correct.getValue(ids[it]) }

    companion object {
        fun start(pool: List<String>, random: Random = Random.Default): QuizSession {
            val unique = pool.distinct()
            require(unique.size >= 25) { "At least 25 different questions required" }
            return QuizSession(unique.shuffled(random).take(25), List(25) { -1 })
        }
    }
}
