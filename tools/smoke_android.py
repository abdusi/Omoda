"""Manual/emulator UI smoke test; requires an already running emulator and installed APK.
Runs only against tj.mmt.prep. Captures previews and checks a full 25-item attempt.
"""
import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADB = str(Path(os.environ.get("ANDROID_HOME", str(Path.home()/"AppData/Local/Android/Sdk"))) / "platform-tools/adb.exe")
DEVICE = os.environ.get("ANDROID_SERIAL", "emulator-5554")
OUT = ROOT / "preview"
OUT.mkdir(exist_ok=True)

def adb(*args):
    return subprocess.check_output([ADB, "-s", DEVICE, *args])

def tree():
    for _ in range(4):
        result = adb("shell", "uiautomator", "dump", "/sdcard/omoda-ui.xml")
        if b"UI hierchary dumped" not in result:
            time.sleep(.3)
            continue
        doc = ET.fromstring(adb("shell", "cat", "/sdcard/omoda-ui.xml"))
        if any(n.get("package") == "tj.mmt.prep" for n in doc.iter("node")):
            return doc
    raise AssertionError("No fresh app hierarchy")

def texts(doc):
    return [n.get("text", "") for n in doc.iter("node")]

def tap(text, doc=None):
    for attempt in range(5):
        doc = doc if doc is not None else tree()
        parents = {c:p for p in doc.iter() for c in p}
        found = next((n for n in doc.iter("node") if n.get("text") == text or n.get("content-desc") == text), None)
        if found is not None:
            target = found
            while target.get("clickable") != "true" and target in parents:
                target = parents[target]
            assert target.get("enabled") == "true", f"Disabled: {text}"
            x0, y0, x1, y1 = map(int, re.findall(r"\d+", target.get("bounds")))
            if y0 < 2180 and y1 > y0:
                adb("shell", "input", "tap", str((x0+x1)//2), str((y0+min(y1,2180))//2))
                return
        adb("shell", "input", "swipe", "800", "1950", "800", "850", "250")
        doc = None
    raise AssertionError(f"Cannot find {text}")

def snap(name):
    (OUT/name).write_bytes(adb("exec-out", "screencap", "-p"))

def run():
    checks = []
    doc = tree()
    tap("Иқтисод ва география", doc)
    doc = tree()
    assert all(s in texts(doc) for s in ["Забони тоҷикӣ", "Математика", "География", "Забони англисӣ"])
    snap("02-subjects.png")
    tap("Забони тоҷикӣ", doc)
    bank = {q["number"]:q for q in json.loads((ROOT/"app/src/main/assets/tajik.json").read_text(encoding="utf8"))}
    seen, expected_score = [], 0
    for i in range(25):
        doc = tree()
        assert f"{i+1} / 25" in texts(doc)
        source = next(t for t in texts(doc) if "Намунаи ММТ 2026" in t)
        number = int(re.search(r"№ (\d+)", source)[1])
        seen.append(number)
        q = bank[number]
        expected_correct = i % 2 == 1
        option = q["correct"] if expected_correct else (q["correct"]+1)%4
        if i == 0:
            button = next(n for n in doc.iter("node") if n.get("text") == "Саволи навбатӣ")
            parents = {c:p for p in doc.iter() for c in p}
            while button.get("clickable") != "true": button = parents[button]
            assert button.get("enabled") == "false"
            snap("03-question.png")
        tap("ABCD"[option], doc)
        doc = tree()
        observed = set(texts(doc))
        required = {"Ҷавоби дуруст"} | ({"Ҷавоби шумо"} if not expected_correct else set())
        if not required.issubset(observed):
            adb("shell", "input", "swipe", "800", "850", "800", "1950", "250")
            doc = tree()
            observed.update(texts(doc))
        if not required.issubset(observed):
            adb("shell", "input", "swipe", "800", "1950", "800", "850", "250")
            doc = tree()
            observed.update(texts(doc))
        assert required.issubset(observed), (i+1, observed)
        if expected_correct:
            expected_score += 1
        else:
            assert "Ҷавоби шумо" in observed
        if i == 0:
            snap("04-wrong-answer.png")
            # A different answer card cannot be selected after submission.
            target = next(n for n in doc.iter("node") if n.get("text") == "ABCD"[q["correct"]])
            x0,y0,x1,y1 = map(int,re.findall(r"\d+", target.get("bounds")))
            adb("shell", "input", "tap", str((x0+x1)//2), str((y0+y1)//2))
            doc = tree()
            assert "Ҷавоби шумо" in texts(doc)
            checks.append("Answer stays locked after submission; next disabled before answer")
            # Put app in background, kill process, reopen the existing task.
            old_pid = adb("shell", "pidof", "tj.mmt.prep").strip()
            adb("shell", "input", "keyevent", "KEYCODE_HOME")
            killed = False
            for _ in range(15):
                adb("shell", "am", "kill", "tj.mmt.prep")
                time.sleep(.3)
                try:
                    adb("shell", "pidof", "tj.mmt.prep")
                except subprocess.CalledProcessError:
                    killed = True
                    break
            assert killed, "Could not confirm process death"
            adb("shell", "am", "start", "-n", "tj.mmt.prep/.MainActivity")
            doc = tree()
            assert adb("shell", "pidof", "tj.mmt.prep").strip() != old_pid
            assert source in texts(doc) and "Ҷавоби шумо" in texts(doc)
            checks.append("Question, order and submitted answer survive process recreation")
        if i == 1: snap("05-correct-answer.png")
        tap("Дидани натиҷа" if i == 24 else "Саволи навбатӣ", doc)
        print(f"Question {i+1}/25 OK", flush=True)
    assert len(set(seen)) == 25
    doc = tree()
    assert "12" in texts(doc) and "13" in texts(doc) and "48%" in texts(doc), texts(doc)
    snap("06-result.png")
    checks.append("25 unique questions; correct and incorrect feedback; final score 12/25 = 48%")
    tap("Аз нав санҷидан", doc)
    doc = tree()
    assert "1 / 25" in texts(doc) and "Ҷавоби шумо" not in texts(doc)
    checks.append("Restart creates an unanswered new attempt")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    doc = tree()
    assert "Аз санҷиш мебароед?" in texts(doc)
    tap("Баромадан", doc)
    doc = tree()
    tap("Математика", doc)
    doc = tree()
    assert "1 / 25" in texts(doc)
    snap("07-math.png")
    checks.append("Exit confirmation and math subject open correctly")
    (OUT/"smoke-results.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf8")
    print("All emulator smoke checks passed", flush=True)

if __name__ == "__main__": run()
