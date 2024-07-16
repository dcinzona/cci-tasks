# Command:
# cci task run find_obe
import os
from pprint import pp
from cumulusci.salesforce_api.org_schema import get_org_schema
from utils.general import makeInClauseFromList
import yaml
import csv
import glob
from collections import defaultdict
from logging import getLogger
from snowfakery import api
from utils.fastSchema import fastSchema
from utils.timer import timer
from snowfakery import parse_recipe_yaml


class optionsClass:
    save = False  # setting to false will print to console
    queryCache = True
    updateCache = False
    fromTemplate = False

    def __getattr__(self, item):
        try:
            return self[item]
        except Exception as ex:
            print(f"Error: {ex}")
            return None


options = optionsClass()

output_dir = os.path.join(os.getcwd(), "reports", "obe")
macroFolder = os.path.join(".", "datasets", "macros")
macros = {
    "Address__c": "address.macro.yml",
    "Account": "account.macro.yml",
    "Academic_Test_Summary__c": "Academic_test_summary.macro.yml",
    "Academic_Tests_Detail__c": "Academic_test_summary.macro.yml",
    "Accession_Details__c": "Accession_Details.macro.yml",
    "Applicant_Citizenship__c": "applicant_citizenship.macro.yml",
    "ASVAB_Test_Details__c": "ASVAB_test_details.macro.yml",
    "Foreign_Language__c": "Foreign_Language.macro.yml",
    "Military_Test_Score__c": "Military_test_score.macro.yml",
    "Military_Service__c": "Military_Service.macro.yml",
    "Opportunity": "opportunity.macro.yml",
    "Reservation__c": "Reservation.macro.yml",
}
recipes = os.path.join(".", "datasets", "TempRes", "**", "*.yml")


class findOBE:
    fieldsFound = defaultdict(list)
    orgname = None
    soqlFields = ["sobject", "name", "label", "type"]
    allObeFields = []
    allObeFieldsBySOBJ = defaultdict(list)

    def __init__(self, **kwargs):
        self.pt = timer()
        for k, v in kwargs.items():
            options.__setattr__(k, v)
        if options.org_config:
            self.org_config = options.org_config
            self.logger = self.org_config.logger
            self.sf = options.sf
        else:
            try:
                self.org_config = globals()["org_config"]
                self.logger = self.org_config.logger
            except Exception as ex:
                pp("*** Error loading org_config ***")
                pp(ex)
                exit(1)
        if options.fromTemplate:
            self.logger = getLogger(__name__)
        self.orgname = self.org_config.name
        self.fs = fastSchema()
        self.options = options

    def run(self):
        self.getAllOBEFields()
        o = self.orgname.upper()
        allObeFieldsFilename = (
            f"{o}_Specified_Objects_OBE_Fields"
            if self.options.sobjects
            else f"{o}_All_OBE_Fields"
        )
        msg = (
            f"Saved OBE Fields found for {self.options.sobjects} in {o} to "
            if self.options.sobjects
            else f"Saved OBE Fields found for all objects in {o} to "
        )
        self.saveToCSV(self.allObeFields, filename=allObeFieldsFilename, message=msg)
        self.logger.info("...Parsing macros for OBE fields")
        for row in self.allObeFields:
            self.findOBEInMacros(row)
        self.findOBEInRecipes()
        self.setUniqueFields()
        self.parseFieldsFound()

    def getAllOBEFields(self, sql=None):
        if sql is None:
            sql = self.genQuery()
        sql = sql.replace("        ", "")  # clean up console display
        self.logger.info(f"SQL QUERY: \n**************{sql}\n*************")
        self.allObeFields = list(self.runQuery(sql))
        for row in self.allObeFields:
            self.allObeFieldsBySOBJ[row["sobject"]].append(row)
        return self.allObeFields

    def parseFieldsFound(self):
        total = 0
        files = []
        for k, v in self.fieldsFound.items():
            sobj = None
            if len(v) > 0:
                self.logger.warning(f"Found OBE Fields in {k}")
            for fields in v:
                if sobj != fields[0]:
                    sobj = fields[0]
                    self.logger.warn(f"  SOBJECT: {sobj}")
                total += 1
                self.logger.warn(f"   - {(fields[1],fields[2])}")
            files.append(
                (
                    k,
                    self.saveToCSV(
                        [
                            {
                                "sobject": x[0],
                                "fieldApiName": x[1],
                                "fieldLabel": x[2],
                                "file": k,
                            }
                            for x in v
                        ],
                        filename=k,
                    ),
                )
            )
        if len(files) > 0:
            self.logger.info(f"Found {total} OBE Fields in {len(files)} files")
            self.logger.info(
                "------------------------------------------------------\n"
            )
            for k, v in files:
                self.logger.info(f"- File: '{k}'\n> Report: '{v}'\n")
        else:
            self.logger.info(f"Found {total} OBE Fields")
        self.logger.info("------------------------------------------------------\n")
        self.pt.log("Completed task in")

    def saveToCSV(self, rowarray_list, filename, headers=None, message=None):
        if len(rowarray_list) == 0:
            return
        folder = os.path.join(output_dir, self.org_config.name.upper())
        if self.options.sobjects:
            folder = os.path.join(folder, "customSearch")
        filepath = os.path.join(folder, os.path.basename(filename) + ".csv")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as csvfile:
            fieldnames = rowarray_list[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rowarray_list:
                writer.writerow(row)
        if message:
            self.logger.info(f"\n{message} {filepath}\n\n")
        else:
            self.logger.info(f"\nSaved OBE Fields to {filepath}\n\n")
        return filepath

    def genQuery(self):
        sobjects = "AND sobject NOT LIKE '%ChangeEvent' "
        if self.options.sobjects:
            sobjects = f"AND sobject IN {makeInClauseFromList(self.options.sobjects)} "
        sql = f"""
        SELECT {','.join(self.soqlFields)}
        FROM fields 
        WHERE custom 
         AND label LIKE '%OBE%'
         {sobjects}
        ORDER BY sobject, name"""
        return sql

    def findOBEInMacros(self, row):
        sobj = row["sobject"]
        fieldApiName = row["name"]
        fieldLabel = row["label"]
        if macros.keys().__contains__(sobj):
            file = macroFolder + macros[sobj]
            self.parseMacro(
                file, sobj=sobj, fieldApiName=fieldApiName, fieldLabel=fieldLabel
            )

    # parse recipes too
    def findOBEInRecipes(self):
        self.logger.info(f"...Parsing Recipes {recipes}\n")
        for file in glob.iglob(recipes, recursive=True):
            self.parseRecipe(file)

    def parseRecipe(self, file):
        with api.open_file_like(file, mode="r") as (path, f):
            data = parse_recipe_yaml.parse_recipe(f)
            recipeObjects = sorted(data.tables.keys())
            usedSObjects = list(
                filter(lambda x: x in self.allObeFieldsBySOBJ.keys(), recipeObjects)
            )
            for k in usedSObjects:
                t = data.tables[k]
                fields = sorted(t.fields.keys())
                obeFields = list(
                    filter(
                        lambda x: x in [y["name"] for y in self.allObeFieldsBySOBJ[k]],
                        fields,
                    )
                )
                obelabels = [
                    (x["name"], x["label"])
                    for x in self.allObeFieldsBySOBJ[k]
                    if x["name"] in obeFields
                ]
                if len(obeFields) > 0:
                    for field in obeFields:
                        label = [x[1] for x in obelabels if x[0] == field][0]
                        self.fieldsFound[file].append((k, field, label))

    def parseMacro(self, file, sobj, fieldApiName, fieldLabel):
        if os.path.exists(file):
            with open(file, "r") as f:
                data = yaml.load(f, Loader=yaml.FullLoader)
                for yml in data:
                    if yml.keys().__contains__("object"):
                        pp(yml["object"])
                        self.logger.warning(
                            f"Found object reference in macro {file}...Skipping"
                        )
                        continue
                    if yml.keys().__contains__("fields"):
                        for field in yml["fields"]:
                            if field == fieldApiName:
                                self.fieldsFound[file].append(
                                    (sobj, fieldApiName, fieldLabel)
                                )

    def setUniqueFields(self):
        for k in self.fieldsFound.keys():
            self.fieldsFound[k] = list(set(self.fieldsFound[k]))

    def runQuery(self, sql):
        self.logger.info("Getting org_schema connection...")
        if options.queryCache or options.updateCache is False:
            self.logger.info(" * Loading values from local cache *")
            with self.fs.get_local_schema(self.org_config) as org_schema:
                if org_schema.session is None:
                    self.logger.info(" * No local cache found *")
                    with get_org_schema(
                        options.sf, self.org_config, force_recache=options.updateCache
                    ) as org_schema:
                        return self.parseRows(self.fs.query_Schema(org_schema, sql))
                else:
                    return self.parseRows(self.fs.query_Schema(org_schema, sql))
        else:
            with get_org_schema(
                options.sf, self.org_config, force_recache=options.updateCache
            ) as org_schema:
                return self.parseRows(self.fs.query_Schema(org_schema, sql))

    def parseRows(self, result):
        rowarray_list = []
        for row in list(result):
            fieldData = self.processRow(row)
            rowarray_list.extend(fieldData)
        self.pt.log("Time to parse rows:")
        return rowarray_list

    def processRow(self, row):
        rows = []
        field = dict(zip(self.soqlFields, row))
        rows.append(field)
        return rows


if __name__ == "<run_path>":
    print("Starting findOBE...")
    pp(globals()["org_config"])
    # findOBE(save=False, queryCache=False, updateCache=True, org_config=globals()['org_config'])
