import xml.etree.ElementTree as ET
import xml.dom.minidom

class CheatTableManager:
    @staticmethod
    def save_table(filepath, hierarchical_data):
        """Saves hierarchical dict data to XML."""
        root = ET.Element("CheatTable")
        entries = ET.SubElement(root, "CheatEntries")
        
        def build_xml(parent_xml, data_list):
            for idx, item_dict in enumerate(data_list):
                row = item_dict["values"]
                entry = ET.SubElement(parent_xml, "CheatEntry")
                
                ET.SubElement(entry, "ID").text = str(idx)
                ET.SubElement(entry, "Description").text = str(row[1])
                # Cheat Engine considers Group Headers as having Type="Group" and no address
                is_group = "Group" in str(row[3])
                
                if not is_group:
                    ET.SubElement(entry, "Address").text = str(row[2])
                    ET.SubElement(entry, "VariableType").text = str(row[3])
                    ET.SubElement(entry, "Value").text = str(row[4])
                    ET.SubElement(entry, "EnableValue").text = str(row[5])
                    ET.SubElement(entry, "DisableValue").text = str(row[6])
                    ET.SubElement(entry, "Length").text = str(row[7])
                else:
                    ET.SubElement(entry, "IsGroupHeader").text = "1"
                    
                ET.SubElement(entry, "Active").text = "1" if row[0] == "[X]" else "0"
                
                if item_dict["children"]:
                    child_container = ET.SubElement(entry, "CheatEntries")
                    build_xml(child_container, item_dict["children"])
                    
        build_xml(entries, hierarchical_data)

        xmlstr = xml.dom.minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        with open(filepath, "w") as f:
            f.write(xmlstr)

    @staticmethod
    def load_table(filepath):
        """Loads XML into a hierarchical dict structure."""
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        def parse_entries(xml_node):
            data_list = []
            for entry in xml_node.findall("./CheatEntry"):
                desc = entry.findtext("Description", "No Description")
                is_group = entry.findtext("IsGroupHeader", "0") == "1"
                active_flag = entry.findtext("Active", "0")
                active_str = "[X]" if active_flag == "1" else "[]"
                
                if is_group:
                    row_vals = (active_str, desc, "", "Group Header", "", "", "", "")
                else:
                    addr = entry.findtext("Address", "00000000")
                    v_type = entry.findtext("VariableType", "4 Bytes (Big Endian)")
                    val = entry.findtext("Value", "?")
                    en_val = entry.findtext("EnableValue", "")
                    dis_val = entry.findtext("DisableValue", "")
                    length = entry.findtext("Length", "4")
                    row_vals = (active_str, desc, addr, v_type, val, en_val, dis_val, length)
                
                child_container = entry.find("CheatEntries")
                children = parse_entries(child_container) if child_container is not None else []
                
                data_list.append({"values": row_vals, "children": children})
            return data_list
            
        main_entries = root.find("CheatEntries")
        return parse_entries(main_entries) if main_entries is not None else []