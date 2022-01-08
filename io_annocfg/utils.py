
import bpy
from pathlib import Path
from .prefs import IO_AnnocfgPreferences


def data_path_to_absolute_path(path):
    path = Path(path)
    rda_absolute_path = Path(IO_AnnocfgPreferences.get_path_to_rda_folder(), path)
    if bpy.context.scene.anno_mod_folder == "":
        return rda_absolute_path
    mod_absolute_path = Path(bpy.context.scene.anno_mod_folder, path)
    if mod_absolute_path.exists():
        return mod_absolute_path
    if rda_absolute_path.exists():
        return rda_absolute_path
    #Maybe it will be used with a different extension, etc. so have a look if the folder exists
    mod_absolute_path_to_folder = Path(bpy.context.scene.anno_mod_folder, path.parent)
    if mod_absolute_path_to_folder.exists():
        return mod_absolute_path
    return rda_absolute_path

def to_data_path(absolute_path):
    absolute_path = Path(absolute_path)
    rda_path = IO_AnnocfgPreferences.get_path_to_rda_folder()
    if absolute_path.is_relative_to(rda_path):
        return absolute_path.relative_to(rda_path)
    mod_path = Path(bpy.context.scene.anno_mod_folder)
    if absolute_path.is_relative_to(mod_path):
        return absolute_path.relative_to(mod_path)
    raise ValueError(f"Path {absolute_path} is neither relative to the rda path nor the current mod path.")