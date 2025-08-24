item(title="Add Exclusion"  
     type="file|dir|back.dir|drive" 
     menu='manage'
     image=\uE194
     admin  
     cmd='powershell.exe'  
     args='-NoProfile -ExecutionPolicy Bypass -Command "Add-MpPreference -ExclusionPath \"@sel.path\""'  
     window=show)