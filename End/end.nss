item(
  type="file|dir"
  title="End Process"
  image=["\uE0BE"]
  vis=key.shift()
  cmd="powershell.exe"
  args='-WindowStyle Hidden -ExecutionPolicy Bypass -File "@app.dir\plugins\end\end.ps1" -Path "@sel.path"'
  window=hidden
)