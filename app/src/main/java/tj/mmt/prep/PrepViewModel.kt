package tj.mmt.prep

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

enum class Screen { COMPONENTS, CLUSTERS, SUBJECTS, QUIZ, RESULT }

class PrepViewModel(private val repository: ContentRepository, private val saved: SavedStateHandle) : ViewModel() {
    var loading by mutableStateOf(true); private set
    var screen by mutableStateOf(Screen.COMPONENTS); private set
    var componentId by mutableStateOf("A"); private set
    var subjectId by mutableStateOf("tajik"); private set
    var clusterId by mutableStateOf(2); private set
    var session by mutableStateOf<QuizSession?>(null); private set
    var catalog by mutableStateOf(repository.catalog()); private set
    var downloaded by mutableStateOf<Map<String, BankRelease>>(emptyMap()); private set
    var busy by mutableStateOf(false); private set
    var refreshing by mutableStateOf(false); private set
    var progress by mutableStateOf(""); private set
    var notice by mutableStateOf<String?>(null); private set
    var onlineMode by mutableStateOf(false); private set
    var attemptYear by mutableStateOf(catalog.year); private set
    private var operation: Job? = null
    private var questions by mutableStateOf<List<Question>>(emptyList())
    val subject: Subject get() = subjects.first { it.id == subjectId }
    val component: ExamComponent get() = examComponents.first { it.id == componentId }
    val availableClusters: List<Cluster> get() = component.clusters
    val cluster: Cluster get() = availableClusters.first { it.id == clusterId }
    val activeSubjects: List<Subject> get() = cluster.subjects
    val ordered: List<Question> get() {
        val byId = questions.associateBy { it.id }
        return session?.ids?.mapNotNull { byId[it] }.orEmpty()
    }
    val question: Question? get() = session?.let { ordered.getOrNull(it.index) }
    val score: Int get() = session?.score(ordered.associate { it.id to it.correct }) ?: 0
    val testSize: Int get() = session?.ids?.size ?: 25
    fun subjectCode(id: String): String = component.subjectCode(cluster, id)

    fun openComponent(id: String) {
        if (busy || examComponents.none { it.id == id }) return
        componentId = id
        clusterId = 1
        subjectId = component.clusters.first().subjectIds.first()
        session = null
        questions = emptyList()
        screen = Screen.CLUSTERS
        persist()
    }

    fun chooseComponent() {
        if (busy) return
        session = null
        questions = emptyList()
        screen = Screen.COMPONENTS
        persist()
    }

    init {
        viewModelScope.launch {
            repository.cleanupInterruptedDownloads()
            downloaded = withContext(Dispatchers.IO) { repository.installed() }
            val restored = withContext(Dispatchers.IO) { runCatching { repository.restoreQuestions() }.getOrDefault(emptyList()) }
            questions = restored
            restore()
            loading = false
            refreshCatalog()
        }
    }

    fun refreshCatalog() {
        if (refreshing || busy) return
        refreshing = true
        viewModelScope.launch {
            try {
                catalog = repository.refresh()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                notice = "Каталог нав нашуд. Пайвасти интернетро санҷед. Фанҳои боргирифта дастрасанд."
            } finally { refreshing = false }
        }
    }

    fun dismissNotice() { notice = null }
    fun cancelOperation() { operation?.cancel() }

    private fun perform(label: String, action: suspend () -> Unit) {
        if (busy) return
        busy = true
        progress = label
        notice = null
        operation = viewModelScope.launch {
            try {
                action()
            } catch (_: CancellationException) {
                notice = "Боргирӣ қатъ шуд. Маълумоти пешина нигоҳ дошта шуд."
            } catch (_: Exception) {
                notice = "Амалиёт иҷро нашуд. Интернет ва ҷойи холии дастгоҳро санҷед ва аз нав кӯшиш кунед."
            } finally {
                downloaded = withContext(kotlinx.coroutines.NonCancellable + Dispatchers.IO) { repository.installed() }
                busy = false
                progress = ""
            }
        }
    }

    private suspend fun showProgress(label: String, done: Int, total: Int) {
        withContext(Dispatchers.Main) {
            progress = label + " · " + if (total == 100) done.toString() + "%" else done.toString() + " / " + total
        }
    }

    fun downloadSubject(id: String) {
        val release = catalog.banks[id] ?: return
        val title = subjects.first { it.id == id }.title
        perform("Боргирии " + title) {
            repository.install(release) { done, total -> showProgress(title, done, total) }
            notice = "Фан барои истифодаи бе интернет омода аст."
        }
    }

    fun downloadCluster() {
        val releases = activeSubjects.mapNotNull { catalog.banks[it.id] }
        if (releases.size != activeSubjects.size) return
        perform("Боргирии кластер") {
            releases.forEachIndexed { index, release ->
                val title = subjects.first { it.id == release.id }.title
                repository.install(release) { done, total ->
                    showProgress((index + 1).toString() + " / " + releases.size + " · " + title, done, total)
                }
            }
            notice = "Ҳамаи фанҳои кластер барои истифодаи бе интернет омодаанд."
        }
    }

    fun removeSubject(id: String) = perform("Ҳазфи файли боргирифта") {
        repository.remove(id)
        notice = "Файли фан аз дастгоҳ ҳазф шуд."
    }

    fun openSubjects(id: Int) {
        if (busy) return
        val selected = availableClusters.firstOrNull { it.id == id && it.available } ?: return
        clusterId = selected.id
        if (subjectId !in selected.subjectIds) subjectId = selected.subjectIds.first()
        screen = Screen.SUBJECTS
        persist()
    }

    fun home() { if (busy) return; session = null; questions = emptyList(); screen = Screen.CLUSTERS; persist() }
    fun leaveQuiz() { if (busy) return; session = null; questions = emptyList(); screen = Screen.SUBJECTS; persist() }

    fun start(id: String = subjectId, online: Boolean = onlineMode) {
        if (id !in cluster.subjectIds || busy) return
        if (!online && id !in downloaded) {
            notice = "Аввал ин фанро боргирӣ кунед ё санҷиши онлайнро интихоб кунед."
            return
        }
        val release = catalog.banks[id]
        perform(if (online) "Омодасозии санҷиши онлайн" else "Омодасозии санҷиши офлайн") {
            val loaded = repository.prepare(id, release, online) { done, total ->
                showProgress("Омодасозии саволҳо", done, total)
            }
            subjectId = id
            onlineMode = online
            attemptYear = if (online) requireNotNull(release).year else requireNotNull(downloaded[id]).year
            // The repository has persisted this exact attempt, including small banks.
            questions = loaded
            session = QuizSession(loaded.map { it.id }, List(loaded.size) { -1 })
            screen = Screen.QUIZ
            persist()
        }
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
        saved["component"] = componentId
        saved["subject"] = subjectId
        saved["cluster"] = clusterId
        saved["online"] = onlineMode
        saved["year"] = attemptYear
        saved["session"] = session?.let {
            JSONObject().put("ids", JSONArray(it.ids)).put("answers", JSONArray(it.answers)).put("index", it.index).toString()
        }
    }

    private fun restore() {
        componentId = saved.get<String>("component")?.takeIf { id -> examComponents.any { it.id == id } } ?: "A"
        clusterId = saved.get<Int>("cluster")?.takeIf { id -> availableClusters.any { it.id == id && it.available } } ?: 1
        subjectId = saved.get<String>("subject")?.takeIf { it in cluster.subjectIds } ?: cluster.subjectIds.first()
        onlineMode = saved.get<Boolean>("online") ?: false
        attemptYear = saved.get<Int>("year") ?: catalog.year
        screen = saved.get<String>("screen")?.let { runCatching { Screen.valueOf(it) }.getOrNull() } ?: Screen.COMPONENTS
        session = runCatching {
            val json = JSONObject(saved.get<String>("session") ?: return@runCatching null)
            val ids = json.getJSONArray("ids")
            val answers = json.getJSONArray("answers")
            QuizSession((0 until ids.length()).map { ids.getString(it) },
                (0 until answers.length()).map { answers.getInt(it) }, json.getInt("index"))
        }.getOrNull()
        val validIds = questions.map { it.id }.toSet()
        if (screen in listOf(Screen.QUIZ, Screen.RESULT) &&
            (session == null || session!!.ids.any { it !in validIds } ||
                questions.any { !it.id.startsWith(subjectId + "-") } ||
                (screen == Screen.RESULT && !session!!.complete))) {
            session = null
            questions = emptyList()
            screen = Screen.SUBJECTS
            notice = "Санҷиши пешина барқарор нашуд. Санҷиши навро оғоз кунед."
        }
    }
}
