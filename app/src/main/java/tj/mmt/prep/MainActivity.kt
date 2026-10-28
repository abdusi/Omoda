package tj.mmt.prep

import android.graphics.BitmapFactory
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.lifecycle.AbstractSavedStateViewModelFactory
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private val Ink = Color(0xFF172E29)
private val Green = Color(0xFF246B58)
private val Muted = Color(0xFF73817C)
private val Paper = Color(0xFFF7F8FA)
private val Line = Color(0xFFE5EAE7)
private val SoftGreen = Color(0xFFEBF4EF)
private val Red = Color(0xFFB83D45)
private val SoftRed = Color(0xFFFFEFF0)

class MainActivity : ComponentActivity() {
    private val model by viewModels<PrepViewModel> {
        object : AbstractSavedStateViewModelFactory(this, null) {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(key: String, modelClass: Class<T>, handle: SavedStateHandle): T =
                PrepViewModel(ContentRepository(application), handle) as T
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MaterialTheme(
                colorScheme = lightColorScheme(primary = Green, onPrimary = Color.White,
                    background = Paper, surface = Color.White, onSurface = Ink, onBackground = Ink,
                    outline = Line, error = Red),
                typography = Typography(
                    headlineLarge = androidx.compose.ui.text.TextStyle(fontSize = 32.sp, lineHeight = 39.sp, fontWeight = FontWeight.Bold),
                    headlineMedium = androidx.compose.ui.text.TextStyle(fontSize = 26.sp, lineHeight = 34.sp, fontWeight = FontWeight.Bold),
                    titleLarge = androidx.compose.ui.text.TextStyle(fontSize = 21.sp, lineHeight = 29.sp, fontWeight = FontWeight.SemiBold),
                    bodyLarge = androidx.compose.ui.text.TextStyle(fontSize = 17.sp, lineHeight = 26.sp),
                    bodyMedium = androidx.compose.ui.text.TextStyle(fontSize = 15.sp, lineHeight = 23.sp)
                )
            ) { PrepApp(model) }
        }
    }
}

@Composable private fun PrepApp(model: PrepViewModel) {
    var confirmExit by rememberSaveable { mutableStateOf(false) }
    val back: () -> Unit = {
        when (model.screen) {
            Screen.QUIZ -> confirmExit = true
            Screen.SUBJECTS -> model.home()
            Screen.RESULT -> model.leaveQuiz()
            else -> Unit
        }
    }
    BackHandler(enabled = model.screen != Screen.CLUSTERS) { back() }
    Surface(color = Paper, modifier = Modifier.fillMaxSize()) {
        Box(Modifier.fillMaxSize().safeDrawingPadding(), contentAlignment = Alignment.TopCenter) {
            Box(Modifier.widthIn(max = 600.dp).fillMaxSize()) {
                when {
                    model.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Green) }
                    else -> when (model.screen) {
                        Screen.CLUSTERS -> ClusterScreen(model)
                        Screen.SUBJECTS -> SubjectScreen(model, back)
                        Screen.QUIZ -> QuizScreen(model, back)
                        Screen.RESULT -> ResultScreen(model)
                    }
                }
            }
        }
    }
    if (model.notice != null && model.screen in listOf(Screen.CLUSTERS, Screen.SUBJECTS)) {
        Dialog(onDismissRequest = model::dismissNotice) {
            Surface(shape = RoundedCornerShape(20.dp), color = Color.White) {
                Column(Modifier.padding(24.dp)) {
                    Text(model.notice.orEmpty(), style = MaterialTheme.typography.bodyMedium)
                    TextButton(onClick = model::dismissNotice, modifier = Modifier.align(Alignment.End)) { Text("Фаҳмо") }
                }
            }
        }
    }
    if (model.busy) AlertDialog(
        onDismissRequest = {},
        title = { Text("Лутфан интизор шавед") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(model.progress)
                Text("Барномаро то анҷоми боргирӣ кушода нигоҳ доред.", color = Muted, fontSize = 12.sp)
            }
        },
        confirmButton = { TextButton(onClick = model::cancelOperation) { Text("Бекор кардан") } }
    )
    if (confirmExit) AlertDialog(
        onDismissRequest = { confirmExit = false },
        title = { Text("Аз санҷиш мебароед?") },
        text = { Text("Агар бароед, ин кӯшиш қатъ мешавад.") },
        confirmButton = { TextButton(onClick = { confirmExit = false; model.leaveQuiz() }) { Text("Баромадан", color = Red) } },
        dismissButton = { TextButton(onClick = { confirmExit = false }) { Text("Идома додан") } }
    )
}

@Composable private fun Brand() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(Modifier.size(38.dp).clip(RoundedCornerShape(12.dp)).background(Green).padding(9.dp)) {
            Canvas(Modifier.fillMaxSize()) {
                val p = Path().apply {
                    moveTo(0f, size.height*.12f); lineTo(size.width*.32f, size.height*.12f)
                    quadraticTo(size.width*.48f, size.height*.12f, size.width*.5f, size.height*.25f)
                    quadraticTo(size.width*.52f, size.height*.12f, size.width*.68f, size.height*.12f)
                    lineTo(size.width, size.height*.12f); lineTo(size.width, size.height*.85f)
                    lineTo(size.width*.68f, size.height*.85f)
                    quadraticTo(size.width*.52f, size.height*.85f, size.width*.5f, size.height*.97f)
                    quadraticTo(size.width*.48f, size.height*.85f, size.width*.32f, size.height*.85f)
                    lineTo(0f, size.height*.85f); close()
                }
                drawPath(p, Color.White, style = Stroke(1.7.dp.toPx(), cap = StrokeCap.Round))
                drawLine(Color.White, androidx.compose.ui.geometry.Offset(size.width*.5f, size.height*.25f),
                    androidx.compose.ui.geometry.Offset(size.width*.5f, size.height*.9f), 1.5.dp.toPx())
            }
        }
        Text("Омода", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Ink)
    }
}

@Composable private fun Pill(text: String, color: Color = Green, background: Color = SoftGreen) {
    Text(text, color = color, fontSize = 12.sp, fontWeight = FontWeight.Medium,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(background).padding(horizontal = 11.dp, vertical = 5.dp))
}

@Composable private fun ClusterScreen(model: PrepViewModel) {
    val open = model::openSubjects
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Brand(); Pill("ММТ · " + model.catalog.year, Muted, Color.White)
        }
        Spacer(Modifier.height(34.dp))
        Text("Оянда аз\nомодагӣ оғоз меёбад.", style = MaterialTheme.typography.headlineLarge, color = Ink)
        Spacer(Modifier.height(12.dp))
        Text("Дониши худро санҷед ва ба имтиҳон\nбо боварӣ қадам гузоред.", color = Muted, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(30.dp))
        Text("Самти худро интихоб кунед", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(14.dp))
        clusters.forEach { cluster ->
            val active = cluster.available
            Surface(onClick = { open(cluster.id) }, enabled = active, color = if (active) Green else Color.White,
                shape = RoundedCornerShape(20.dp), border = if (active) null else BorderStroke(1.dp, Line),
                modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp)) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    Box(Modifier.size(46.dp).clip(RoundedCornerShape(14.dp)).background(if (active) Color.White.copy(alpha = .13f) else Paper), contentAlignment = Alignment.Center) {
                        Text("0${cluster.id}", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = if (active) Color.White else Muted)
                    }
                    Column(Modifier.weight(1f)) {
                        Text("КЛАСТЕРИ ${cluster.id}", fontSize = 10.sp, letterSpacing = 1.5.sp, color = if (active) Color(0xFFBFE1D3) else Muted)
                        Spacer(Modifier.height(3.dp))
                        Text(cluster.title, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp, color = if (active) Color.White else Ink)
                        if (active) { Spacer(Modifier.height(5.dp)); Text("4 фан · 25 савол дар ҳар санҷиш", fontSize = 12.sp, color = Color(0xFFD5EAE2)) }
                        else Text("Ба наздикӣ", fontSize = 12.sp, color = Muted)
                    }
                    if (active) Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, "Интихоби кластери ${cluster.id}", tint = Color.White)
                }
            }
        }
        Spacer(Modifier.height(14.dp))
        Text("Қадами хурд имрӯз. Боварии бештар фардо.", fontSize = 12.sp, color = Muted, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
    }
}

@Composable private fun PageHeader(title: String, back: () -> Unit, close: Boolean = false, trailing: @Composable () -> Unit = {}) {
    Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 24.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = back) { Icon(if (close) Icons.Default.Close else Icons.AutoMirrored.Filled.ArrowBack,
            if (close) "Баромадан аз санҷиш" else "Бозгашт", tint = Ink) }
        Text(title, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f).padding(start = 4.dp))
        trailing()
    }
}

private fun storageSize(bytes: Long): String = if (bytes < 1024 * 1024)
    (bytes / 1024).toString() + " КиБ"
else String.format(java.util.Locale.ROOT, "%.1f МиБ", bytes / (1024.0 * 1024.0))

@Composable private fun SubjectScreen(model: PrepViewModel, back: () -> Unit) {
    var removeId by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxSize()) {
        PageHeader("Кластери " + model.clusterId, back) {
            TextButton(onClick = model::refreshCatalog, enabled = !model.refreshing) {
                Text(if (model.refreshing) "Навсозӣ…" else "Навсозӣ")
            }
        }
        Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
            Spacer(Modifier.height(16.dp))
            Pill(model.cluster.title.uppercase())
            Spacer(Modifier.height(18.dp))
            Text("Аз кадом фан\nоғоз мекунем?", style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(12.dp))
            Text("Онлайн санҷед ё фанҳоро барои омӯзиши бе интернет боргирӣ кунед.", color = Muted)
            Spacer(Modifier.height(18.dp))
            val pending = model.activeSubjects.mapNotNull { model.catalog.banks[it.id] }
                .filter { model.downloaded[it.id]?.version != it.version }
            OutlinedButton(onClick = model::downloadCluster, enabled = pending.isNotEmpty(),
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                Text(if (pending.isEmpty()) "Кластер боргирӣ шудааст" else
                    "Боргирии кластер · " + storageSize(pending.sumOf { it.packBytes }))
            }
            Spacer(Modifier.height(20.dp))
            model.activeSubjects.forEachIndexed { i, subject ->
                val release = model.catalog.banks[subject.id]
                val local = model.downloaded[subject.id]
                val update = local != null && release != null && local.version != release.version
                Surface(color = Color.White, shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, Line),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 14.dp)) {
                    Column(Modifier.padding(18.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            val palette = listOf(SoftGreen, Color(0xFFEEF0FB), Color(0xFFFDF1E6), Color(0xFFF4ECF7))
                            Box(Modifier.size(46.dp).clip(RoundedCornerShape(14.dp)).background(palette[i]), contentAlignment = Alignment.Center) {
                                Text(subject.symbol, fontWeight = FontWeight.SemiBold, fontSize = 23.sp, color = Ink)
                            }
                            Column(Modifier.weight(1f)) {
                                Text(subject.title, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
                                Text((release?.count ?: local?.count ?: 0).toString() + " савол · " + subject.code,
                                    color = Muted, fontSize = 13.sp)
                            }
                        }
                        Spacer(Modifier.height(10.dp))
                        if (local != null) Text(
                            if (update) "Бе интернет дастрас · Навсозӣ ҳаст" else "Бе интернет дастрас",
                            color = Green, fontSize = 12.sp)
                        else Text("Барои офлайн: " + storageSize(release?.packBytes ?: 0), color = Muted, fontSize = 12.sp)
                        Spacer(Modifier.height(10.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Button(onClick = { model.start(subject.id, online = true) }, enabled = release != null,
                                modifier = Modifier.weight(1f)) { Text("Онлайн") }
                            OutlinedButton(onClick = { model.start(subject.id, online = false) }, enabled = local != null,
                                modifier = Modifier.weight(1f)) { Text("Офлайн") }
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            if (local == null || update) TextButton(onClick = { model.downloadSubject(subject.id) }, enabled = release != null) {
                                Text((if (update) "Навсозӣ · " else "Боргирӣ · ") + storageSize(release?.packBytes ?: 0))
                            }
                            if (local != null) TextButton(onClick = { removeId = subject.id }) {
                                Text("Ҳазфи боргирӣ", color = Muted)
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            Text("Ҳар санҷиш 25 савол дорад. Фанҳои умумӣ як бор боргирӣ мешаванд. Матн ва тасвирҳои санҷиши онлайн пеш аз оғоз омода мешаванд.",
                color = Muted, fontSize = 13.sp, lineHeight = 21.sp)
            Spacer(Modifier.height(32.dp))
        }
    }
    if (removeId != null) AlertDialog(
        onDismissRequest = { removeId = null },
        title = { Text("Файли фанро ҳазф мекунед?") },
        text = { Text("Барои истифодаи офлайн онро аз нав боргирӣ кардан лозим мешавад.") },
        confirmButton = { TextButton(onClick = {
            removeId?.let(model::removeSubject); removeId = null
        }) { Text("Ҳазф кардан", color = Red) } },
        dismissButton = { TextButton(onClick = { removeId = null }) { Text("Бекор кардан") } }
    )
}

@Composable private fun QuizScreen(model: PrepViewModel, back: () -> Unit) {
    val session = model.session ?: return
    val question = model.question ?: return
    val answered = session.selected >= 0
    val correct = session.selected == question.correct
    val scroll = rememberScrollState()
    LaunchedEffect(question.id) { scroll.scrollTo(0) }
    Column(Modifier.fillMaxSize()) {
        PageHeader(model.subject.title, back, close = true) { Pill("${session.index+1} / 25", Muted, Color.White) }
        LinearProgressIndicator(progress = { (session.index+1)/25f }, color = Green, trackColor = Line,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp).height(4.dp).clip(CircleShape))
        Column(Modifier.weight(1f).verticalScroll(scroll).padding(24.dp)) {
            Text("САВОЛИ ${session.index+1}", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 1.5.sp)
            Spacer(Modifier.height(16.dp))
            if (question.prompt.visual) {
                Surface(color = Color.White, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        FragmentView(question.prompt, prompt = true)
                        Spacer(Modifier.height(10.dp))
                        Text("Барои калон кардан пахш кунед", color = Muted, fontSize = 11.sp)
                    }
                }
            } else Text(question.prompt.text, style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(12.dp))
            Text("Намунаи ММТ ${model.attemptYear} · № ${question.number} · саҳ. ${question.page}", fontSize = 11.sp, color = Muted)
            Spacer(Modifier.height(24.dp))
            Text(if (answered) "Натиҷаи ҷавоби шумо" else "Як ҷавобро интихоб кунед", fontSize = 13.sp, color = Muted)
            Spacer(Modifier.height(12.dp))
            question.options.forEachIndexed { index, option ->
                val good = answered && index == question.correct
                val bad = answered && index == session.selected && !correct
                val accent = if (good) Green else if (bad) Red else Ink
                val background = if (good) SoftGreen else if (bad) SoftRed else Color.White
                Surface(color = background, shape = RoundedCornerShape(16.dp), border = BorderStroke(if (good || bad) 1.5.dp else 1.dp, if (good || bad) accent else Line),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp)
                        .clip(RoundedCornerShape(16.dp)).clickable(enabled = !answered, role = Role.RadioButton) { model.answer(index) }) {
                    Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        Box(Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(if (good || bad) accent else Paper), contentAlignment = Alignment.Center) {
                            Text("ABCD"[index].toString(), color = if (good || bad) Color.White else Muted, fontWeight = FontWeight.SemiBold)
                        }
                        Column(Modifier.weight(1f)) {
                            if (option.visual) Surface(color = Color.White, shape = RoundedCornerShape(5.dp)) {
                                Box(Modifier.padding(4.dp)) { FragmentView(option, prompt = false) }
                            } else Text(option.text, fontSize = 17.sp, lineHeight = 25.sp, color = accent)
                            if (good || bad) { Spacer(Modifier.height(3.dp)); Text(if (good) "Ҷавоби дуруст" else "Ҷавоби шумо", color = accent, fontSize = 11.sp) }
                        }
                        if (good || bad) Icon(if (good) Icons.Default.Check else Icons.Default.Close, if (good) "Дуруст" else "Нодуруст", tint = accent, modifier = Modifier.size(20.dp))
                    }
                }
            }
            if (answered) {
                Spacer(Modifier.height(10.dp))
                Text(if (correct) "Офарин, ҷавоби дуруст!" else "Ҷавоби дуруст: ${"ABCD"[question.correct]}", color = if (correct) Green else Red, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                Text(if (correct) "Ба саволи навбатӣ гузаред." else "Хато ҳам як қадами омӯзиш аст.", fontSize = 13.sp, color = Muted)
            }
            Spacer(Modifier.height(8.dp))
        }
        Surface(color = Paper) {
            Column(Modifier.padding(horizontal = 24.dp, vertical = 16.dp)) {
                Button(onClick = model::next, enabled = answered, shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp), contentPadding = PaddingValues(16.dp)) {
                    Text(if (session.index == 24) "Дидани натиҷа" else "Саволи навбатӣ", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.width(8.dp)); Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null)
                }
            }
        }
    }
}

@Composable private fun FragmentView(fragment: Fragment, prompt: Boolean) {
    var zoom by remember(fragment.image) { mutableStateOf(false) }
    val bitmap by key(fragment.image) {
        produceState<android.graphics.Bitmap?>(null) {
            value = withContext(Dispatchers.IO) {
                runCatching { java.io.File(fragment.image).inputStream().use { BitmapFactory.decodeStream(it) } }.getOrNull()
            }
        }
    }
    val loaded = bitmap
    if (loaded == null) {
        Text("Боркунӣ…", color = Muted, modifier = Modifier.padding(8.dp))
    } else {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val natural = (fragment.width / 2.4f * 1.15f).dp
            val displayWidth = minOf(natural, maxWidth)
            Image(loaded.asImageBitmap(), contentDescription = if (fragment.text.contains("cid:")) "Формулаи математикӣ" else fragment.text,
                contentScale = ContentScale.Fit,
                modifier = Modifier.width(displayWidth).aspectRatio(fragment.width.toFloat()/fragment.height)
                    .then(if (prompt) Modifier.clickable { zoom = true } else Modifier))
        }
        if (zoom) Dialog(onDismissRequest = { zoom = false }) {
            Surface(shape = RoundedCornerShape(20.dp), color = Color.White) {
                Column(Modifier.padding(16.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("Матни савол", modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                        IconButton(onClick = { zoom = false }) { Icon(Icons.Default.Close, "Пӯшидан") }
                    }
                    Text("Барои дидани пурра ба тарафҳо ҳаракат кунед.", fontSize = 12.sp, color = Muted)
                    Spacer(Modifier.height(16.dp))
                    Box(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()).horizontalScroll(rememberScrollState())) {
                        Image(loaded.asImageBitmap(), fragment.text, modifier = Modifier.width(maxOf(560.dp, (fragment.width/2f).dp)).aspectRatio(fragment.width.toFloat()/fragment.height))
                    }
                }
            }
        }
    }
}

@Composable private fun ResultScreen(model: PrepViewModel) {
    val score = model.score
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Brand(); Pill("АНҶОМ ЁФТ")
        }
        Spacer(Modifier.height(40.dp))
        Text("Як қадам ба пеш!", style = MaterialTheme.typography.headlineLarge, textAlign = TextAlign.Center)
        Spacer(Modifier.height(10.dp))
        Text(model.subject.title, color = Muted)
        Spacer(Modifier.height(32.dp))
        Box(Modifier.size(196.dp), contentAlignment = Alignment.Center) {
            CircularProgressIndicator(progress = { score/25f }, modifier = Modifier.fillMaxSize(), strokeWidth = 10.dp, color = Green, trackColor = Line, strokeCap = StrokeCap.Round)
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("$score", fontSize = 58.sp, fontWeight = FontWeight.Bold, color = Ink)
                Text("аз 25 дуруст", color = Muted, fontSize = 14.sp)
            }
        }
        Spacer(Modifier.height(32.dp))
        Surface(color = Color.White, shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, Line), modifier = Modifier.fillMaxWidth()) {
            Row(Modifier.padding(22.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                Stat("$score", "Дуруст", Green)
                Stat("${25-score}", "Нодуруст", Red)
                Stat("${score*4}%", "Натиҷа", Ink)
            }
        }
        Spacer(Modifier.height(24.dp))
        Text(if (score >= 20) "Омодагии хуб! Ҳамин тавр идома диҳед." else "Ҳар кӯшиш дониши шуморо бештар мекунад.", textAlign = TextAlign.Center, color = Muted)
        Spacer(Modifier.height(32.dp))
        Button(onClick = { model.start() }, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
            Icon(Icons.Default.Refresh, null); Spacer(Modifier.width(10.dp)); Text("Аз нав санҷидан", fontSize = 16.sp)
        }
        TextButton(onClick = model::leaveQuiz, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Интихоби фани дигар") }
        TextButton(onClick = model::home) { Text("Ба саҳифаи асосӣ", color = Muted) }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable private fun Stat(value: String, label: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontSize = 25.sp, fontWeight = FontWeight.Bold, color = color)
        Text(label, fontSize = 12.sp, color = Muted)
    }
}
