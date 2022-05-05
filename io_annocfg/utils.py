from __future__ import annotations
import bpy
from pathlib import Path
from .prefs import IO_AnnocfgPreferences

import xml.etree.ElementTree as ET
import re
from typing import Tuple, List, NewType, Any, Union, Dict, Optional, TypeVar, Type

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



def parse_float_node(node, query, default_value = 0.0):
    value = default_value
    if node.find(query) is not None:
        value = float(node.find(query).text)
    return value

def get_float(node, query, default_value = 0.0):
    value = default_value
    if node.find(query) is not None:
        value = float(node.find(query).text)
    return value


def is_type(T: type, s: str) -> bool:
    try:
        T(s)
        return True
    except:
        return False

def string_to_fitting_type(s: str):
    if is_type(int, s) and s.isnumeric():
        return int(s)
    if is_type(float, s):
        return float(s)
    return s
    
def get_first_or_none(list):
    if list:
        return list[0]
    return None


def get_text(node: ET.Element, query: str, default_value = "") -> str:
    if node.find(query) is None:
        return str(default_value)
    if node.find(query).text is None:
        return str(default_value)
    return node.find(query).text

def get_text_and_delete(node: ET.Element, query: str, default_value = "") -> str:
    if node.find(query) is None:
        return str(default_value)
    subnode = node.find(query)
    parent = node
    if "/" in query:
        query = query.rsplit("/", maxsplit=1)[0]
        parent = node.find(query)
    parent.remove(subnode)
    while len(list(parent)) == 0 and parent != node:
        elements = query.rsplit("/", maxsplit=1)
        query = elements[0]
        parents_parent = node
        if len(elements) > 1:
            parents_parent = node.find(query)
        parents_parent.remove(parent)
        parent = parents_parent
    if subnode.text is None:
        return default_value
    return subnode.text

def format_float(value: Union[float, int]):
    return "{:.6f}".format(value)

def find_or_create(parent: ET.Element, simple_query: str) -> ET.Element:
    """Finds or creates the subnode corresponding to the simple query.
    

    Args:
        parent (ET.Element): root node
        simple_query (str): Only supports queries like "Config[ConfigType="ORIENTATION_TRANSFORM"]/Position/x", no advanced xpath.

    Returns:
        ET.Element: The node.
    """
    parts = simple_query.split("/", maxsplit = 1)
    query = parts[0]
    queried_node = parent.find(query)
    if queried_node is None:
        tag = query.split("[")[0]
        queried_node = ET.SubElement(parent, tag)
        if "[" in query:
            condition = query.split("[")[1].replace("]", "")
            subnode_tag = condition.split("=")[0].strip()
            subnode_value = condition.split("=")[1].strip().replace('"', '').replace("'", "")
            ET.SubElement(queried_node, subnode_tag).text = subnode_value
    if len(parts) > 1:
        return find_or_create(queried_node, parts[1])
    return queried_node

