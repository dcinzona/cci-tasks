from cumulusci.salesforce_api.metadata import ApiListMetadata
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.salesforce_api.org_schema_models import SObject
from cumulusci.core.utils import process_bool_arg, process_list_arg
import inspect


def get_boolean_attribute_names(cls):
    """
    Returns a list of attribute names of a class that are of type boolean.
    """
    return [name for name, value in inspect.getmembers(cls) if not name.startswith('_') and name.endswith('able')]


class GetSObjects(BaseSalesforceApiTask):
    api_class = ApiListMetadata
    task_options = {
        "include_tooling": {
            "description": "Include objects from the Tooling API",
            "required": False,
        },
        "filters": {
            "description": "A list of filters to apply to the list of objects such as 'queryable, createable'",
            "required": False,
        },
        "print": {
            "description": "Print out the results",
            "required": False,
        },
    }

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.print_results = process_bool_arg(self.options.get("print", False))
        self.includeTooling = process_bool_arg(
            self.options.get("include_tooling", False)
        )
        self.filters = process_list_arg(self.options.get("filters", []))
        boolean_attributes = get_boolean_attribute_names(SObject)
        for f in self.filters:
            if f not in boolean_attributes:
                raise ValueError(
                    f"\nFilter '{f}' is invalid. \nValid filters include: {boolean_attributes}."
                )

    def _check_object_filter(self, obj):
        return all([obj[f] for f in self.filters])

    def _run_task(self):
        # return_values = self._get_components()
        # objects = [f"{o['MemberName']}" for o in return_values]
        # objects.sort()
        apiobjects = [obj for obj in self.sf.describe()["sobjects"] if obj['associateEntityType'] not in ("ChangeEvent", "Share", "History", "Feed")]
        # for obj in apiobjects:
        #     self.logger.info(f"Object: {obj['name']}")
        #     for key, value in obj.items():
        #         self.logger.info(f"  {key}: {value}")
        # exit()
        if self.includeTooling:
            toolingobjects = self.tooling.describe()["sobjects"]
            self.return_values = set([
                o["name"]
                for o in (apiobjects + toolingobjects)
                if all([o[f] for f in self.filters]) is True
            ])
        else: 
            self.return_values = set(
                [
                    o["name"]
                    for o in apiobjects
                    if all([o[f] for f in self.filters]) is True
                ]
            )

        self.return_values = sorted(self.return_values)

        if self.print_results:
            for obj in self.return_values:
                self.logger.info(obj)
            self.logger.info(f"\nFound {len(self.return_values)} objects")

        return list(self.return_values)

        # describeList = [f for f in self.sf.describe()["sobjects"]
        #                 if f["queryable"] is True
        #                 and f["createable"] is True
        #                 # and f["keyPrefix"] is not None
        #                 ]

        # validObjects = []
        # for obj in describeList:
        #     sobj = obj["name"]
        #     if sobj not in validObjects:
        #         validObjects.append(sobj)

        # self.return_values = validObjects
        # return self.return_values

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
