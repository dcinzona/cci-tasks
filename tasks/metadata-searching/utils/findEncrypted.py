from cumulusci.cli.runtime import CliRuntime
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.salesforce_api.org_schema import get_org_schema
import json
import time

start = time.time()


def printTime(str='Total Time: ', start=start):    
    end = time.time()
    timeRounded = "{:.2f}".format(end - start)
    print(f" {str} {timeRounded} seconds")


RUNTIME = CliRuntime()

runtime = CliRuntime(load_keychain=True)
name, org_config = runtime.get_org()
sf = get_simple_salesforce_connection(runtime.project_config, org_config)

printTime('elapsed time before get_org_schema')
with get_org_schema(sf, org_config) as org_schema:
    printTime('Time to get org_schema: ')
    # q = "SELECT sobjects.name, fields.Name FROM sobjects JOIN fields ON fields.sobject=SObjects.name WHERE fields.encrypted "
    q = "SELECT json_object('sobject', sobject \
        , 'fields', json_group_array(name)) \
        FROM fields \
        WHERE encrypted \
        GROUP BY sobject"
    result = org_schema.session.execute(q)
    rowarray_list = []
    for row in result.all():
        t = json.loads(row[0])
        rowarray_list.append(t)
    # print(list(result))
    prettyjson = json.dumps(rowarray_list, indent=2)
    # print(prettyjson)
    printTime('Total Time: ')
