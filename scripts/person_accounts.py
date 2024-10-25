# Scans files that provide access to the Account object but not the Contact object
# Access to Contacts is required for Person Account

import os
import xml.etree.ElementTree as ET
import sys

tagNamespace = "http://soap.sforce.com/2006/04/metadata"


def tag(tag):
    return '{' + tagNamespace + '}' + tag


class PersonAccountChecker:
    invalid_files = []
    root_tag = tag('PermissionSet')
    tag_objectPermissions = tag('objectPermissions')
    tag_object = tag('object')
    tag_allowRead = tag('allowRead')

    def __init__(self):
        self.invalid_files = []
        if len(sys.argv) == 1:
            # Ask for the directory to scan and append it to the current running directory
            self.scan_files()
        else:
            self.scan_files(sys.argv[1])

    def check_path(self, path):
        if not path:
            return False
        if not os.path.exists(path):
            return False
        return True
    
    # Ask for the directory to scan
    def get_path(self, path=None):
        if not path:
            path = input("Enter the path to the directory or file to scan: ")
            if path == "" or path == ".":
                path = os.getcwd()

        while not self.check_path(path):
            path = input("Invalid path. Please enter a valid path: ")
        return path

    # Scan all files in the directory
    def scan_files(self, path=None):        
        path_to_scan = path if self.check_path(path) else self.get_path(path)
        if os.path.isfile(path_to_scan):
            print(f"Scanning file: {path_to_scan}")
            self.check_file(path_to_scan)
            return
        print(f"Scanning directory: {os.path.abspath(path_to_scan)}")
        for root, dirs, files in os.walk(path_to_scan):
            # check each file in the directory and subdirectories
            for file in files:
                self.check_file(os.path.join(root, file))
            
    def check_file(self, file):
        if not file.endswith('.xml'):
            return
        # if not file.endswith('permissionset-meta.xml'):
        #     return
        # print("Checking file: " + file)
        with open(file, 'r') as f:
            # read xml nodes
            tree = ET.parse(f)
            root = tree.getroot()
            if self.needs_fixed(root) and file not in self.invalid_files:
                self.invalid_files.append(file)

    def needs_fixed(self, rootNode: ET.Element):
        hasAccountRead = False
        hasContactRead = False
        for node in rootNode.iterfind(self.tag_objectPermissions):
            accountObject = node.find(self.tag_object).text == 'Account'
            contactObject = node.find(self.tag_object).text == 'Contact'
            readAccess = node.find(self.tag_allowRead).text == 'true'
            if accountObject and readAccess:
                hasAccountRead = True
            if contactObject and readAccess:
                hasContactRead = True
            if hasAccountRead and hasContactRead:
                return False
        
        if not hasAccountRead:
            return False
        return not hasContactRead

    def get_contact_node(self, rootNode: ET.Element):
        for node in rootNode.iterfind(self.tag_objectPermissions):
            if node.find(self.tag_object).text == 'Contact':
                return node
        return None
    
    def fixFile(self, file):
        print(f"Fixing [{file}]")
        with open(file, 'r') as f:
            # read xml nodes
            tree = ET.parse(f)
            root = tree.getroot()
            if self.needs_fixed(root):
                contactNode = self.get_contact_node(root)
                if contactNode is None:
                    self.add_contact_node(root)
                else:
                    self.update_contact_node(contactNode)
                xmlStr = ET.tostring(root, encoding='utf-8', xml_declaration=True, default_namespace=tagNamespace).decode()
                with open(file, 'w') as f:
                    f.write(xmlStr)

    def confirm_fix(self, file=None):
        if not file:
            return input(f"Would you like to fix {len(self.invalid_files)} files? [yN] ").lower() == 'y'

        filename = os.path.basename(file)
        return input(f"Would you like to fix {filename}? [yN] ").lower() == 'y'

    def add_contact_node(self, rootNode: ET.Element):
        objectPermission = ET.Element(self.tag_objectPermissions)
        objectName = ET.Element(self.tag_object)
        objectName.text = 'Contact'
        allowRead = ET.Element(self.tag_allowRead)
        allowRead.text = 'true'
        objectPermission.append(objectName)
        objectPermission.append(allowRead)
        rootNode.append(objectPermission)
        ET.indent(rootNode)

    def update_contact_node(self, contactNode: ET.Element):
        contactNode.find(self.tag_allowRead).text = 'true'


def log(element, should_log):
    if should_log:
        print(element)

   
def main():
    checker = PersonAccountChecker()
    if checker.invalid_files:
        plural = len(checker.invalid_files) > 1
        print(f"\nFound {len(checker.invalid_files)} file{'s' if plural else ''} that specify Account Read but {'are' if plural else 'is'} missing Contact Read permissions...\n")
        if checker.confirm_fix():
            for file in checker.invalid_files:
                checker.fixFile(file)
        else:
            print("\nNo files were modified.")
    else:
        print("\nAll files support Person Accounts.")


if __name__ == "__main__":
    main()
