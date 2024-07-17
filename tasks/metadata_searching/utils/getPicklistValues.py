# Command:
# cci org shell acudev --script ./SchemaQueries/getPicklistValues.py
from pprint import pp
from cumulusci.salesforce_api.org_schema import get_org_schema
import json
import pickle as pickle
import csv
import time
from os import path
from logging import getLogger


from utils.fastSchema import fastSchema
from utils.timer import timer


class optionsClass:
    save = False  # setting to false will print to console
    filename = "picklistResults"
    ext = "csv"  # 'csv' or 'json'
    sobj = []  # query all sobj or specif ex: ['Account','Contact']
    labels = []
    fieldApiNames = []
    fieldApiNamesLike = []
    field_type = "ALL"  # Can be custom, standard - anything else defaults to all
    queryCache = True
    updateCache = False
    fromTemplate = False

    def __getattr__(self, item):
        try:
            return self[item]
        except Exception as ex:
            print(f"Error: {ex}")
            return None

    """
    To search for specific picklists where the label of the field contains text:
    - Add the field label text to the labels list below.
    - Lists with multiple values are combined using %
    To return all picklist-type fields without a label filter:
    - Pass in an empty array or comment it out
    """


options = optionsClass()
# options.sobj=['Account'] #query all sobj or specify: ['Account','Contact']
# options.labels=['marital']

start = time.time()


class picklister:

    fs = None
    values = None

    def printTime(self, str="Elapsed Time: ", start=start):
        timer().log(str, start)

    def __init__(self, **kwargs):
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
        sql = self.genQuery(field_type=options.field_type).replace(
            "        ", ""
        )  # clean up console display
        self.logger.info(f"SQL QUERY: \n**************{sql}\n*************")
        self.fs = fastSchema()
        self.values = self.run(sql)

    def run(self, sql):
        self.logger.info("Getting org_schema connection...")
        if not options.queryCache:
            self.logger.info(" * Loading picklist values from local cache *")
            with self.fs.get_local_schema(self.org_config) as org_schema:
                if org_schema.session is None:
                    self.logger.info(" * No local cache found *")
                    with get_org_schema(
                        options.sf, self.org_config, force_recache=options.updateCache
                    ) as org_schema:
                        return self.parsePicklistValues(
                            self.fs.query_Schema(org_schema, sql)
                        )
                else:
                    return self.parsePicklistValues(
                        self.fs.query_Schema(org_schema, sql)
                    )
        else:
            with get_org_schema(
                options.sf, self.org_config, force_recache=options.updateCache
            ) as org_schema:
                return self.parsePicklistValues(self.fs.query_Schema(org_schema, sql))

    def parsePicklistValues(self, result):
        rowarray_list = []
        parseTimeStart = time.time()
        for row in list(result):
            fieldData = self.processRow(row)
            rowarray_list.extend(fieldData)
        self.printTime("Time to parse rows:", parseTimeStart)
        if eval(options.save):
            self.saveData(rowarray_list)
            self.printTime("DONE!")
        else:
            self.logger.info(json.dumps(rowarray_list, indent=2))

        return rowarray_list

    def processRow(self, row):
        sobj = row["sobject"]
        fieldApiName = row["name"]
        label = row["label"]
        compound = f"{sobj}.{fieldApiName}"
        restrictedPicklist = row["restrictedPicklist"]
        rows = []
        pickled = row["picklistValues"]
        picklistValues = pickle.loads(pickled)
        field = {
            "sobject": sobj,
            "fieldApiName": fieldApiName,
            "compound": compound,
            "fieldLabel": label,
            "isRestrictedPicklist": restrictedPicklist,
        }
        if options.ext == "json":
            field["picklistValues"] = picklistValues
            rows.append(field)
        else:
            for pldict in picklistValues:
                del pldict["validFor"]
                plvalue_as_row = field | pldict
                rows.append(plvalue_as_row)
        return rows

    def saveData(self, data):
        if len(data) == 0:
            self.logger.info("Query did not find any results")
        else:
            filename = f"reports/{options.filename}.{options.ext}"
            filepath = path.realpath(filename)
            self.logger.info(f"Saving to {filepath}")
            if options.ext == "json":
                data_file = open(filepath, "w")
                json.dump(data, data_file, indent=2)
                data_file.close()
            else:
                try:
                    with open(filepath, "w", newline="") as output_file:
                        dict_writer = csv.DictWriter(
                            output_file,
                            extrasaction="ignore",
                            fieldnames=data[0].keys(),
                        )
                        dict_writer.writeheader()
                        dict_writer.writerows(data)
                except IOError:
                    self.logger.error("I/O error")

    def filterArray(self, arr):
        self.logger.info(arr)
        return list(filter(lambda s: len(s) > 3, arr))

    def genQuery(self, field_type="ALL", ftype="picklist"):
        SOBJ = self.filterArray(options.sobj)
        ANDNOTLIKE = """ AND sobject NOT LIKE '%ChangeEvent' 
         AND sobject NOT LIKE '%\\_\\_History' ESCAPE '\\'
         AND sobject NOT LIKE '%\\_\\_Share' ESCAPE '\\'"""

        q = f"""
        SELECT sobject, name, label, restrictedPicklist, picklistValues
        FROM fields 
        WHERE type='picklist' 
        { " AND custom " 
            if field_type=='custom' 
            else (" AND custom=0 " 
                if field_type=='standard'  
                else "") }"""
        try:
            if len(SOBJ) > 1:
                sep = "','"
                q += f" AND sobject IN ('{sep.join(SOBJ)}')"
            elif len(SOBJ) == 1:
                q += f" AND sobject='{SOBJ[0]}'"
            else:
                q += ANDNOTLIKE
        except Exception as ex:
            self.logger.debug(f"Error: {ex}")
            q += ANDNOTLIKE

        try:
            fieldNames = self.filterArray(options.fieldApiNames)
            if len(fieldNames) > 1:
                sep = "','"
                q += f" AND name IN ('{sep.join(options.fieldApiNames)}')"
            elif len(fieldNames) == 1:
                q += f" AND name='{fieldNames[0]}'"
            else:
                pass
        except Exception as ex:
            self.logger.debug(f"Error: {ex}")
            pass

        try:
            labelsArr = self.filterArray(options.labels)
            LABELSJOINED = "%".join(labelsArr) if len(labelsArr) > 0 else ""
            LABELCLAUSE = (
                f"""\n AND label LIKE '%{LABELSJOINED}%'"""
                if len(options.labels) > 0
                else None
            )
            q = f"""{q} {LABELCLAUSE}""" if LABELCLAUSE else q
        except Exception as ex:
            self.logger.debug(f"Error: {ex}")
            pass

        try:
            namesLike = self.filterArray(options.fieldApiNamesLike)
            APINamesLike = "%".join(namesLike) if len(namesLike) > 0 else ""
            APILikeClause = (
                f"""\n AND name LIKE '%{APINamesLike}%'"""
                if len(APINamesLike) > 0
                else None
            )
            q = f"""{q} {APILikeClause}""" if APILikeClause else q
        except Exception as ex:
            self.logger.debug(f"Error: {ex}")
            pass

        return f"""{q}\nORDER BY sobject, name"""


if __name__ == "<run_path>":
    print("Starting picklist values...")
    picklister(
        save=True,
        queryCache=True,
        updateCache=False,
        org_config=globals()["org_config"],
    )
"""
# total arguments
import sys
n = len(sys.argv)
print("Total arguments passed:", n)
 
# Arguments passed
print("\nName of Python script:", sys.argv[0])
 
print("\nArguments passed:", end = " ")
for i in range(1, n):
    print(sys.argv[i], end = " ")
"""
