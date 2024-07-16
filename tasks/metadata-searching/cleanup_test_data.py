from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from pprint import pprint
from datetime import datetime
import json


def find(key, dictionary):
    for k, v in dictionary.items():
        if k == key:
            yield v
        elif isinstance(v, dict):
            for result in find(key, v):
                yield result
        elif isinstance(v, list):
            for d in v:
                for result in find(key, d):
                    yield result


class cleanupTestData(BaseSalesforceApiTask):
    userId = ""
    byMeFilter = ""
    bulk = None

    def _run_task(self):
        self.bulk = self.sf.bulk
        self.userId = self.org_config.config["userinfo"]["user_id"]
        self.byMeFilter = f"CreatedById='{self.userId}' AND CreatedDate=LAST_N_DAYS:1"
        data = self.sf.query_all(
            f"SELECT Id \
        FROM Account WHERE {self.byMeFilter}"
        )

        accountsNoQuotes = list(set(list(find("Id", data))))
        accounts = []
        for row in accountsNoQuotes:
            accounts.append(f"'{row}'")

        if len(accounts) > 0:
            pprint(json.dumps(accounts, indent=2))
            pprint(json.dumps(self.updateAddresses(accounts), indent=2))
            pprint(json.dumps(self.deleteAllRecords(accountsNoQuotes), indent=2))

        return

    def updateAddresses(self, accounts):
        adrs = self.bulk.Address__c.query(
            f"SELECT Id, Current_Address__c FROM Address__c WHERE Person_Account1__c in ({','.join(accounts)}) AND Current_Address__c = true"
        )
        for record in adrs:
            # record_id = record["Id"]
            dt = datetime.today().isoformat().split("T")[0]
            record["Current_Address__c"] = False
            record["End_Date__c"] = dt
            # self.sf.Address__c.update(record_id, {"Current_Address__c": False, "End_Date__c": dt})
        result = self.bulk.Address__c.update(adrs)
        return result

    def deleteAllRecords(self, accounts):
        data = self.sf.query_all(
            f"SELECT \
        (SELECT Id from Account.Accession_Details__r), \
        (SELECT Id FROM Account.Academic_Tests_Details__r), \
        (SELECT Id From Account.Addresses1__r), \
        (SELECT Id FROM Account.Opportunities), \
        (SELECT Id FROM Account.Military_Test_Scores__r), \
        (SELECT Id FROM Academic_Test_Summaries__r), \
        (SELECT Id FROM ASVAB_Test_Details__r), \
        Name \
        FROM Account WHERE {self.byMeFilter}"
        )
        # pprint(json.dumps(data, indent = 2))
        allIds = list(set(list(find("Id", data))))

        delResult = []
        delFailed = False
        if len(allIds) > 0:
            # jsonstring1 = json.dumps(allIds, indent = 2)
            params = dict(ids=",".join(allIds), allOrNone=True)
            # TRY DELETING ALL IDS USING
            # Method:DELETE URI:/composite/sobjects?ids=001xx000003DGb2AAG,003xx000004TmiQAAS&allOrNone=false
            try:
                delResult.append(
                    self.sf.restful(
                        method="DELETE", path="composite/sobjects", params=params
                    )
                )
            except Exception as e:
                delFailed = True
                print(e)

        if delFailed:
            return delResult

        if len(accounts) > 0:
            # jsonstring1 = json.dumps(allIds, indent = 2)
            params = dict(ids=",".join(accounts), allOrNone=True)
            # TRY DELETING ALL IDS USING
            # Method:DELETE URI:/composite/sobjects?ids=001xx000003DGb2AAG,003xx000004TmiQAAS&allOrNone=false
            try:
                delResult.append(
                    self.sf.restful(
                        method="DELETE", path="composite/sobjects", params=params
                    )
                )
            except Exception as e:
                print(f"Error {e}")

        return delResult
