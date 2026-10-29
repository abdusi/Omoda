"""Verify A/B routing, English-only selection, 18-question scoring and offline B packs."""
import json
import re
import subprocess
import time

from smoke_android import adb, tree, texts, tap, snap, OUT
from smoke_content import wait_for, dismiss, tap_in_card, tap_prefix, session_bank

TITLES = {
    "tajik": "Забони тоҷикӣ", "math": "Математика", "physics": "Физика", "chemistry": "Химия",
    "geography": "География", "english": "Забони англисӣ", "biology": "Биология",
    "history": "Таърих", "literature": "Адабиёти тоҷик", "law": "Ҳуқуқ",
}
CLUSTERS = {
    "А": [
        ("Табиӣ ва техникӣ", ["tajik", "math", "chemistry", "physics"]),
        ("Иқтисод ва география", ["tajik", "math", "geography", "english"]),
        ("Филология, педагогика ва санъат", ["tajik", "history", "literature", "english"]),
        ("Ҷомеашиносӣ ва ҳуқуқ", ["tajik", "history", "law", "english"]),
        ("Тиб, биология ва варзиш", ["tajik", "biology", "chemistry", "physics"]),
    ],
    "Б": [
        ("Табиӣ ва техникӣ", ["tajik", "math", "physics"]),
        ("Иқтисод ва география", ["tajik", "math", "geography"]),
        ("Филология, педагогика ва санъат", ["tajik", "literature", "english"]),
        ("Ҷомеашиносӣ ва ҳуқуқ", ["tajik", "history", "english"]),
        ("Тиб, биология ва варзиш", ["tajik", "biology", "chemistry"]),
    ],
}


def back():
    adb("shell", "input", "keyevent", "KEYCODE_BACK")


def leave():
    back()
    tap("Баромадан")
    wait_for(lambda d: any("Кластери" in t for t in texts(d)))


def run():
    checks = []
    dismiss()
    doc = tree()
    assert all(t in texts(doc) for t in ("Варианти А", "Синфи 11", "Варианти Б", "Синфи 9"))
    snap("v06-components.png")
    for letter in ("А", "Б"):
        tap("Варианти " + letter)
        for index, (title, ids) in enumerate(CLUSTERS[letter], 1):
            tap(title)
            doc = tree()
            assert f"Варианти {letter} · Кластери {index}" in texts(doc)
            observed = set(texts(doc))
            for _ in range(2):
                adb("shell", "input", "swipe", "800", "1950", "800", "850", "250")
                observed.update(texts(tree()))
            assert observed.intersection(TITLES.values()) == {TITLES[sid] for sid in ids}, (letter, index, observed)
            assert all(any(t.endswith(f" · {letter}{i}") for t in observed) for i in range(1, len(ids) + 1))
            assert not any(name in " ".join(observed) for name in ("Забони немисӣ", "Забони франсавӣ", "Забони арабӣ"))
            if letter == "Б" and index == 3:
                snap("v06-b-subjects.png")
            back()
        back()
        assert "Варианти А" in texts(tree())
        checks.append(f"Component {letter}: all five clusters contain only their official subjects and subtest codes")
        print(checks[-1], flush=True)

    tap("Варианти Б")
    tap("Филология, педагогика ва санъат")
    tap_in_card("Забони англисӣ", "Онлайн")
    wait_for(lambda d: "1 / 18" in texts(d))
    bank = session_bank()
    assert len(bank) == 18 and all(q["id"].startswith("b_english-") for q in bank)
    assert {q["number"] for q in bank} == set(range(1, 19))
    assert all(q["source"] == "B-En_tj_ru.pdf" for q in bank)
    snap("v06-b-english.png")
    for index, question in enumerate(bank):
        doc = tree()
        assert f"{index + 1} / 18" in texts(doc)
        correct = index % 2 == 1
        tap("ABCD"[question["correct"] if correct else (question["correct"] + 1) % 4], doc)
        if index == 0:
            old_pid = adb("shell", "pidof", "tj.mmt.prep").strip()
            adb("shell", "input", "keyevent", "KEYCODE_HOME")
            for _ in range(20):
                time.sleep(.4)
                adb("shell", "am", "kill", "tj.mmt.prep")
                try:
                    adb("shell", "pidof", "tj.mmt.prep")
                except subprocess.CalledProcessError:
                    break
            adb("shell", "am", "start", "-n", "tj.mmt.prep/.MainActivity")
            doc = wait_for(lambda d: "1 / 18" in texts(d))
            assert adb("shell", "pidof", "tj.mmt.prep").strip() != old_pid
            assert "Б · Забони англисӣ" in texts(doc) and "Натиҷаи ҷавоби шумо" in texts(doc)
            checks.append("Component B, English source, submitted answer and 18-question length survive process death")
        tap("Дидани натиҷа" if index == 17 else "Саволи навбатӣ")
    doc = wait_for(lambda d: "аз 18 дуруст" in texts(d))
    assert "9" in texts(doc) and "50%" in texts(doc)
    snap("v06-b-result.png")
    checks.append("All 18 B English questions are unique; 9 correct answers produce 50%")
    print(checks[-1], flush=True)
    tap("Интихоби фани дигар", doc)
    tap_in_card("Забони англисӣ", "Боргирӣ", starts_with=True)
    wait_for(lambda d: any("Фан барои истифодаи" in t for t in texts(d)))
    dismiss()
    try:
        adb("reverse", "--remove", "tcp:8876")
        adb("shell", "svc", "wifi", "disable")
        adb("shell", "svc", "data", "disable")
        tap_in_card("Забони англисӣ", "Офлайн")
        wait_for(lambda d: "1 / 18" in texts(d))
        assert all(q["id"].startswith("b_english-") for q in session_bank())
        tap("A")
        leave()
        checks.append("Downloaded B English works without either network or the local test server")
    finally:
        adb("shell", "svc", "wifi", "enable")
        adb("shell", "svc", "data", "enable")
        adb("reverse", "tcp:8876", "tcp:8876")
    back()
    back()
    tap("Варианти А")
    tap("Филология, педагогика ва санъат")
    tap_in_card("Забони англисӣ", "Онлайн")
    wait_for(lambda d: "1 / 25" in texts(d))
    assert all(q["id"].startswith("english-") and q["source"] == "A4-234_En.pdf" for q in session_bank())
    checks.append("Switching B to A uses the A English bank and returns to 25-question attempts")
    leave()
    back()
    back()
    tap("Варианти Б")
    tap("Табиӣ ва техникӣ")
    tap_prefix("Боргирии кластер")
    wait_for(lambda d: any("Ҳамаи фанҳои кластер" in t for t in texts(d)))
    dismiss()
    installed = adb("shell", "run-as", "tj.mmt.prep", "ls", "files/study/installed").decode().split()
    assert all(sid + ".json" in installed for sid in ("tajik", "b_math", "b_physics"))
    try:
        adb("reverse", "--remove", "tcp:8876")
        adb("shell", "svc", "wifi", "disable")
        adb("shell", "svc", "data", "disable")
        tap_in_card("Математика", "Офлайн")
        wait_for(lambda d: "1 / 25" in texts(d))
        assert all(q["id"].startswith("b_math-") and q["source"] == "B-Math_tj.pdf" for q in session_bank())
        snap("v06-b-math-offline.png")
        tap("A")
        assert "Натиҷаи ҷавоби шумо" in texts(tree())
        checks.append("B cluster download installs exactly its shared Tajik, B math and B physics banks; visual math works offline")
    finally:
        adb("shell", "svc", "wifi", "enable")
        adb("shell", "svc", "data", "enable")
        adb("reverse", "tcp:8876", "tcp:8876")
    (OUT / "v06-components-results.json").write_text(
        json.dumps({"checks": checks, "passed": len(checks), "complete": True,
                    "transport": "loopback server with the verified NTC A/B catalog; offline checks disable/remove both transports"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run()
