import argparse
import xml.etree.ElementTree as ET
import logging
import json
import os


class XmlTree:

    fromFile = None
    toFile = None
    xml1Root = None
    xml2Root = None
    json1Root = None
    json2Root = None
    missingTags = []

    def __init__(self):
        logging.basicConfig(
            filename="xml-comparison.log",
            level=logging.DEBUG,
            format="%(message)s",
            filemode="w",
        )
        self.logger = logging.getLogger("compare")

    @staticmethod
    def convert_string_to_tree(xmlString):
        return ET.fromstring(xmlString)

    def compare(self, fromFile, toFile):
        self.fromName = os.path.basename(fromFile)
        self.toName = os.path.basename(toFile)
        self.missingTags = []
        self.fromFile = fromFile
        self.toFile = toFile
        self.xml1Root = None
        self.xml2Root = None
        self.json1Root = None
        self.json2Root = None
        file1ext = os.path.splitext(fromFile)[1]
        file2ext = os.path.splitext(toFile)[1]
        if file1ext == ".xml" and file2ext == ".xml":
            self.compareXmlToXml(fromFile, toFile)
        elif file1ext == ".json" and file2ext == ".json":
            self.compareJsonFileToJson()
        elif file1ext == ".xml" and file2ext == ".json":
            self.compareXmlToJson(fromFile, toFile)
        elif file1ext == ".json" and file2ext == ".xml":
            self.compareJsonFileToXML(fromFile, toFile)

        self.logger.debug("\n")
        return len(self.missingTags)

    def compareXmlToXml(self, fromfile, tofile):
        self.logger.debug(f"Checking if tags in {fromfile} are in {tofile}")
        tree1 = ET.parse(fromfile)
        tree2 = ET.parse(tofile)
        self.xml1Root = tree1.getroot()
        self.xml2Root = tree2.getroot()
        for child in self.xml1Root.iter():
            childFound = self.findKeyInXML(child.tag, self.xml2Root)
            if not childFound:
                self.missingTags.append(child.tag)

    def compareJsonFileToJson(self):
        with open(self.fromFile) as json_data:
            self.json1Root = json.load(json_data)
            with open(self.toFile) as json_data2:
                self.json2Root = json.load(json_data2)
                self.loopThroughJson(self.json1Root)

    def compareJsonFileToXML(self, jsonFile, xmlFile):
        with open(jsonFile) as json_data:
            self.json1Root = json.load(json_data)
            tree = ET.parse(xmlFile)
            self.xml2Root = tree.getroot()
            self.loopThroughJson(self.json1Root)

    def compareXmlToJson(self, xmlFile, jsonFile):
        tree = ET.parse(xmlFile)
        root = tree.getroot()
        self.xml1Root = root
        with open(jsonFile) as json_data:
            self.json2Root = json.load(json_data)
            self.loopThroughXml(self.xml1Root)

    def loopThroughJson(self, jsonData):
        for k, v in jsonData.items():
            if isinstance(v, dict):
                self.loopThroughJson(v)
            elif isinstance(v, list):
                for item in v:
                    self.loopThroughJson(item)
            foundKey = None
            if self.xml2Root is not None:
                foundKey = self.findKeyInXML(k, self.xml2Root)
            else:
                foundKey = self.findKeyInJSON(k, self.json2Root)
            if not foundKey:
                self.missingTags.append(f'"{k}"')

    def loopThroughXml(self, root1):
        for child in root1.iter():
            k = child.tag
            foundKey = None
            if self.xml2Root is not None:
                foundKey = self.findKeyInXML(k, self.xml2Root)
            else:
                if k.find("}") == -1:
                    foundKey = self.findKeyInJSON(k, self.json2Root)
                else:
                    foundKey = "skipped"
            if not foundKey:
                self.missingTags.append(f"<{k}>")

    def findKeyInXML(self, key, root):
        for child in root.iter(key):
            if child.tag == key:
                return f"<{key}>"
        return None

    def findKeyInJSON(self, key, jsonData):
        if key in jsonData:
            return key
        for k, v in jsonData.items():
            if isinstance(v, dict):
                return self.findKeyInJSON(key, v)
            elif isinstance(v, list):
                for item in v:
                    return self.findKeyInJSON(key, item)
            if k == key:
                return f'"{key}"'
        return None


def main():
    ET.register_namespace("req", "http://www.mepcom.army.mil/request")
    ET.register_namespace("dat", "http://www.mepcom.army.mil/dataTypes")
    parser = argparse.ArgumentParser()
    parser.add_argument("fromfile")
    parser.add_argument("tofile")
    options = parser.parse_args()

    fromfile = options.fromfile
    tofile = options.tofile
    fromName = os.path.basename(fromfile)
    toName = os.path.basename(tofile)

    comparator = XmlTree()
    print(f"\n\n== Checking if keys in {fromName} exist in {toName} ==")
    # print(f'====================')
    results = comparator.compare(fromfile, tofile)
    print("")
    for tag in comparator.missingTags:
        print(f" - {tag}")
    print(
        f' {toName} is missing {results} key{"s" if results > 1 else ""}'
        if results > 0
        else f"\n {toName} has no missing keys"
    )

    print(f"\n== Checking if keys in {toName} exist in {fromName} ==")
    # print(f'====================')
    results2 = comparator.compare(tofile, fromfile)
    fromfile = os.path.basename(fromfile)
    tofile = os.path.basename(tofile)
    for tag in comparator.missingTags:
        print(f" - {tag}")
    print(
        f' {fromName} is missing {results2} key{"s" if results2 > 1 else ""}'
        if results2 > 0
        else f"\n {fromName} has no missing keys"
    )
    print("\nDONE!")


if __name__ == "__main__":
    main()
