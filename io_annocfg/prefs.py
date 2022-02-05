# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
import bpy
from bpy.types import AddonPreferences, Scene
from bpy.props import StringProperty, EnumProperty, BoolProperty

from pathlib import Path

class IO_AnnocfgPreferences(AddonPreferences):
    bl_idname = __package__
    
    path_to_rda_folder : StringProperty( # type: ignore
        name = "Path to rda Folder",
        description = "Path where you unpacked the Anno rda files. Should contain the data folder.",
        subtype='FILE_PATH',
        default = "C:\\Users\\Lars\\Documents\\Anno 1800\\ModdingRDAExplorer-1.4.0.0\\rda",
    )
    path_to_rdm4 : StringProperty( # type: ignore
        name = "Path to rdm4-bin.exe",
        description = "Path to the rdm4 converter.",
        subtype='FILE_PATH',
        default = "C:\\tools\\rdm4-bin.exe",
    )
    path_to_texconv : StringProperty( # type: ignore
        name = "Path to texconv.exe",
        description = "Path to the texconv tool used to convert .dds to .png.",
        subtype='FILE_PATH',
        default = "C:\\Users\\Public\\texconv.exe",
    )
    path_to_fc_converter : StringProperty( # type: ignore
        name = "Path to AnnoFCConverter.exe",
        description = "Path to the AnnoFCConverter tool used to convert .fc to .cf7 and vice versa.",
        subtype='FILE_PATH',
        default = "C:\\tools\\AnnoFCConverter.exe",
    )
    texture_quality : EnumProperty( #type: ignore
        name='Texture Quality',
        description='Determines which texture files will be used (_0.dds, _1.dds, etc). 0 is the highest setting. Only applies to newly imported models.',
        items= [
            ("0", "High", "High (_0.dds)"),
            ("1", "Medium", "Medium (_1.dds)"),
            ("2", "Low", "Low (_2.dss)"),
        ],
        default='0')
    enable_splines : BoolProperty( # type: ignore
        name = "Import/Export Spline Data (Experimental)",
        description = "If .fc splines are imported/exported. Currently, only supports ControlPoints",
        default = False
    )
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "path_to_rda_folder")
        layout.prop(self, "path_to_rdm4")
        layout.prop(self, "path_to_texconv")
        layout.prop(self, "path_to_fc_converter")
        layout.prop(self, "texture_quality")

    @classmethod
    def get_path_to_rda_folder(cls):
        return Path(bpy.context.preferences.addons[__package__].preferences.path_to_rda_folder)
    @classmethod
    def get_path_to_rdm4(cls):
        return Path(bpy.context.preferences.addons[__package__].preferences.path_to_rdm4)
    @classmethod
    def get_path_to_texconv(cls):
        return Path(bpy.context.preferences.addons[__package__].preferences.path_to_texconv)
    @classmethod
    def get_path_to_fc_converter(cls):
        return Path(bpy.context.preferences.addons[__package__].preferences.path_to_fc_converter)
    @classmethod
    def get_texture_quality(cls):
        return bpy.context.preferences.addons[__package__].preferences.texture_quality
    @classmethod
    def splines_enabled(cls):
        return bpy.context.preferences.addons[__package__].preferences.enable_splines

classes = (
    IO_AnnocfgPreferences,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.anno_mod_folder = StringProperty( # type: ignore
        name = "Anno Mod Folder",
        description = "Path of the current mod (should contain the data/... folder). Optional.",
        subtype='FILE_PATH',
        default = "",
    )


def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)
    del bpy.types.Scene.anno_mod_folder
