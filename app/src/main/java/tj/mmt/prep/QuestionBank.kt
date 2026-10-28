package tj.mmt.prep

import java.io.File
import org.json.JSONArray
import org.json.JSONObject

data class Fragment(val text: String, val image: String, val width: Int, val height: Int,
                    val visual: Boolean, val sha256: String = "")
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
    Subject("literature", "Адабиёти тоҷик", "А3", "Адибон ва осор", "Ад"),
    Subject("b_math", "Математика", "Б2", "Ададҳо ва муодилаҳо", "∑"),
    Subject("b_physics", "Физика", "Б3", "Қонунҳои табиат", "Ф"),
    Subject("b_geography", "География", "Б3", "Ҷаҳон ва табиат", "◎"),
    Subject("b_literature", "Адабиёти тоҷик", "Б2", "Адибон ва осор", "Ад"),
    Subject("b_english", "Забони англисӣ", "Б3", "Грамматика ва луғат", "En"),
    Subject("b_history", "Таърих", "Б2", "Гузашта ва тамаддун", "Т"),
    Subject("b_biology", "Биология", "Б2", "Ҳаёт ва табиат", "Б"),
    Subject("b_chemistry", "Химия", "Б3", "Моддаҳо ва реаксияҳо", "Х")
)
val clusters = listOf(
    Cluster(1, "Табиӣ ва техникӣ", listOf("tajik", "math", "chemistry", "physics")),
    Cluster(2, "Иқтисод ва география", listOf("tajik", "math", "geography", "english")),
    Cluster(3, "Филология, педагогика ва санъат", listOf("tajik", "history", "literature", "english")),
    Cluster(4, "Ҷомеашиносӣ ва ҳуқуқ", listOf("tajik", "history", "law", "english")),
    Cluster(5, "Тиб, биология ва варзиш", listOf("tajik", "biology", "chemistry", "physics"))
)
val bClusters = listOf(
    Cluster(1, "Табиӣ ва техникӣ", listOf("tajik", "b_math", "b_physics")),
    Cluster(2, "Иқтисод ва география", listOf("tajik", "b_math", "b_geography")),
    Cluster(3, "Филология, педагогика ва санъат", listOf("tajik", "b_literature", "b_english")),
    Cluster(4, "Ҷомеашиносӣ ва ҳуқуқ", listOf("tajik", "b_history", "b_english")),
    Cluster(5, "Тиб, биология ва варзиш", listOf("tajik", "b_biology", "b_chemistry"))
)

data class ExamComponent(val id: String, val letter: String, val grade: Int, val clusters: List<Cluster>) {
    val title: String get() = "Варианти " + letter
    val subtitle: String get() = "Синфи " + grade
    fun subjectCode(cluster: Cluster, subjectId: String): String {
        val index = cluster.subjectIds.indexOf(subjectId)
        require(index >= 0)
        return letter + (index + 1)
    }
}

val examComponents = listOf(
    ExamComponent("A", "А", 11, clusters),
    ExamComponent("B", "Б", 9, bClusters)
)

object QuestionBank {
    fun parse(text: String, directory: File, checkImages: Boolean): List<Question> {
        val json = JSONArray(text)
        require(json.length() in 1..10000)
        val questions = (0 until json.length()).map { index ->
            val q = json.getJSONObject(index)
            val options = q.getJSONArray("options")
            Question(q.getString("id"), q.getInt("number"), q.getInt("page"), q.getString("source"),
                fragment(q.getJSONObject("prompt"), directory, checkImages),
                (0 until options.length()).map { fragment(options.getJSONObject(it), directory, checkImages) }, q.getInt("correct"))
        }
        require(questions.isNotEmpty())
        require(questions.map { it.id }.distinct().size == questions.size)
        require(questions.all { it.options.size == 4 && it.correct in 0..3 })
        return questions
    }
    private fun fragment(json: JSONObject, directory: File, checkImages: Boolean): Fragment {
        val visual = json.getBoolean("visual")
        val image = if (visual) ContentFiles.child(directory, json.getString("image")) else null
        if (checkImages && visual) require(image!!.isFile)
        val text = json.getString("text")
        require(visual || text.isNotBlank())
        val width = json.getInt("width")
        val height = json.getInt("height")
        require(width in 1..20000 && height in 1..20000 && width.toLong() * height <= 40_000_000)
        val sha = if (visual) json.getString("sha256") else ""
        require(!visual || sha.matches(Regex("[a-f0-9]{64}")))
        return Fragment(text, image?.absolutePath.orEmpty(), width, height, visual, sha)
    }
}
