# cci shell --script ./utils/getDependencies.py
from collections import defaultdict
import csv
import math
import os
import time
from typing import OrderedDict
from cumulusci.cli.runtime import CliRuntime
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
import json
from utils.fastSchema import fastSchema
from utils.general import makeInClauseFromList
from utils.timer import timer
from utils.findOBE import findOBE
from utils.options import options


class getDependencies:
    options = options()
    logger = None
    output_dir = os.path.join(os.getcwd(), "reports", "dependencies")
    DEP_QUERY = """SELECT MetadataComponentId,
                        MetadataComponentName,
                        MetadataComponentType,
                        RefMetadataComponentId,
                        RefMetadataComponentName,
                        RefMetadataComponentType
                        FROM MetadataComponentDependency
                        Where RefMetadataComponentType in ('CustomField') """
    CUSTOM_FIELDS_DATA = []
    CUSTOM_OBJECTS_DATA = []
    ALL_CUSTOM_OBJECTS_DATA = []
    ALL_CUSTOM_OBJECTS_DATA = []
    ALL_FIELD_SETS_DATA = []
    DEP_DATA = []
    RESULTS = defaultdict(list)
    maxNumberOfIds = 50

    def __init__(self, options=None, **kwargs):
        self.pt = timer()
        self.options.save = True
        if options:
            self.options.update(options)
        if kwargs:
            self.options.update(kwargs)
        runtime = CliRuntime(load_keychain=True)
        self.project_config = runtime.project_config
        name, org_config = runtime.get_org(
            self.options.org_name
        )  # gets the default cci org
        self.org_config = org_config
        self.sf = self._init_api()
        self.tooling = self._init_api("tooling")
        self.bulkTooling = self._init_api("bulk")
        self.fs = fastSchema()
        self.logger = org_config.logger
        self.obe = findOBE(
            save=False,
            logger=self.logger,
            org_config=org_config,
            sf=self.sf,
            project_config=self.project_config,
        )

    def run(self):
        self.logger.info(self.options)

        if self.options.fields:
            fields = [
                {"sobject": el[0], "name": el[1]}
                for el in (sub.split(".") for sub in self.options.fields.split(","))
            ]
            self.logger.info(f"Fields specified: {fields}")
            sql = f"""
            SELECT {','.join(self.obe.soqlFields)}
            FROM fields 
            WHERE custom
            AND (sobject,name) IN (VALUES {','.join(f"('{el['sobject']}','{el['name']}')" for el in fields)})
            ORDER BY sobject, name;"""
            self.all_obe_fields = self.obe.getAllOBEFields(sql)
            self.logger.info(f"Fields: {self.all_obe_fields}")
            self.options.customSearch = True
            # self.options.save = False
        else:
            self.all_obe_fields = self.obe.getAllOBEFields()
        assert len(self.all_obe_fields) > 0
        self.getAllCustomObjects()
        self.getAllCustomFields()
        self.getAllFieldSets()
        self.pt.log("...Done getting all custom objects and fields")
        saveResult = self.getObeDeps2()
        if not self.options.save:
            self.logger.info(json.dumps(self.RESULTS, indent=2))
        self.logger.info(
            "\n------------------------------------------------------------\n"
        )
        self.logger.info(
            "- Found {} components referencing {} field(s)".format(
                len(self.RESULTS), len(self.all_obe_fields)
            )
        )
        self.logger.info("> Report: '{}'".format(saveResult))
        self.logger.info(
            "\n------------------------------------------------------------\n"
        )
        self.pt.log("Completed task in")

    def getObeDeps2(self):
        self.putFieldIdsInOBEFieldsList()
        self.getOBEDependencies([x["fieldId"] for x in self.all_obe_fields])
        self.putDepsInAllOBEFields()
        self.RESULTS = self._flattenAllOBEFieldsListForCSV()
        # self.logger.info('Flattened OBE Fields List: {}'.format(json.dumps(self.RESULTS[:5], indent=2)))
        filename = (
            "OBE_Field_Dependencies"
            if not self.options.customSearch
            else "Field_Dependencies"
        )
        return (
            self.saveResultsToCSV2(fileName=filename)
            if self.options.save
            else "...Not saving results"
        )

    def putFieldIdsInOBEFieldsList(self):
        sortedObeFields = sorted(self.all_obe_fields, key=lambda k: k["sobject"])
        for row in sortedObeFields:
            sobjectAPIName = row["sobject"]
            custObjExt = ("__c", "__e")
            isCustomObj = sobjectAPIName.endswith(custObjExt)
            isPCField = row["name"].endswith("__pc")
            if isCustomObj:
                sobj = (
                    sobjectAPIName.removesuffix(custObjExt[0])
                    if sobjectAPIName.endswith(custObjExt[0])
                    else sobjectAPIName.removesuffix(custObjExt[1])
                )
            else:
                sobj = sobjectAPIName
            fieldSuffix = "__pc" if isPCField else "__c"
            fieldName = row["name"].removesuffix(fieldSuffix)
            if isPCField:
                sobjId = "Contact"
            else:
                sobjId = (
                    [
                        x["TableEnumOrId"]
                        for x in self.ALL_CUSTOM_OBJECTS_DATA
                        if x["DeveloperName"] == sobj
                    ][0]
                    if isCustomObj
                    else sobj
                )
            fieldId = [
                x["fieldId"]
                for x in self.ALL_CUSTOM_FIELDS_DATA
                if x["DeveloperName"] == fieldName and x["TableEnumOrId"] == sobjId
            ]
            if len(fieldId) == 0:
                self.logger.error(
                    "Could not find fieldId for {}.{}".format(sobj, fieldName)
                )
                self.logger.info("Last row: {}".format(row))
                exit()
            row["fieldId"] = fieldId[0]
        filtered = filter(lambda x: x["sobject"] != "Contact", sortedObeFields)
        self.all_obe_fields = list(filtered)
        fieldsWithoutId = [x for x in self.all_obe_fields if "fieldId" not in x]
        assert len(fieldsWithoutId) == 0
        # self.logger.info('OBE fields without fieldIds: {}'.format(len(fieldsWithoutId)))
        # self.logger.info('OBE fields with fieldIds: {}'.format(len(self.all_obe_fields)))
        self.pt.log("...Done associating fieldIds to OBE fields")

    def putDepsInAllOBEFields(self):
        for row in self.all_obe_fields:
            deps = [
                {
                    "CompId": x["MetadataComponentId"],
                    "CompType": x["MetadataComponentType"],
                    "CompName": x["MetadataComponentName"],
                }
                for x in self.DEP_DATA
                if x["RefMetadataComponentId"] == row["fieldId"]
            ]
            # hasCustomFieldDep = False
            for dep in deps:
                compName = (
                    dep["CompName"]
                    if dep["CompType"] != "CustomField"
                    else self._getCustomFieldCompoundName(dep["CompId"])
                )
                dep["CompName"] = compName
                # if(dep['CompType'] == 'CustomField'):
                #     hasCustomFieldDep = True
            row["dependencies"] = deps
            # if(hasCustomFieldDep and row['sobject'] in ['Contact','Account']):
            #     self.logger.info('{}'.format(json.dumps(row, indent=2)))
        self.pt.log("...Done putting OBE dependencies in OBE fields")

    def _hasNoDupeFieldIds(self):
        visited = set()
        dupes = {
            x["fieldId"]
            for x in self.all_obe_fields
            if x["fieldId"] in visited or (visited.add(x["fieldId"]) or False)
        }
        dupes = [x for x in self.all_obe_fields if x["fieldId"] in dupes]
        hasDupeIds = len(visited) > 0
        if hasDupeIds:
            # self.logger.error(json.dumps(dupes, indent=2))
            self.logger.error("{} Duplicate fieldIds found!".format(len(dupes)))
        return hasDupeIds is False

    def getObeDeps(self):
        customSObjectNames = set(
            [
                x["sobject"].removesuffix("__c")
                for x in self.all_obe_fields
                if x["sobject"].endswith("__c")
            ]
        )
        customFieldApiNames = set(
            [
                x["name"].removesuffix(("__c", "__pc"))
                for x in self.all_obe_fields
                if x["name"].endswith(("__c", "__pc"))
            ]
        )
        self.getOBESObjectData(customSObjectNames)
        self.standardSObjects = list(
            set(
                [
                    x["sobject"]
                    for x in self.all_obe_fields
                    if not x["sobject"].endswith(("__c", "__e"))
                ]
            )
        )
        self.objectIds = list(
            set([x["TableEnumOrId"] for x in self.CUSTOM_OBJECTS_DATA])
        )
        self.objectIds.extend(self.standardSObjects)
        self.getOBECustomFields(customFieldApiNames)
        # self.logger.info(self.CUSTOM_FIELDS_DATA)
        self.getOBEDependencies(
            fieldIds=[x["fieldId"] for x in self.CUSTOM_FIELDS_DATA]
        )
        self.processDepData()
        self.logger.info("Retrieved {} dependencies".format(len(self.RESULTS)))
        self.pt.log("...Done getting OBE dependencies")

    def getOBESObjectData(self, customSObjects=None):
        if customSObjects is None:
            return self.getAllCustomObjects()
        query = "SELECT Id, DeveloperName FROM CustomObject c WHERE c.DeveloperName In "
        splitIds = self.splitIds(customSObjects, query=query, maxNumberOfIds=50)
        query = query + str(tuple(splitIds["left"])) + " LIMIT 2000"
        self.logger.info(query)
        customObjects = self.tooling.query_all(query)
        self.CUSTOM_OBJECTS_DATA.extend(
            [
                {"TableEnumOrId": x["Id"], "DeveloperName": x["DeveloperName"]}
                for x in customObjects["records"]
            ]
        )
        if len(splitIds["right"]) > 0:
            self.getOBESObjectData(splitIds["right"])

    def getOBECustomFields(self, customFieldIds):
        query = "SELECT Id, DeveloperName, TableEnumOrId FROM CustomField c WHERE c.DeveloperName In "
        splitIds = self.splitIds(customFieldIds, query=query, maxNumberOfIds=50)
        spl1 = str(tuple(splitIds["left"]))
        spl2 = str(tuple(self.objectIds))
        query = f"{query} {spl1} AND c.TableEnumOrId IN {spl2} ORDER BY TableEnumOrId, DeveloperName"  # query + spl1 + ' AND c.TableEnumOrId In ' + spl2 + ' LIMIT 2000'
        customFields = self.tooling.query_all(query)
        self.CUSTOM_FIELDS_DATA.extend(
            [
                {
                    "fieldId": x["Id"],
                    "DeveloperName": x["DeveloperName"],
                    "TableEnumOrId": x["TableEnumOrId"],
                }
                for x in customFields["records"]
            ]
        )
        if len(splitIds["right"]) > 0:
            self.getOBECustomFields(splitIds["right"])

    def getOBEDependencies(self, fieldIds):
        query = """SELECT MetadataComponentId, 
        MetadataComponentName, 
        MetadataComponentType, 
        RefMetadataComponentId, 
        RefMetadataComponentName, 
        RefMetadataComponentType 
        FROM MetadataComponentDependency 
        Where RefMetadataComponentType IN ('CustomField') AND RefMetadataComponentId """.replace(
            "\n        ", ""
        )
        splitIds = self.splitIds(fieldIds, query=query)
        ids = makeInClauseFromList(splitIds["left"])
        query = f"""{query} IN {ids} ORDER BY MetadataComponentType, MetadataComponentName LIMIT 2000"""
        results = self.tooling.query_all(query)
        if len(results["records"]) > 0:
            self.DEP_DATA.extend(results["records"])
        if len(splitIds["right"]) > 0:
            self.getOBEDependencies(splitIds["right"])
        else:
            self.pt.log("...Done getting OBE dependencies")

    def processDepData(self):
        customFieldDependency = list(
            set(
                [
                    x["MetadataComponentId"]
                    for x in self.DEP_DATA
                    if x["MetadataComponentType"] == "CustomField"
                ]
            )
        )
        if len(customFieldDependency) > 0:
            if len(self.ALL_CUSTOM_FIELDS_DATA) == 0:
                self.getAllCustomFields()
            if len(self.ALL_CUSTOM_OBJECTS_DATA) == 0:
                self.getAllCustomObjects()
            # use MetadataComponentId to get CustomFields and Object names

        for x in self.DEP_DATA:
            reffieldId = x["RefMetadataComponentId"]
            reffieldObjectName = self._getObjectAPINameFromFieldId(reffieldId)
            refcompoundName = self._getCustomFieldCompoundName(reffieldId)
            isContactField = reffieldObjectName == "Contact"
            compType = x["MetadataComponentType"]
            compName = (
                x["MetadataComponentName"]
                if x["MetadataComponentType"] != "CustomField"
                else self._getCustomFieldCompoundName(x["MetadataComponentId"])
            )
            dep = {compType: compName}
            self._appendToResults(refcompoundName, dep)
            if isContactField:
                self._appendToResults(
                    self._getCustomFieldCompoundName(reffieldId, True), dep
                )
        if len(self.RESULTS.items()) > 0:
            self.RESULTS = OrderedDict(sorted(self.RESULTS.items(), key=lambda t: t[0]))
            self.saveResultsCSV()
        return self.RESULTS

    def _appendToResults(self, compoundName, dep):
        if compoundName not in self.RESULTS.keys():
            self.RESULTS[compoundName] = [dep]
        else:
            if dep not in self.RESULTS[compoundName]:
                self.RESULTS[compoundName].append(dep)
            else:
                return
        return self.RESULTS

    def _getCustomFieldCompoundName(self, fieldId, getPCField=False):
        objectName = self._getObjectAPINameFromFieldId(fieldId, getPCField)
        developerName = self._getFieldAPINameFromFieldId(fieldId, getPCField)
        return f"{objectName}.{developerName}"

    def _getFieldAPINameFromFieldId(self, fieldId, getPCField=False):
        isContactField = self._getObjectAPINameFromFieldId(fieldId) == "Contact"
        developerName = [
            x["DeveloperName"]
            for x in self.ALL_CUSTOM_FIELDS_DATA
            if x["fieldId"] == fieldId
        ][0]
        fieldSuffix = "__pc" if getPCField and isContactField else "__c"
        return f"{developerName}{fieldSuffix}"

    def _getObjectAPINameFromFieldId(self, fieldId, getPCField=False):
        objectName = [
            x["TableEnumOrId"]
            for x in self.ALL_CUSTOM_FIELDS_DATA
            if x["fieldId"] == fieldId
        ][0]
        if (getPCField) and (objectName == "Contact"):
            return "Account"
        if objectName.startswith("0"):
            objectName = [
                x["DeveloperName"]
                for x in self.ALL_CUSTOM_OBJECTS_DATA
                if x["TableEnumOrId"] == objectName
            ][0] + "__c"
        return objectName

    def makeResultsUnique(self):
        for k, v in self.RESULTS.items():
            self.RESULTS[k] = list(set(v))

    def saveResultsCSV(self, fileName="OBE_Field_Dependencies"):
        folder = os.path.join(self.output_dir, self.org_config.name.upper())
        filepath = os.path.join(folder, os.path.basename(fileName) + ".csv")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(
                "CompoundName,SObject,FieldApiName,MetadataComponentType,MetadataComponentName\n"
            )
            for key in self.RESULTS.keys():
                compSplit = key.split(".")
                # row = f"{key},{compSplit[0]},{compSplit[1]},{self.RESULTS[key][0][0]},{self.RESULTS[key][0][1]}\n"
                for x in self.RESULTS[key]:
                    for y in x.keys():
                        row = f"{key},{compSplit[0]},{compSplit[1]},{y},{x[y]}\n"
                        f.write(row)

    def saveResultsToCSV2(self, fileName="OBE_Field_Dependencies"):
        timestr = time.strftime("%Y%m%d_%H%M%S_")
        saveFile = "{}{}".format(timestr, fileName)
        folder = os.path.join(self.output_dir, self.org_config.name.upper())
        folder = os.path.join(
            folder, ("customSearch" if self.options.fields else "OBE")
        )
        filepath = os.path.join(folder, os.path.basename(saveFile) + ".csv")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        dict_list = self.RESULTS
        with open(filepath, "w", newline="") as f:
            dict_writer = csv.DictWriter(f, fieldnames=dict_list[0].keys())
            dict_writer.writeheader()
            dict_writer.writerows(dict_list)
        return filepath

    def getAllCustomFieldDeps(self):
        self.logger.info(
            "Getting dependencies for org: {}".format(self.org_config.name)
        )
        query = """SELECT MetadataComponentId,
                            MetadataComponentName,
                            MetadataComponentType,
                            RefMetadataComponentId,
                            RefMetadataComponentName,
                            RefMetadataComponentType
                            FROM MetadataComponentDependency
                            Where RefMetadataComponentType in ('CustomField')"""
        results = self.tooling.query_all(query)
        self.DEP_DATA = list(results["records"])
        customFieldIds = set([x["RefMetadataComponentId"] for x in self.DEP_DATA])
        self.retrieveCustomFields(customFieldIds)
        customObjectIds = set(
            [
                x["TableEnumOrId"]
                for x in self.CUSTOM_FIELDS_DATA
                if x["TableEnumOrId"].startswith("0")
            ]
        )
        self.retrieveCustomObjects(customObjectIds)
        self.processDepData()

    def retrieveCustomFields(self, ids=None):
        if ids is None:
            return self.getAllCustomFields()
        query = """SELECT Id, TableEnumOrId, DeveloperName FROM CustomField c WHERE c.Id In """
        splitIds = self.splitIds(ids, query=query)
        query = query + str(tuple(splitIds["left"])) + " LIMIT 2000"
        customFields = self.tooling.query_all(query)
        self.CUSTOM_FIELDS_DATA.extend(
            [
                {"fieldId": x["Id"], "TableEnumOrId": x["TableEnumOrId"]}
                for x in customFields["records"]
            ]
        )
        if len(splitIds["right"]) > 0:
            self.retrieveCustomFields(splitIds["right"])

    def retrieveCustomObjects(self, ids=None):
        if ids is None:
            self.CUSTOM_OBJECTS_DATA = self.getAllCustomObjects()
            return self.CUSTOM_OBJECTS_DATA
        query = "SELECT Id, DeveloperName FROM CustomObject c WHERE c.Id In "
        splitIds = self.splitIds(ids, query=query)
        query = query + str(tuple(splitIds["left"])) + " LIMIT 2000"
        customObjects = self.tooling.query_all(query)
        self.CUSTOM_OBJECTS_DATA.extend(
            [
                {"TableEnumOrId": x["Id"], "DeveloperName": x["DeveloperName"]}
                for x in customObjects["records"]
            ]
        )
        if len(splitIds["right"]) > 0:
            self.retrieveCustomObjects(splitIds["right"])

    def getAllCustomObjects(self):
        self.logger.info(
            "Getting Custom Objects for org: {}".format(self.org_config.name)
        )
        query = "SELECT Id, DeveloperName FROM CustomObject c ORDER BY DeveloperName"
        customObjects = self.tooling.query_all(query)
        self.ALL_CUSTOM_OBJECTS_DATA = [
            {"TableEnumOrId": x["Id"], "DeveloperName": x["DeveloperName"]}
            for x in customObjects["records"]
        ]
        return self.ALL_CUSTOM_OBJECTS_DATA

    def getAllCustomFields(self):
        self.logger.info(
            "Getting Custom Fields for org: {}".format(self.org_config.name)
        )
        query = "SELECT Id, DeveloperName, TableEnumOrId FROM CustomField WHERE NamespacePrefix = '' ORDER BY TableEnumOrId, DeveloperName"
        customFields = self.tooling.query_all(query)
        self.ALL_CUSTOM_FIELDS_DATA = [
            {
                "fieldId": x["Id"],
                "DeveloperName": x["DeveloperName"],
                "TableEnumOrId": x["TableEnumOrId"],
            }
            for x in customFields["records"]
        ]
        # self.logger.info(['{}.{}'.format(x['TableEnumOrId'], x['DeveloperName']) for x in self.ALL_CUSTOM_FIELDS_DATA if x['TableEnumOrId']=='Contact'])
        return self.CUSTOM_FIELDS_DATA

    def addFieldIdToObeFields(self):
        for x in self.OBE_FIELDS:
            x["fieldId"] = [
                y["fieldId"]
                for y in self.ALL_CUSTOM_FIELDS_DATA
                if y["DeveloperName"] == x["DeveloperName"]
            ][0]

    def getAllFieldSets(self):
        self.logger.info("Getting Field Sets for org: {}".format(self.org_config.name))
        query = "SELECT Id, DeveloperName, EntityDefinitionId FROM FieldSet WHERE NamespacePrefix = '' ORDER BY DeveloperName"
        fieldSets = self.tooling.query_all(query)
        self.ALL_FIELD_SETS_DATA = [
            {"fieldSetId": x["Id"], "DeveloperName": x["DeveloperName"]}
            for x in fieldSets["records"]
        ]
        return self.ALL_FIELD_SETS_DATA

    def splitIds(self, ids, query, maxNumberOfIds=0):
        idsList = list(ids)
        maxURIlength = 12000
        idNumChars = 23
        index = 0
        if (maxNumberOfIds) and (len(idsList) > maxNumberOfIds):
            index = maxNumberOfIds
        else:
            if ((len(idsList) * idNumChars) + len(query)) > maxURIlength:
                index = math.floor((maxURIlength - len(query)) / idNumChars)
            else:
                index = len(idsList)
        allIds = {"left": idsList[0:index], "right": idsList[index:]}
        return allIds

    def _flattenAllOBEFieldsListForCSV(self):
        flattenedList = []
        for row in self.all_obe_fields:
            for dep in row["dependencies"]:
                # generate a new row for each dependency with the values from the parent row
                r = {k: row[k] for k in row.keys() if not isinstance(row[k], list)}
                for k, v in dep.items():
                    # k = f'dep_{k}'
                    r[k] = v
                # reorder the keys for CSV
                flattenedList.append(
                    {
                        "OBE_field_CompId": r["fieldId"],
                        # "OBE_field_Compound_Name": f"{r['sobject']}.{r['name']}",
                        "OBE_field_SObject": r["sobject"],
                        "OBE_field_APIName": r["name"],
                        "OBE_field_Label": r["label"],
                        "OBE_field_Type": r["type"],
                        "DEP_ComponentType": r["CompType"],
                        "DEP_ComponentName": r["CompName"],
                        "DEP_ComponentId": r["CompId"],
                    }
                )
        return flattenedList

    def _init_api(self, base_url=None):
        rv = get_simple_salesforce_connection(
            self.project_config,
            self.org_config,
            api_version=None,
            base_url=base_url,
        )

        return rv


if __name__ == "__main__" or __name__ == "<run_path>":
    fr = getDependencies()
    fr.run()
else:
    # print(str(__name__))
    pass
