
from cumulusci.salesforce_api.metadata import ApiListMetadata
from cumulusci.tasks.salesforce import BaseSalesforceApiTask


class GetSObjects(BaseSalesforceApiTask):
    api_class = ApiListMetadata

    def _run_task(self):
        return_values = self._get_components()
        objects = [f"{o['MemberName']}" for o in return_values]
        objects.sort()
        describeList = [f for f in self.sf.describe()["sobjects"] 
                        if f["queryable"] is True
                        and f["createable"] is True
                        and f["keyPrefix"] is not None
                        ]

        validObjects = []
        for obj in describeList:
            sobj = obj["name"]
            if sobj in objects and sobj not in validObjects:
                validObjects.append(sobj)
        
        self.return_values = validObjects
        return self.return_values

    def _get_components(self):
        list_components = []
        for md_type in ["CustomObject"]:
            api_object = self.api_class(
                self, metadata_type=md_type, as_of_version=self.project_config.project__package__api_version
            )
            components = api_object()
            for temp in components[md_type]:
                cmp = {
                    "MemberType": md_type,
                    "MemberName": temp["fullName"],
                    "lastModifiedByName": temp["lastModifiedByName"],
                    "lastModifiedDate": temp["lastModifiedDate"],
                }
                if cmp not in list_components:
                    list_components.append(cmp)
        return list_components
