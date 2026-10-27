package tj.mmt.prep

import android.content.res.AssetManager
import org.json.JSONArray
import org.json.JSONObject

data class Fragment(val text: String, val image: String, val width: Int, val height: Int, val visual: Boolean)
data class Question(val id: String, val number: Int, val page: Int, val source: String,
                    val prompt: Fragment, val options: List<Fragment>, val correct: Int)
data class Subject(val id: String, val title: String, val code: String, val caption: String, val symbol: String)
data class Cluster(val id: Int, val title: String, val subjectIds: List<String> = emptyList()) {
    val available: Boolean get() = subjectIds.isNotEmpty()
    val subjects: List<Subject> get() = subjectIds.map { id -> tj.mmt.prep.subjects.first { it.id == id } }
}

val subjects = listOf(
    Subject("tajik", "Забони тоҷикӣ", "А1", "Забон ва имло", "Аа"),
    Subject("math", "Математика", "А2", "Ададҳо ва муодилаҳо", "∑"),
    Subject("geography", "География", "А3", "Ҷаҳон ва табиат", "◎"),
    Subject("english", "Забони англисӣ", "А4", "Грамматика ва луғат", "En"),
    Subject("biology", "Биология", "А2", "Ҳаёт ва табиат", "Б"),
    Subject("chemistry", "Химия", "А3", "Моддаҳо ва реаксияҳо", "Х"),
    Subject("physics", "Физика", "А4", "Қонунҳои табиат", "Ф"),
    Subject("history", "Таърих", "А2", "Гузашта ва тамаддун", "Т"),
    Subject("law", "Ҳуқуқ", "А3", "Давлат ва ҳуқуқ", "Ҳ"),
    Subject("literature", "Адабиёти тоҷик", "А3", "Адибон ва осор", "Ад")
)
val clusters = listOf(
    Cluster(1, "Табиӣ ва техникӣ", listOf("tajik", "math", "chemistry", "physics")),
    Cluster(2, "Иқтисод ва география", listOf("tajik", "math", "geography", "english")),
    Cluster(3, "Филология, педагогика ва санъат", listOf("tajik", "history", "literature", "english")),
    Cluster(4, "Ҷомеашиносӣ ва ҳуқуқ", listOf("tajik", "history", "law", "english")),
    Cluster(5, "Тиб, биология ва варзиш", listOf("tajik", "biology", "chemistry", "physics"))
)

class QuestionBank(private val assets: AssetManager) {
    fun load(): Map<String, List<Question>> = subjects.associate { subject ->
        val json = assets.open("${subject.id}.json").bufferedReader(Charsets.UTF_8).use { JSONArray(it.readText()) }
        val questions = (0 until json.length()).map { index ->
            val q = json.getJSONObject(index)
            val options = q.getJSONArray("options")
            Question(q.getString("id"), q.getInt("number"), q.getInt("page"), q.getString("source"),
                fragment(q.getJSONObject("prompt")), (0 until options.length()).map { fragment(options.getJSONObject(it)) }, q.getInt("correct"))
        }
        require(questions.size >= 25)
        require(questions.map { it.id }.distinct().size == questions.size)
        require(questions.all { it.options.size == 4 && it.correct in 0..3 })
        subject.id to questions
    }
    private fun fragment(json: JSONObject) = Fragment(json.getString("text"), json.getString("image"),
        json.getInt("width"), json.getInt("height"), json.optBoolean("visual"))
}
