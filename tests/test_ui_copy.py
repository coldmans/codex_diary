import json
from pathlib import Path
import re
import shutil
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
UI_COPY_JS = ROOT / "codex_diary" / "ui" / "ui_copy.js"
UI_COPY_EXTRA_JS = ROOT / "codex_diary" / "ui" / "ui_copy_extra.js"
APP_JS = ROOT / "codex_diary" / "ui" / "app.js"


class UiCopyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is required to evaluate UI copy files")
    def test_all_supported_output_languages_have_complete_ui_copy(self) -> None:
        script = textwrap.dedent(
            f"""
            const fs = require("fs");
            const vm = require("vm");

            const sandbox = {{ window: {{}} }};
            vm.createContext(sandbox);

            for (const file of {json.dumps([str(UI_COPY_JS), str(UI_COPY_EXTRA_JS)])}) {{
              const code = fs.readFileSync(file, "utf8");
              vm.runInContext(code, sandbox, {{ filename: file }});
            }}

            const copy = sandbox.window.CODEX_DIARY_UI_COPY;
            const baseKeys = Object.keys(copy.en);
            const summary = {{}};

            for (const [lang, entries] of Object.entries(copy)) {{
              const keys = Object.keys(entries);
              summary[lang] = {{
                count: keys.length,
                missing: baseKeys.filter((key) => !(key in entries)),
                extra: keys.filter((key) => !baseKeys.includes(key)),
              }};
            }}

            console.log(JSON.stringify(summary));
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        summary = json.loads(result.stdout)
        expected_languages = self._supported_output_languages_from_app_js()

        self.assertEqual(set(summary.keys()), expected_languages)
        self.assertGreaterEqual(summary["en"]["count"], 180)

        for lang in sorted(expected_languages):
            with self.subTest(language=lang):
                self.assertEqual(summary[lang]["missing"], [])
                self.assertEqual(summary[lang]["extra"], [])
                self.assertEqual(summary[lang]["count"], summary["en"]["count"])

    def _supported_output_languages_from_app_js(self) -> set[str]:
        text = APP_JS.read_text(encoding="utf-8")
        return set(re.findall(r'key: "([a-z]{2})"', text))


if __name__ == "__main__":
    unittest.main()
