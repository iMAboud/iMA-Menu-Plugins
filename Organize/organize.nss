item(  
    where=if(sel.back, path.exists(path.combine(dir, 'organize_undo.log')), sel.file.name == 'organize_undo.log')  
    type='file|back.dir'  
    title='Undo Organize'  
    cmd='"@app.dir\plugins\organize\organize.exe"'  
    args=if(sel.back, '--undo "@dir\organize_undo.log"', '--undo @sel(true)')  
    image=\uE1B2 
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