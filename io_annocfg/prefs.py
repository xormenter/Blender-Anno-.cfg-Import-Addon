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
from bpy.props import StringProperty, EnumProperty, BoolProperty, FloatProperty

from pathlib import Path

class IO_AnnocfgPreferences(AddonPreferences):
    bl_idname = __package__
    
    path_to_rda_folder : StringProperty( # type: ignore
        name = "Path to rda Folder",
        description = "Path where you unpacked the Anno rda files. Should contain the data folder.",
        subtype='FILE_PATH',
        default = "",
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
        description = "If .fc splines are imported/exported.",
        default = False
    )
    mirror_models_bool : BoolProperty( # type: ignore
        name = "Mirror along X",
        description = "The anno engine mirrors object along the X axis. When enabled, the addon will also mirror meshes along the X axis s.t. text is displayed correctly. However, this means that all .glb files imported directly (using the .glb import instead of the .rmd import) will have the wrong orientation, to avoid this uncheck this box. Keep in mind that when you change this setting, all your exising .blend files will not export properly.",
        default = True
    )
    sequences_as_blender_objects : BoolProperty( # type: ignore
        name = "Sequences as Blender Objects",
        description = "Turns sequences into blender objects and resolves ModelID (and ParticleID) references to their respective blender object. Allows easier handling of animated files and prevents errors coming from a reordering of the models when exporting. ",
        default = True
    )
    cfg_cache_probability_float : FloatProperty( # type: ignore
        name = "Cfg Cache Probability",
        description = "Caches .cfg files in a specific library folder to allow faster retrieval. Set to 0 to disable and to 1 to cache everything. Use a value in between to only cache frequently used .cfgs (in expectation)",
        default = 1.0,
        min = 0.0,
        max = 1.0,
    )
    cfg_cache_loading_enabled_bool : BoolProperty( # type: ignore
        name = "Cfg Cache Loading Enabled",
        description = "Allow to load cached .cfgs",
        default = True,
    )
    cfg_cache_path : StringProperty( # type: ignore
        name = "Path to cfg cache",
        description = "Select a Path for the cfg Cache. Sadly it does not work great as an asset library, because it lacks preview images...",
        subtype='FILE_PATH',
        default = "C:\\Users\\Public\\Anno\\CfgCache",
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "path_to_rda_folder")
        layout.prop(self, "path_to_rdm4")
        layout.prop(self, "path_to_texconv")
        layout.prop(self, "path_to_fc_converter")
        layout.prop(self, "texture_quality")
        layout.prop(self, "mirror_models_bool")
        layout.prop(self, "enable_splines")
        layout.prop(self, "sequences_as_blender_objects")
        layout.prop(self, "cfg_cache_loading_enabled_bool")
        layout.prop(self, "cfg_cache_probability_float")
        layout.prop(self, "cfg_cache_path")

    @classmethod
    def get_cfg_cache_path(cls):
        return Path(bpy.context.preferences.addons[__package__].preferences.cfg_cache_path)
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
    @classmethod
    def mirror_models(cls):
        return bpy.context.preferences.addons[__package__].preferences.mirror_models_bool
    @classmethod
    def turn_sequences_into_blender_objects(cls):
        return bpy.context.preferences.addons[__package__].preferences.sequences_as_blender_objects
    @classmethod
    def cfg_cache_probability(cls):
        return bpy.context.preferences.addons[__package__].preferences.cfg_cache_probability_float
    @classmethod
    def cfg_cache_loading_enabled(cls):
        return bpy.context.preferences.addons[__package__].preferences.cfg_cache_loading_enabled_bool

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
