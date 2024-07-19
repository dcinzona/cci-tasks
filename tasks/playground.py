from cumulusci.tasks.salesforce import DescribeMetadataTypes
from cumulusci.salesforce_api.metadata import ApiListMetadata
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.salesforce_api.org_schema import get_org_schema
from cumulusci.tasks.salesforce.nonsourcetracking import ListComponents
from cumulusci.salesforce_api.metadata import ApiListMetadata
from cumulusci.core.config import TaskConfig
from cumulusci.tasks.salesforce import BaseSalesforceApiTask


class Playground(BaseSalesforceApiTask):
    api_class = ApiListMetadata
    
    def _run_task(self):
        with get_org_schema(
            self.sf,
            self.org_config,
        ) as schema:
            for obj in schema.keys():
                for field in schema[obj]["fields"].values():
                    field.defaultValue = None
                    field.nillable = False
                    field.defaultedOnCreate = False
                    field.createable = True
                        
            for obj in schema.keys():
                fields = [f"{fi['name']}.{fi.requiredOnCreate}" for fi in schema[obj]["fields"].values()]
                self.logger.info(f"Fields in {obj}: { fields }")
            return 
        self.return_values = self._get_components()
        objects = [f"{o['MemberName']}" for o in self.return_values]
        objects.sort()
        describeList = [f for f in self.sf.describe()["sobjects"] 
                        if f["queryable"] is True
                        and f["createable"] is True
                        and f["keyPrefix"] is not None
                        ]
        
        self.logger.info(f"Objects in org: {objects}")

        for obj in describeList:
            sobj = obj["name"]
            if sobj in objects:
                # self.logger.info(f"{sobj} in components")
                continue
            else:
                self.logger.info(f"{sobj} is not in components")
        
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
                    "namespacePrefix": temp["namespacePrefix"] + '__' if temp["namespacePrefix"] is not None else '',
                }
                if cmp not in list_components:
                    list_components.append(cmp)
        return list_components


def _make_task(task_class, project_config, org_config, **options):
    task_config = TaskConfig({"options": options})
    return task_class(project_config, task_config, org_config)
