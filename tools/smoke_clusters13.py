"""Exercise the new clusters, shared banks, and a complete literature attempt."""
import json
import re
import subprocess
import time
from smoke_android import adb, tree, texts, tap, snap, ROOT, OUT
from smoke_cluster5 import source_label


def leave(cluster):
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    tap("Баромадан")
    doc = tree()
    assert f"Кластери {cluster}" in texts(doc)
    return doc


def restore_question(label, title):
    old_pid = adb("shell", "pidof", "tj.mmt.prep").strip()
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    dead = False
    for _ in range(15):
        adb("shell", "am", "kill", "tj.mmt.prep")
        time.sleep(.3)
        try:
            adb("shell", "pidof", "tj.mmt.prep")
        except subprocess.CalledProcessError:
            dead = True
            break
    assert dead, "Test process did not terminate"
    adb("shell", "am", "start", "-n", "tj.mmt.prep/.MainActivity")
    for _ in range(10):
        doc = tree()
        if title in texts(doc) and "1 / 25" in texts(doc):
            break
        time.sleep(.3)
    assert adb("shell", "pidof", "tj.mmt.prep").strip() != old_pid
    assert title in texts(doc) and "1 / 25" in texts(doc)
    restored, doc = source_label(doc)
    assert label == restored
    assert "Натиҷаи ҷавоби шумо" in texts(doc)
    return doc


def run():
    checks = []
    snap("v04-clusters.png")
    for cluster, cluster_title, members in [
        (1, "Табиӣ ва техникӣ", [("tajik", "Забони тоҷикӣ"), ("math", "Математика"),
                                ("chemistry", "Химия"), ("physics", "Физика")]),
        (3, "Филология, педагогика ва санъат", [("tajik", "Забони тоҷикӣ"), ("history", "Таърих"),
                                                  ("literature", "Адабиёти тоҷик"), ("english", "Забони англисӣ")]),
    ]:
        tap(cluster_title)
        doc = tree()
        assert f"Кластери {cluster}" in texts(doc)
        assert all(title in texts(doc) for _, title in members)
        snap(f"v04-cluster{cluster}.png")
        for sid, title in members:
            tap(title, doc)
            doc = tree()
            assert title in texts(doc) and "1 / 25" in texts(doc)
            label, doc = source_label(doc)
            number = int(re.search(r"№ (\d+)", label)[1])
            bank = json.loads((ROOT/f"app/src/main/assets/{sid}.json").read_text(encoding="utf8"))
            question = next(q for q in bank if q["number"] == number)
            tap("ABCD"[question["correct"]], doc)
            doc = tree()
            assert "Натиҷаи ҷавоби шумо" in texts(doc) or "Ҷавоби дуруст" in texts(doc)
            if sid in {"physics", "literature"}:
                doc = restore_question(label, title)
                snap(f"v04-{sid}-restored.png")
                checks.append(f"Cluster {cluster}: {sid} question and answer survive process death")
            doc = leave(cluster)
            print(f"Cluster {cluster}: {sid} routing and answer OK", flush=True)
        checks.append(f"Cluster {cluster}: all four subjects open and check answers using their expected banks")
        if cluster == 1:
            adb("shell", "input", "keyevent", "KEYCODE_BACK")
    tap("Адабиёти тоҷик", doc)
    bank = {q["number"]: q for q in json.loads((ROOT/"app/src/main/assets/literature.json").read_text(encoding="utf8"))}
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
        if index == 0:
            snap("v04-literature-answer.png")
        tap("Дидани натиҷа" if index == 24 else "Саволи навбатӣ", doc)
        print(f"Literature {index+1}/25 OK", flush=True)
    assert len(set(seen)) == 25
    doc = tree()
    assert all(label in texts(doc) for label in ["12", "13", "48%", "Адабиёти тоҷик"])
    snap("v04-result.png")
    tap("Интихоби фани дигар", doc)
    assert "Кластери 3" in texts(tree())
    checks.append("Literature: 25 unique questions, score 12/25 (48%), returns to cluster 3")
    (OUT/"smoke-clusters13-results.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf8")
    print("All cluster 1/3 UI checks passed", flush=True)


if __name__ == "__main__":
    run()
