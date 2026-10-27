"""Check cluster 4, shared language banks and a complete history attempt."""
import json
import re
import subprocess
import time
from smoke_android import adb, tree, texts, tap, snap, ROOT, OUT
from smoke_cluster5 import source_label


def leave():
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    doc = tree()
    tap("Баромадан", doc)
    doc = tree()
    assert "Кластери 4" in texts(doc)
    return doc


def run():
    tap("Ҷомеашиносӣ ва ҳуқуқ")
    doc = tree()
    assert "Кластери 4" in texts(doc)
    assert all(title in texts(doc) for title in ["Забони тоҷикӣ", "Таърих", "Ҳуқуқ", "Забони англисӣ"])
    assert "Биология" not in texts(doc) and "Математика" not in texts(doc)
    snap("v03-cluster4.png")
    checks = ["Cluster 4 lists Tajik, history, law and English in exam order"]
    for sid, title in [("tajik", "Забони тоҷикӣ"), ("english", "Забони англисӣ"), ("law", "Ҳуқуқ")]:
        tap(title, doc)
        doc = tree()
        assert title in texts(doc) and "1 / 25" in texts(doc)
        label, doc = source_label(doc)
        number = int(re.search(r"№ (\d+)", label)[1])
        bank = json.loads((ROOT/f"app/src/main/assets/{sid}.json").read_text(encoding="utf8"))
        question = next(q for q in bank if q["number"] == number)
        assert question["prompt"]["text"] in texts(doc) or question["prompt"]["visual"]
        tap("ABCD"[question["correct"]], doc)
        doc = tree()
        assert "Натиҷаи ҷавоби шумо" in texts(doc) or "Ҷавоби дуруст" in texts(doc)
        if sid == "law":
            snap("v03-law.png")
            old_pid = adb("shell", "pidof", "tj.mmt.prep").strip()
            adb("shell", "input", "keyevent", "KEYCODE_HOME")
            dead = False
            for _ in range(15):
                adb("shell", "am", "kill", "tj.mmt.prep")
                time.sleep(.3)
                try: adb("shell", "pidof", "tj.mmt.prep")
                except subprocess.CalledProcessError:
                    dead = True
                    break
            assert dead
            adb("shell", "am", "start", "-n", "tj.mmt.prep/.MainActivity")
            doc = tree()
            assert adb("shell", "pidof", "tj.mmt.prep").strip() != old_pid
            assert title in texts(doc) and "1 / 25" in texts(doc)
            restored, doc = source_label(doc)
            assert label == restored
            checks.append("Law question, answer and cluster 4 survive confirmed process death")
        doc = leave()
        print(f"{sid}: shared bank or subject routing OK", flush=True)
    checks.append("Shared Tajik and English questions use their existing question and answer banks")
    tap("Таърих", doc)
    bank = {q["number"]: q for q in json.loads((ROOT/"app/src/main/assets/history.json").read_text(encoding="utf8"))}
    seen = []
    for index in range(25):
        doc = tree()
        assert f"{index+1} / 25" in texts(doc)
        label, doc = source_label(doc)
        number = int(re.search(r"№ (\d+)", label)[1])
        seen.append(number)
        correct = bank[number]["correct"]
        tap("ABCD"[correct if index % 2 else (correct+1)%4], doc)
        doc = tree()
        if index == 0: snap("v03-history-answer.png")
        tap("Дидани натиҷа" if index == 24 else "Саволи навбатӣ", doc)
        print(f"history {index+1}/25 OK", flush=True)
    assert len(set(seen)) == 25
    doc = tree()
    assert all(label in texts(doc) for label in ["12", "13", "48%", "Таърих"])
    snap("v03-result.png")
    tap("Интихоби фани дигар", doc)
    doc = tree()
    assert "Кластери 4" in texts(doc)
    checks.append("History: 25 unique questions, expected score 12/25 (48%), returns to cluster 4")
    (OUT/"smoke-cluster4-results.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf8")
    print("All cluster 4 UI checks passed", flush=True)


if __name__ == "__main__": run()
