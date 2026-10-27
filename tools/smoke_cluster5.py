"""Exercise cluster routing, science subjects, answer feedback and restoration."""
import json
import re
import subprocess
import time
from smoke_android import adb, tree, texts, tap, snap, ROOT, OUT


def source_label(doc):
    for _ in range(4):
        label = next((t for t in texts(doc) if "Намунаи ММТ 2026" in t), None)
        if label:
            return label, doc
        adb("shell", "input", "swipe", "800", "1950", "800", "900", "250")
        doc = tree()
    raise AssertionError("Missing question source")


def leave():
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    doc = tree()
    tap("Баромадан", doc)
    doc = tree()
    assert "Кластери 5" in texts(doc)
    return doc


def run():
    tap("Тиб, биология ва варзиш")
    doc = tree()
    assert "Кластери 5" in texts(doc)
    for title in ["Забони тоҷикӣ", "Биология", "Химия", "Физика"]:
        assert title in texts(doc)
    assert "Математика" not in texts(doc)
    snap("v02-cluster5.png")
    checks = ["Cluster 5 lists Tajik, biology, chemistry and physics only"]
    for sid, title in [("tajik", "Забони тоҷикӣ"), ("chemistry", "Химия"), ("physics", "Физика")]:
        tap(title, doc)
        doc = tree()
        assert title in texts(doc) and "1 / 25" in texts(doc)
        label, doc = source_label(doc)
        number = int(re.search(r"№ (\d+)", label)[1])
        bank = json.loads((ROOT/f"app/src/main/assets/{sid}.json").read_text(encoding="utf8"))
        question = next(q for q in bank if q["number"] == number)
        tap("ABCD"[question["correct"]], doc)
        doc = tree()
        snap(f"v02-{sid}.png")
        assert "Натиҷаи ҷавоби шумо" in texts(doc) or "Ҷавоби дуруст" in texts(doc)
        if sid == "physics":
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
            restored_label, doc = source_label(doc)
            assert restored_label == label
            checks.append("Physics question, answer and cluster 5 survive confirmed process death")
        doc = leave()
        print(f"{sid}: subject and routing OK", flush=True)
    tap("Биология", doc)
    bank = {q["number"]:q for q in json.loads((ROOT/"app/src/main/assets/biology.json").read_text(encoding="utf8"))}
    seen = []
    for index in range(25):
        doc = tree()
        assert f"{index+1} / 25" in texts(doc)
        label, doc = source_label(doc)
        number = int(re.search(r"№ (\d+)", label)[1])
        seen.append(number)
        correct = bank[number]["correct"]
        chosen = correct if index % 2 else (correct+1)%4
        tap("ABCD"[chosen], doc)
        doc = tree()
        if index == 0: snap("v02-biology-answer.png")
        tap("Дидани натиҷа" if index == 24 else "Саволи навбатӣ", doc)
        print(f"biology {index+1}/25 OK", flush=True)
    assert len(set(seen)) == 25
    doc = tree()
    assert all(label in texts(doc) for label in ["12", "13", "48%", "Биология"])
    snap("v02-result.png")
    tap("Интихоби фани дигар", doc)
    doc = tree()
    assert "Кластери 5" in texts(doc)
    checks.append("Biology: 25 unique questions; expected score 12/25, 48%; result returns to cluster 5")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    doc = tree()
    # Returning home may retain scroll position near cluster 5.
    adb("shell", "input", "swipe", "800", "750", "800", "2100", "250")
    tap("Иқтисод ва география")
    doc = tree()
    assert "Кластери 2" in texts(doc) and "Математика" in texts(doc)
    assert "Биология" not in texts(doc)
    tap("Математика", doc)
    doc = tree()
    assert "Математика" in texts(doc) and "1 / 25" in texts(doc)
    snap("v02-math.png")
    checks.append("Cluster 2 still opens its own subject bank after using cluster 5")
    (OUT/"smoke-cluster5-results.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf8")
    print("All cluster 5 UI checks passed", flush=True)


if __name__ == "__main__": run()
