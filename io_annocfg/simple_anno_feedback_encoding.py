#from lxml import etree
import xml.etree.ElementTree as etree
from pathlib import Path

from . import feedback_enums

SEQUENCE_ID_BY_NAME = {"none":-1, "idle01":1000, "idle02":1001, "idle03":1002, "idle04":1003, "idle05":1003, "death01":1005, "talk01":1010, "talk02":1011, "greet01":1020, \
    "bow01":1021, "cheer01":1030, "cheer02":1031, "cheer03":1032, "lookat01":1040, "lookat02":1041, "protest01":1050, "protest02":1051, "laydown01":1060, \
    "laydown02":1061, "laydown03":1062, "fishing01":1070, "fishing02":1071, "fishing03":1072, "dance01":1080, "dance02":1081, "dance03":1082, "dance04":1083, "fight01":1090, \
    "fight02":1091, "walk01":2000, "walk02":2001, "walk03":2002, "walk04":2003, "walk05":2004, "walk06":2005, "walk07":2005, "drunkenwalk01":2010, "drunkenwalk02":2011, \
    "run01":2100, "panicrun01":2101, "panicrun02":2102, "donate01":2200, "buy01":2201, "buy02":2202, "work01":3000, "work02":3001, "work03":3002, \
    "work04":3003, "work05":3004, "work06":3005, "stand01":4000, "build01":5000, "portrait_neutral_idle":10000, "portrait_neutral_talk":10001, \
    "portrait_friendly_idle":10010, "portrait_friendly_talk":10011, "portrait_angry_idle":10020, "portrait_angry_talk":10021, "portrait_neutral_talk_idle":10030, \
    "portrait_friendly_talk_idle":10031, "portrait_angry_talk_idle":10040, "extFire01":5100, "extFire02":5101, "extFire03":5102, "pray01":5200, \
    "protestwalk01":5300, "protestwalk02":5301, "protest03":1052, "protest04":1053, "protest05":1054, "protest06":1055, "fight03":1092, "protestwalk03":5302, \
    "fight04":1093, "fight05":1094, "work_staged01":3010, "work_staged02":3011, "work_staged03":3012, "takeoff01":5400, "land01":5410, "riotspecial01":5350, \
    "riotspecial02":5351, "boosted":3050, "riotspecial03":5352, "sitdown01":5500, "sitdown02":5501, "sitdown03":5502, "explode01":2300, "explode02":2301, \
    "explode03":2302, "explode04":2303, "idleLoaded01":6000, "walkingLoaded01":6001, "hitwood":2400, "hitbrick":2401, "hitsteel":2402, "hitconcrete":2403, \
    "misswater":2410, "missland":2411, "work07":3006, "work08":3007, "work09":3008, "work10":3009, "work11":3020, "work12":3021, "work13":3022, \
    "work14":3023, "work15":3024, "work16":3025, "work17":3026, "work18":3027, "work19":3028}

def get_sequence(sequence):
    return str(SEQUENCE_ID_BY_NAME.get(sequence, -1))

def get_text(node, query, default = ""):
    if node.find(query) is not None:
        if node.find(query).text is None or node.find(query).text == "None":
            return ""
        return node.find(query).text
    return default

def get_required_text(node, query):
    if node.find(query) is not None:
        if node.find(query).text is None or node.find(query).text == "None":
            return ""
        return node.find(query).text
    raise Exception(f"Missing node {query} in Feedback")



class FeedbackConfig():
    property_values = {"Description":"", "IgnoreRootObjectXZRotation":"0", "IsAlwaysVisibleActor":"0", "ApplyScaleToMovementSpeed":"1", "ActorCount":"1", \
        "MaxActorCount":"1", "CreateChance":"100", "BoneLink":"NoLink", "RenderFlags":"0", "MultiplyActorByDummyCount":None, "IgnoreForceActorVariation":"0", "IgnoreDistanceScale":"0"}
    def __init__(self, feedback_config_node, feedback_encoding):
        self.node = feedback_config_node
        self.feedback_encoding = feedback_encoding
        self.extract_properties()
        self.extract_guid_variations()
        self.extract_scale()
        self.default_state_dummy = get_required_text(self.node, "DefaultStateDummy")
        self.start_dummy_group = get_text(self.node, "StartDummyGroup", "")
        self.extract_sequence()

    def extract_properties(self):
        self.properties = {}
        for prop, default_value in FeedbackConfig.property_values.items():
            value = get_text(self.node, prop, default_value)
            if value == "True":
                value = "1"
            if value == "False":
                value = "0"
            self.properties[prop] = value

    def extract_guid_variations(self):
        self.guid_variations = []
        for guid_node in self.node.find("GUIDVariationList").findall("GUID"):
            guid = guid_node.text
            if guid in feedback_enums.full_guids_by_name:
                guid = str(feedback_enums.full_guids_by_name[guid])
            if guid.isnumeric():
                self.guid_variations.append(guid)
            else:
                print("Warning: Invalid GUID: ", guid)
    
    def extract_scale(self):
        scale_node = self.node.find("Scale")
        self.min_scale = get_required_text(scale_node, "m_MinScaleFactor")
        self.max_scale = get_required_text(scale_node, "m_MaxScaleFactor")



    def extract_sequence(self):
        self.sequence_elements = []
        if self.start_dummy_group != "":
            #For more than one person, the only option seems to be this special element type 12. Format CDATA[4 * len(seq) seq]
            #Example: <m_SequenceIds>CDATA[20 1000 1001 1040 1010 3000]</m_SequenceIds>
            #We use the sequence_ids of ALL IdleSequences specified in here.
            sequence_ids = []
            for sequence_element_node in list(self.node.find("SequenceElements")):
                if sequence_element_node.tag == "IdleAnimation":
                    seq_id = get_sequence(get_required_text(sequence_element_node, 'm_IdleSequenceID'))
                    sequence_ids.append(seq_id)
            element = etree.Element("i")
            etree.SubElement(element, "m_SequenceIds").text = f"CDATA[{4*len(sequence_ids)} {' '.join(sequence_ids)}]"
            etree.SubElement(element, "hasValue").text = "1"
            etree.SubElement(element, "elementType").text = "12"
            etree.SubElement(element, "MinPlayCount").text = "1"
            etree.SubElement(element, "MaxPlayCount").text = "2"
            etree.SubElement(element, "MinPlayTime").text = "0"
            etree.SubElement(element, "MaxPlayTime").text = "0"
            self.sequence_elements.append(element)
            return
        for sequence_element_node in list(self.node.find("SequenceElements")):
            element = etree.Element("i")
            etree.SubElement(element, "hasValue").text = "1"
            if sequence_element_node.tag == "IdleAnimation":
                # if self.start_dummy_group == "":
                etree.SubElement(element, "elementType").text = "1"
                etree.SubElement(element, "m_IdleSequenceID").text = get_sequence(get_required_text(sequence_element_node, "m_IdleSequenceID"))
                etree.SubElement(element, "ResetStartTime").text = "0"
                # else:
                #     etree.SubElement(element, "elementType").text = "12"
                #     etree.SubElement(element, "m_SequenceIds").text = f"CDATA[4 {get_sequence(get_required_text(sequence_element_node, 'm_IdleSequenceID'))}]"
                etree.SubElement(element, "MinPlayCount").text = get_required_text(sequence_element_node, "MinPlayCount")
                etree.SubElement(element, "MaxPlayCount").text = get_required_text(sequence_element_node, "MaxPlayCount")
                etree.SubElement(element, "MinPlayTime").text = "0"
                etree.SubElement(element, "MaxPlayTime").text = "0"
            if sequence_element_node.tag == "TimedIdleAnimation":
                etree.SubElement(element, "elementType").text = "1"
                etree.SubElement(element, "m_IdleSequenceID").text = get_sequence(get_required_text(sequence_element_node, "m_IdleSequenceID"))
                etree.SubElement(element, "MinPlayCount").text = "0"
                etree.SubElement(element, "MaxPlayCount").text = "0"
                etree.SubElement(element, "MinPlayTime").text = get_required_text(sequence_element_node, "MinPlayTime")
                etree.SubElement(element, "MaxPlayTime").text = get_required_text(sequence_element_node, "MaxPlayTime")
                etree.SubElement(element, "ResetStartTime").text = "0"
            if sequence_element_node.tag == "Walk":
                etree.SubElement(element, "elementType").text = "0"
                etree.SubElement(element, "WalkSequence").text = get_sequence(get_required_text(sequence_element_node, "WalkSequence"))
                etree.SubElement(element, "TargetDummy").text = get_required_text(sequence_element_node, "TargetDummy")
                etree.SubElement(element, "TargetDummyId").text = self.feedback_encoding.dummy_id_by_name.get(get_required_text(sequence_element_node, "TargetDummy"), "0")
                etree.SubElement(element, "SpeedFactorF").text = get_required_text(sequence_element_node, "SpeedFactorF")
                etree.SubElement(element, "StartDummy")
                etree.SubElement(element, "StartDummyId").text = "0"
                etree.SubElement(element, "WalkFromCurrentPosition").text = "1"
                etree.SubElement(element, "UseTargetDummyDirection").text = "1"
                etree.SubElement(element, "DummyGroup").text = "CDATA[12 -1 -1 -1]"
            if sequence_element_node.tag == "Wait":
                etree.SubElement(element, "elementType").text = "2"
                etree.SubElement(element, "MinTime").text = get_required_text(sequence_element_node, "MinTime")
                etree.SubElement(element, "MaxTime").text = get_required_text(sequence_element_node, "MaxTime")
            if sequence_element_node.tag == "TurnAngle":
                etree.SubElement(element, "elementType").text = "10"
                etree.SubElement(element, "TurnAngleF").text = get_required_text(sequence_element_node, "TurnAngleF") #in radians
                etree.SubElement(element, "TurnSequence").text = get_required_text(sequence_element_node, "TurnSequence")
                etree.SubElement(element, "TurnToDummy")
                etree.SubElement(element, "TurnToDummyID").text = "0"
            if sequence_element_node.tag == "TurnToDummy":
                etree.SubElement(element, "elementType").text = "10"
                etree.SubElement(element, "TurnAngleF").text = "0"
                etree.SubElement(element, "TurnSequence").text = get_required_text(sequence_element_node, "TurnSequence")
                etree.SubElement(element, "TurnToDummy").text = get_required_text(sequence_element_node, "TurnToDummy")
                etree.SubElement(element, "TurnToDummyID").text = self.feedback_encoding.dummy_id_by_name.get(get_required_text(sequence_element_node, "TurnToDummy"), "0")
            self.sequence_elements.append(element)

    def export_to_cf7(self, feedback_config_node, feedback_loop_mode):
        etree.SubElement(feedback_config_node, "hasValue").text = "1"
        etree.SubElement(feedback_config_node, "MainObject").text = "0"
        self.export_properties(feedback_config_node)
        self.export_guid_variations(feedback_config_node)
        fl_node = etree.SubElement(feedback_config_node, "FeedbackLoops") #no idea what this is...
        etree.SubElement(fl_node, "k").text = str(feedback_loop_mode)
        etree.SubElement(fl_node, "v").text = "0"
        sequence_definitions_node = etree.SubElement(feedback_config_node, "SequenceDefinitions")
        sequence_definition_node = etree.SubElement(sequence_definitions_node, "i")
        self.export_sequence_definition(sequence_definition_node)

    def export_properties(self, feedback_config_node):
        for prop, value in self.properties.items():
            prop_element = etree.SubElement(feedback_config_node, prop)
            if value is not None:
                prop_element.text = str(value)

    def export_guid_variations(self, feedback_config_node):
        asset_variation_node = etree.SubElement(feedback_config_node, "AssetVariationList")
        guid_variation_bytes = 8 * len(self.guid_variations)
        guid_variations_string = f"CDATA[{guid_variation_bytes} {' '.join([guid + ' -1' for guid in self.guid_variations])}]"
        etree.SubElement(asset_variation_node, "GuidVariationList").text = guid_variations_string
        etree.SubElement(asset_variation_node, "AssetGroupNames")

    def export_sequence_definition(self, feedback_config_node):
        etree.SubElement(feedback_config_node, "hasValue").text = "1"
        
        #Loop 0 - mostly hardcoded
        loop0_node = etree.SubElement(feedback_config_node, "Loop0")
        etree.SubElement(loop0_node, "hasValue").text = "1"
        loop0_default_state_node = etree.SubElement(loop0_node, "DefaultState")
        start_dummy_group_node = etree.SubElement(loop0_node, "StartDummyGroup")
        etree.SubElement(loop0_default_state_node, "DummyName")
        etree.SubElement(loop0_default_state_node, "StartDummyGroup")
        etree.SubElement(loop0_default_state_node, "DummyId").text = "0"
        etree.SubElement(loop0_default_state_node, "SequenceID").text = "-1"
        etree.SubElement(loop0_default_state_node, "Visible").text = "1"
        etree.SubElement(loop0_default_state_node, "FadeVisibility").text = "1"
        etree.SubElement(loop0_default_state_node, "ResetToDefaultEveryLoop").text = "1"
        etree.SubElement(loop0_default_state_node, "ForceSequenceRestart").text = "0"
        loop_0_container = etree.SubElement(loop0_node, "ElementContainer")
        loop_0_elements = etree.SubElement(loop_0_container, "Elements")
        loop_0_element1 = etree.SubElement(loop_0_elements, "i")
        etree.SubElement(loop_0_element1, "hasValue").text = "1"
        etree.SubElement(loop_0_element1, "elementType").text = "9"
        etree.SubElement(loop_0_element1, "m_MinScaleFactor").text = self.min_scale
        etree.SubElement(loop_0_element1, "m_MaxScaleFactor").text = self.max_scale
        
        #loop 1
        loop1_node = etree.SubElement(feedback_config_node, "Loop1")
        etree.SubElement(loop1_node, "hasValue").text = "1"
        loop1_default_state_node = etree.SubElement(loop1_node, "DefaultState")
        etree.SubElement(loop1_default_state_node, "DummyName").text = self.default_state_dummy
        etree.SubElement(loop1_default_state_node, "StartDummyGroup").text = self.start_dummy_group
        etree.SubElement(loop1_default_state_node, "DummyId").text = self.feedback_encoding.dummy_id_by_name.get(self.default_state_dummy, "0")
        etree.SubElement(loop1_default_state_node, "SequenceID").text = "-1"
        etree.SubElement(loop1_default_state_node, "Visible").text = "1"
        etree.SubElement(loop1_default_state_node, "FadeVisibility").text = "1"
        etree.SubElement(loop1_default_state_node, "ResetToDefaultEveryLoop").text = "1"
        etree.SubElement(loop1_default_state_node, "ForceSequenceRestart").text = "0"
        loop_1_container = etree.SubElement(loop1_node, "ElementContainer")
        loop_1_elements = etree.SubElement(loop_1_container, "Elements")
        for element in self.sequence_elements:
            loop_1_elements.append(element)

class SimpleAnnoFeedbackEncoding():
    def __init__(self, root_node):
        self.root = root_node
        self.dummy_id_by_name = {} #id by name
        self.dummy_id_counter = 1 #id1 is reserved for the dummy_group node
        self.dummy_groups = {} #list of dummies (nodes) by group name
        self.guid_by_name = {} 
        self.feedback_configs = []

        self.extract_guid_names()
        self.extract_dummy_groups()
        self.extract_feedback_configs()

    def extract_dummy_groups(self):
        if self.root.find("DummyGroups") is None:
            return
        for dummy_group_node in self.root.find("DummyGroups").findall("DummyGroup"):
            name = get_required_text(dummy_group_node, "Name")
            dummy_id = self.get_dummy_id() #groups also need an id for some reason
            if name in self.dummy_id_by_name:
                raise Exception(f"Non unique dummy name {name}")
            self.dummy_id_by_name[name] = dummy_id
            self.dummy_groups[name] = self.extract_dummies(dummy_group_node)
    def get_dummy_id(self):
        self.dummy_id_counter += 1
        return str(self.dummy_id_counter)

    def extract_dummies(self, dummy_group_node):
        dummies = []
        for dummy_node in dummy_group_node.findall("Dummy"):
            name = get_required_text(dummy_node, "Name")
            dummy_id = self.get_dummy_id()
            if name in self.dummy_id_by_name:
                raise Exception(f"Non unique dummy name {name}")
            self.dummy_id_by_name[name] = dummy_id

            etree.SubElement(dummy_node, "Id").text = str(dummy_id)
            etree.SubElement(dummy_node, "hasValue").text = "1"
            etree.SubElement(dummy_node, "RotationY").text = str("0.000000")

            # Okay, rotation is fully controlled by rotationY with 0 => looking towards negative x, 3.14 => looking towards positive x.
            # Orientation is something else entirely.

            dummies.append(dummy_node)
        return dummies

    def extract_guid_names(self):
        if self.root.find("GUIDNames") is None:
            return
        for item_node in self.root.find("GUIDNames").findall("Item"):
            name = get_required_text(item_node, "Name")
            guid = get_required_text(item_node, "GUID")
            self.guid_by_name[name] = guid
        
    def extract_feedback_configs(self):
        if self.root.find("FeedbackConfigs") is None:
            return
        for feedback_config_node in self.root.find("FeedbackConfigs").findall("FeedbackConfig"):
            self.feedback_configs.append(FeedbackConfig(feedback_config_node, self))

    def as_cf7(self, feedback_loop_mode = 1):
        cf7root = etree.Element("cf7_imaginary_root")
        dummy_root = etree.SubElement(cf7root, "DummyRoot")
        self.export_dummies(dummy_root)
        etree.SubElement(cf7root, "IdCounter").text = str(self.dummy_id_counter)
        etree.SubElement(cf7root, "SplineData")

        feedback_definition_node = etree.SubElement(cf7root, "FeedbackDefinition")
        feedback_configs_node = etree.SubElement(feedback_definition_node, "FeedbackConfigs")
        for feedback_config in self.feedback_configs:
            feedback_config_node = etree.SubElement(feedback_configs_node, "i")
            feedback_config.export_to_cf7(feedback_config_node, feedback_loop_mode)
        etree.SubElement(feedback_definition_node, "ValidSequenceIDs").text = "CDATA[8 0 1]"

        return cf7root
    
    def write_as_cf7(self, filename, feedback_loop_mode = 1):
        cf7root = self.as_cf7(feedback_loop_mode)
        etree.indent(cf7root, space=" ")
        cf7tree_string = etree.tostring(cf7root, encoding='unicode', method='xml')

        cf7tree_string = cf7tree_string.replace("</cf7_imaginary_root>", "").replace("<cf7_imaginary_root>","")
        with open(str(filename.with_suffix(".cf7")), 'w') as f:
            f.write(cf7tree_string)

    def export_dummies(self, dummy_root):
        etree.SubElement(dummy_root, "hasValue").text = "1"
        etree.SubElement(dummy_root, "Name")
        etree.SubElement(dummy_root, "Dummies")
        etree.SubElement(dummy_root, "Id").text = "1"
        dummy_groups_node = etree.SubElement(dummy_root, "Groups")
        for dummy_group_name in self.dummy_groups:
            group_item_node = etree.SubElement(dummy_groups_node, "i")
            self.export_dummy_group(dummy_group_name, group_item_node)
    
    def export_dummy_group(self, dummy_group_name, group_item_node):
        etree.SubElement(group_item_node, "hasValue").text = "1"
        etree.SubElement(group_item_node, "Name").text = dummy_group_name
        etree.SubElement(group_item_node, "Id").text = self.dummy_id_by_name[dummy_group_name]
        etree.SubElement(group_item_node, "Groups")
        dummy_list_node = etree.SubElement(group_item_node, "Dummies")
        for dummy_node in self.dummy_groups[dummy_group_name]:
            dummy_node.tag = "i"
            dummy_list_node.append(dummy_node)