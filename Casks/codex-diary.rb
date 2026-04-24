cask "codex-diary" do
  version "0.1.0"
  sha256 "8bf5e401c9bc90039c43b619e480e3838183ffcd8a082572ce910f927cab8af4"

  url "https://github.com/coldmans/codex_diary/releases/download/v#{version}/Codex-Diary-#{version}-macOS.dmg",
      verified: "github.com/coldmans/codex_diary/"
  name "Codex Diary"
  desc "Generate diary drafts from Chronicle Markdown summaries"
  homepage "https://github.com/coldmans/codex_diary"

  app "Codex Diary.app"

  caveats <<~EOS
    Codex Diary is currently distributed as an unsigned macOS build.
    If macOS blocks first launch, Control-click the app in Finder and choose Open.
  EOS

  zap trash: [
    "~/Library/Application Support/Codex Diary",
    "~/Library/Caches/io.github.coldmans.codex-diary",
    "~/Library/Preferences/io.github.coldmans.codex-diary.plist",
  ]
end
