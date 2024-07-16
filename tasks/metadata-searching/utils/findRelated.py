import pickle
from cumulusci.cli.runtime import CliRuntime
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
import json
from utils.fastSchema import fastSchema
from utils.timer import timer


class findRelated:
    logger = None

    def __init__(self, org_name=None):
        self.pt = timer()
        runtime = CliRuntime(load_keychain=True)
        name, org_config = runtime.get_org(org_name)  # gets the default cci org
        self.sf = get_simple_salesforce_connection(runtime.project_config, org_config)
        self.fs = fastSchema()
        self.logger = org_config.logger
        self.go(org_config)

    def go(self, org_config, relationshipName="%Reservation%"):
        with self.fs.get_local_schema(org_config) as org_schema:
            self.pt.log("Time to load schema: ")
            q = f"""SELECT 
                fields.sobject 
                , sobjects.label sobjectLabel
                , fields.name fieldApiName
                , fields.label fieldLabel
                , relationshipName
                , type
                , referenceTo
                from fields 
                JOIN sobjects on fields.sobject = sobjects.name
                WHERE 
                fields.type = 'reference' AND 
                relationshipName LIKE '{relationshipName}' 
                """
            print(q)
            result = self.fs.query_Schema(org_schema=org_schema, sql=q)
            self.pt.log("Time to query: ")
            rowarray_list = []
            for row in result.all():
                if row:
                    rowarray_list.append(
                        [
                            x if type(x).__name__ != "bytes" else pickle.loads(x)
                            for x in row
                        ]
                    )
            # print(list(result))
            prettyjson = json.dumps(rowarray_list, indent=2)
            print(prettyjson)
            self.pt.log("Done! ")


if __name__ == "__main__" or __name__ == "<run_path>":
    fr = findRelated()
else:
    print(str(__name__))
