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

bl_info = {
    "name": "Annocfg ImportExport",
    "author": "xormenter",
    "version": (2, 9, 2),
    "blender": (3, 1, 0),
    "location": "File > Import > Anno (.cfg)",
    "description": "Allows importing and exporting configuration files for Anno 1800 3d models.",
    "doc_url": "https://github.com/xormenter/Blender-Anno-.cfg-Import-Addon",
    "tracker_url": "https://github.com/xormenter/Blender-Anno-.cfg-Import-Addon/issues",
    "category": "Import-Export",
}

import bpy
import os

from . import operators
from . import prefs
from . import feedback_ui
from . import anno_objects
from . import anno_object_ui

# =========================================================================
# Registration:
# =========================================================================
               


def register():
    operators.register()
    prefs.register()
    anno_objects.register()
    anno_object_ui.register()
    
    feedback_ui.register()
    


def unregister():
    operators.unregister()
    prefs.unregister()
    anno_objects.unregister()
    anno_object_ui.unregister()
    
    feedback_ui.unregister()


if __name__ == "__main__":
    register()
