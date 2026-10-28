"""End-to-end content smoke test on an emulator; restores Wi-Fi/mobile data on exit."""
import json
import re
import subprocess
import time
from pathlib import Path

from smoke_android import adb, tree, texts, tap, snap, ROOT, OUT


def wait_for(predicate, timeout=900):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        doc = tree()
        observed = texts(doc)
        if any("Амалиёт иҷро нашуд" in t for t in observed):
            raise AssertionError(observed)
        if predicate(doc):
            return doc
        time.sleep(.4)
    raise AssertionError("Timed out waiting for content operation")


def tap_prefix(prefix):
    doc = tree()
    value = next(t for t in texts(doc) if t.startswith(prefix))
    tap(value, doc)


def dismiss():
    doc = tree()
    if "Фаҳмо" in texts(doc):
        tap("Фаҳмо", doc)


def tap_in_card(title, label):
    for _ in range(8):
        doc = tree()
        parents = {child: parent for parent in doc.iter() for child in parent}
        heading = next((n for n in doc.iter("node") if n.get("text") == title), None)
        if heading is not None:
            card = heading
            while card in parents:
                card = parents[card]
                target = next((n for n in card.iter("node") if n.get("text") == label), None)
                if target is not None:
                    while target.get("clickable") != "true" and target in parents:
                        target = parents[target]
                    bounds = list(map(int, re.findall(r"\d+", target.get("bounds", ""))))
                    if len(bounds) == 4 and bounds[3] > bounds[1] and bounds[3] < 2250:
                        assert target.get("enabled") == "true"
                        adb("shell", "input", "tap", str((bounds[0] + bounds[2]) // 2), str((bounds[1] + bounds[3]) // 2))
                        return
                    break
        adb("shell", "input", "swipe", "800", "1950", "800", "900", "250")
    raise AssertionError((title, label))


def session_bank():
    name = adb("shell", "run-as", "tj.mmt.prep", "cat", "files/study/session.txt").decode().strip()
    return json.loads(adb("shell", "run-as", "tj.mmt.prep", "cat",
                         f"files/study/sessions/{name}/bank.json").decode())


def leave():
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    tap("Баромадан")
    wait_for(lambda doc: "Кластери 4" in texts(doc))


def run(download_only=False):
    checks = []
    if download_only:
        checkpoints = json.loads((OUT / "v05-content-results.json").read_text("utf-8"))
        checks = checkpoints["checks"]
        verify_downloads(checks)
        return
    # Start with the app on the cluster screen; do not clear user/app data.
    dismiss()
    tap("Ҷомеашиносӣ ва ҳуқуқ")
    tap_in_card("Забони тоҷикӣ", "Онлайн")
    doc = wait_for(lambda d: "1 / 25" in texts(d))
    bank = session_bank()
    assert len(bank) == len({q["id"] for q in bank}) == 25
    snap("v05-online-question.png")
    checks.append("Online session fetches and persists exactly 25 unique questions")
    expected_score = 0
    for index, question in enumerate(bank):
        doc = tree()
        assert f"{index + 1} / 25" in texts(doc)
        assert any(f"№ {question['number']} ·" in t for t in texts(doc))
        correct = index % 2 == 1
        option = question["correct"] if correct else (question["correct"] + 1) % 4
        tap("ABCD"[option], doc)
        expected_score += correct
        if index == 0:
            doc = tree()
            source = next(t for t in texts(doc) if t.startswith("Намунаи ММТ"))
            old_pid = adb("shell", "pidof", "tj.mmt.prep").strip()
            adb("shell", "input", "keyevent", "KEYCODE_HOME")
            killed = False
            for _ in range(20):
                time.sleep(.4)
                adb("shell", "am", "kill", "tj.mmt.prep")
                try:
                    adb("shell", "pidof", "tj.mmt.prep")
                except subprocess.CalledProcessError:
                    killed = True
                    break
            assert killed, "Emulator did not terminate the background process"
            adb("shell", "am", "start", "-n", "tj.mmt.prep/.MainActivity")
            doc = wait_for(lambda d: "1 / 25" in texts(d))
            assert old_pid != adb("shell", "pidof", "tj.mmt.prep").strip()
            assert source in texts(doc) and "Натиҷаи ҷавоби шумо" in texts(doc)
            checks.append("Question order and submitted answer survive process death")
        tap("Дидани натиҷа" if index == 24 else "Саволи навбатӣ")
    doc = wait_for(lambda d: "аз 25 дуруст" in texts(d))
    assert str(expected_score) in texts(doc) and f"{expected_score * 4}%" in texts(doc)
    snap("v05-result.png")
    checks.append(f"Full online attempt scores {expected_score}/25 correctly")
    save(checks, complete=False)
    tap("Интихоби фани дигар", doc)
    tap_prefix("Боргирии кластер")
    verify_downloads(checks)


def verify_downloads(checks):
    wait_for(lambda d: any("Ҳамаи фанҳои кластер" in t for t in texts(d)))
    dismiss()
    installed = adb("shell", "run-as", "tj.mmt.prep", "ls", "files/study/installed").decode().split()
    assert all(f"{sid}.json" in installed for sid in ("tajik", "history", "law", "english"))
    checks.append("Entire cluster downloads and installs all four subject packages")
    snap("v05-downloaded.png")
    try:
        adb("shell", "svc", "wifi", "disable")
        adb("shell", "svc", "data", "disable")
        time.sleep(1)
        tap_in_card("Таърих", "Офлайн")
        doc = wait_for(lambda d: "1 / 25" in texts(d))
        offline = session_bank()
        assert len(offline) == 25
        assert any(f["visual"] for q in offline for f in [q["prompt"], *q["options"]])
        assert "Боркунӣ…" not in texts(doc)
        snap("v05-offline-history.png")
        tap("A", doc)
        checks.append("Downloaded history starts and checks answers with Wi-Fi/mobile data disabled")
        leave()
        # Back to the top of the subject list.
        adb("shell", "input", "swipe", "800", "650", "800", "2000", "300")
        tap_in_card("Забони тоҷикӣ", "Ҳазфи боргирӣ")
        tap("Ҳазф кардан")
        wait_for(lambda d: any("Файли фан аз дастгоҳ" in t for t in texts(d)))
        dismiss()
        installed = adb("shell", "run-as", "tj.mmt.prep", "ls", "files/study/installed").decode().split()
        assert "tajik.json" not in installed and "history.json" in installed
        checks.append("Removing one downloaded subject preserves other installed subjects")
    finally:
        adb("shell", "svc", "wifi", "enable")
        adb("shell", "svc", "data", "enable")
    save(checks, complete=True)
    print(json.dumps(checks, ensure_ascii=False), flush=True)


def save(checks, complete):
    (OUT / "v05-content-results.json").write_text(
        json.dumps({"checks": checks, "passed": len(checks), "complete": complete},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-only", action="store_true", help="Resume the download stage using a saved online checkpoint")
    run(parser.parse_args().download_only)
