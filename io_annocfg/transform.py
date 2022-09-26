
from __future__ import annotations
import bpy
from bpy.types import Object as BlenderObject
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple, List, NewType, Any, Union, Dict, Optional, TypeVar, Type
import bmesh
from math import radians
from .prefs import IO_AnnocfgPreferences
from .utils import *

class Transform:
    """
    Parses an xml tree node for transform operations, stores them and can apply them to a blender object.
    """
    def __init__(self, loc = [0,0,0], rot = [1,0,0,0], sca = [1,1,1], anno_coords = True):
        self.location = loc
        self.rotation = rot
        self.rotation_euler = [0,0,0]
        self.euler_rotation = False
        self.scale = sca
        self.anno_coords = anno_coords
        
    def get_component_value(self, component_name: str) -> float:
        component_by_name = {
            "location.x": self.location[0],
            "location.y": self.location[1],
            "location.z": self.location[2],
            
            "rotation.w": self.rotation[0],
            "rotation.x": self.rotation[1],
            "rotation.y": self.rotation[2],
            "rotation.z": self.rotation[3],
            
            "rotation_euler.x": self.rotation_euler[0],
            "rotation_euler.y": self.rotation_euler[1],
            "rotation_euler.z": self.rotation_euler[2],
            
            "scale.x": self.scale[0],
            "scale.y": self.scale[1],
            "scale.z": self.scale[2],
        }
        return component_by_name[component_name]
        
    def get_component_from_node(self, node: ET.Element, transform_paths: Dict[str, str], component: str, default = 0.0) -> float:
        query = transform_paths.get(component, None)
        if not query:
            return default
        value = float(get_text_and_delete(node, query, str(default)))
        return value
        
    @classmethod
    def from_node(cls, node: ET.Element, transform_paths, enforce_equal_scale: bool, euler_rotation: bool = False) -> Transform:
        instance = cls()
        instance.location[0] = instance.get_component_from_node(node, transform_paths, "location.x")
        instance.location[1] = instance.get_component_from_node(node, transform_paths, "location.y")
        instance.location[2] = instance.get_component_from_node(node, transform_paths, "location.z")
        
        instance.scale[0] = instance.get_component_from_node(node, transform_paths, "scale.x", 1.0)
        instance.scale[1] = instance.get_component_from_node(node, transform_paths, "scale.y", 1.0)
        instance.scale[2] = instance.get_component_from_node(node, transform_paths, "scale.z", 1.0)
        if enforce_equal_scale:
            instance.scale[1] = instance.scale[0]
            instance.scale[2] = instance.scale[1]
        
        if not euler_rotation:        
            instance.rotation[0] = instance.get_component_from_node(node, transform_paths, "rotation.w", 1.0)
            instance.rotation[1] = instance.get_component_from_node(node, transform_paths, "rotation.x")
            instance.rotation[2] = instance.get_component_from_node(node, transform_paths, "rotation.y")
            instance.rotation[3] = instance.get_component_from_node(node, transform_paths, "rotation.z")
        else:
            instance.rotation_euler[0] = instance.get_component_from_node(node, transform_paths, "rotation_euler.x")
            instance.rotation_euler[1] = instance.get_component_from_node(node, transform_paths, "rotation_euler.y")
            instance.rotation_euler[2] = instance.get_component_from_node(node, transform_paths, "rotation_euler.z")
            instance.euler_rotation = True
            
        instance.anno_coords = True
        return instance
        
    @classmethod
    def from_blender_object(cls, obj, enforce_equal_scale: bool, euler_rotation: bool = False) -> Transform:
        if enforce_equal_scale:
            if len(set([obj.scale[0], obj.scale[1], obj.scale[2]])) > 1:
                print(obj.name, "Cannot have different scale values on xyz")
        instance = cls(obj.location, [1,0,0,0], obj.scale, False)
        if not euler_rotation:
            obj.rotation_mode = "QUATERNION"
            instance.rotation = list(obj.rotation_quaternion)
            return instance
        obj.rotation_mode = "XYZ"
        instance.rotation_euler = [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z]
        return instance
    
    def convert_to_blender_coords(self):
        if not self.anno_coords:
            return
        if IO_AnnocfgPreferences.mirror_models():
            self.location = (-self.location[0], -self.location[2], self.location[1])
            self.rotation = (self.rotation[0], self.rotation[1], self.rotation[3], -self.rotation[2])
        else:     
            self.location = (self.location[0], -self.location[2], self.location[1])
            self.rotation = (self.rotation[0], self.rotation[1], self.rotation[3], self.rotation[2])
        self.rotation_euler = (self.rotation_euler[0], self.rotation_euler[2], self.rotation_euler[1])
        self.scale = (self.scale[0], self.scale[2], self.scale[1])
        
        self.anno_coords = False

    def convert_to_anno_coords(self):
        if self.anno_coords:
            return
        if IO_AnnocfgPreferences.mirror_models():
            self.location = (-self.location[0], self.location[2], -self.location[1])
            self.rotation = (self.rotation[0], self.rotation[1], -self.rotation[3], self.rotation[2])
        else:     
            self.location = (self.location[0], self.location[2], -self.location[1])
            self.rotation = (self.rotation[0], self.rotation[1], self.rotation[3], self.rotation[2])
        self.rotation_euler = (self.rotation_euler[0], self.rotation_euler[2], self.rotation_euler[1])
        self.scale = (self.scale[0], self.scale[2], self.scale[1])
        
        self.anno_coords
    
    @classmethod
    def mirror_mesh(self, obj):
        if not IO_AnnocfgPreferences.mirror_models():
            return
        if not obj.data or not hasattr(obj.data, "vertices"):
            return
        for v in obj.data.vertices:
            v.co.x *= -1.0
        #Inverting normals for import AND Export they are wrong because of scaling on the x axis.
        #Warn people that this will break exports from .blend files made with an earlier version!!!
        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh) # load bmesh
        for f in bm.faces:
             f.normal_flip()
        bm.normal_update() # not sure if req'd
        bm.to_mesh(mesh)
        mesh.update()
        bm.clear() #.. clear before load next
    
    def apply_to(self, object):
        if self.anno_coords:
            self.convert_to_blender_coords()
        #self.mirror_mesh(object)
        object.location = self.location
        if not self.euler_rotation:
            object.rotation_mode = "QUATERNION"
            object.rotation_quaternion = self.rotation
        else:
            object.rotation_mode = "XYZ"
            object.rotation_euler = self.rotation_euler
        object.scale = self.scale
