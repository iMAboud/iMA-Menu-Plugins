item(
    where=sel.file.name == 'organize_undo.log'
    type='file'
    title='Undo Organize'
    cmd='"@app.dir\plugins\organize\organize.exe"'
    args='--undo @sel(true)'
    image=\uE10A
)
item(
    where=path.exists(path.combine(dir, 'organize_undo.log'))
    type='back.dir'
    title='Undo Organize'
    cmd='"@app.dir\plugins\organize\organize.exe"'
    args='--undo "@dir\organize_undo.log"'
    image=\uE10A
)
item(
    where=sel.file.name != 'organize_undo.log'
    type='file|dir'
    mode='multiple'
    title='Organize Files'
    cmd='"@app.dir\plugins\organize\organize.exe"'
    args='@if(sel.count, sel(true), quote(dir))'
    image=\uE290
)