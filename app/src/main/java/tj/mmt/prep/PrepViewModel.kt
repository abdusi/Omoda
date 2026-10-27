package tj.mmt.prep

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

enum class Screen { CLUSTERS, SUBJECTS, QUIZ, RESULT }

class PrepViewModel(bank: QuestionBank, private val saved: SavedStateHandle) : ViewModel() {
    var loading by mutableStateOf(true); private set
    var error by mutableStateOf(false); private set
    var screen by mutableStateOf(Screen.CLUSTERS); private set
    var subjectId by mutableStateOf("tajik"); private set
    var clusterId by mutableStateOf(2); private set
    var session by mutableStateOf<QuizSession?>(null); private set
    var pools by mutableStateOf<Map<String, List<Question>>>(emptyMap()); private set
    val subject: Subject get() = subjects.first { it.id == subjectId }
    val cluster: Cluster get() = clusters.first { it.id == clusterId }
    val activeSubjects: List<Subject> get() = cluster.subjects
    val ordered: List<Question> get() {
        val byId = pools[subjectId].orEmpty().associateBy { it.id }
        return session?.ids?.mapNotNull { byId[it] }.orEmpty()
    }
    val question: Question? get() = session?.let { ordered.getOrNull(it.index) }
    val score: Int get() = session?.score(ordered.associate { it.id to it.correct }) ?: 0

    init {
        viewModelScope.launch {
            try {
                pools = withContext(Dispatchers.IO) { bank.load() }
                restore()
            } catch (_: Exception) { error = true }
            loading = false
        }
    }
    fun openSubjects(id: Int) {
        val selected = clusters.firstOrNull { it.id == id && it.available } ?: return
        clusterId = selected.id
        if (subjectId !in selected.subjectIds) subjectId = selected.subjectIds.first()
        screen = Screen.SUBJECTS
        persist()
    }
    fun home() { session = null; screen = Screen.CLUSTERS; persist() }
    fun leaveQuiz() { session = null; screen = Screen.SUBJECTS; persist() }
    fun start(id: String = subjectId) {
        if (id !in cluster.subjectIds) return
        val pool = pools[id].orEmpty()
        if (pool.size < 25) return
        subjectId = id
        session = QuizSession.start(pool.map { it.id })
        screen = Screen.QUIZ
        persist()
    }
    fun answer(option: Int) { session = session?.answer(option); persist() }
    fun next() {
        val current = session ?: return
        if (current.selected == -1) return
        if (current.complete) screen = Screen.RESULT else session = current.next()
        persist()
    }
    private fun persist() {
        saved["screen"] = screen.name
        saved["subject"] = subjectId
        saved["cluster"] = clusterId
        saved["session"] = session?.let {
            JSONObject().put("ids", JSONArray(it.ids)).put("answers", JSONArray(it.answers)).put("index", it.index).toString()
        }
    }
    private fun restore() {
        clusterId = saved.get<Int>("cluster")?.takeIf { id -> clusters.any { it.id == id && it.available } } ?: 2
        subjectId = saved.get<String>("subject")?.takeIf { id -> subjects.any { it.id == id } } ?: "tajik"
        if (subjectId !in cluster.subjectIds) subjectId = cluster.subjectIds.first()
        screen = saved.get<String>("screen")?.let { runCatching { Screen.valueOf(it) }.getOrNull() } ?: Screen.CLUSTERS
        session = runCatching {
            val json = JSONObject(saved.get<String>("session") ?: return@runCatching null)
            val ids = json.getJSONArray("ids")
            val answers = json.getJSONArray("answers")
            QuizSession((0 until ids.length()).map { ids.getString(it) },
                (0 until answers.length()).map { answers.getInt(it) }, json.getInt("index"))
        }.getOrNull()
        val validIds = pools[subjectId].orEmpty().map { it.id }.toSet()
        if (screen in listOf(Screen.QUIZ, Screen.RESULT) &&
            (session == null || session!!.ids.any { it !in validIds } || (screen == Screen.RESULT && !session!!.complete))) {
            session = null
            screen = Screen.SUBJECTS
        }
    }
}
