from cumulusci.salesforce_api.metadata import ApiListMetadata
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.salesforce_api.org_schema import SObject
from cumulusci.core.utils import process_bool_arg, process_list_arg
from cumulusci.salesforce_api.org_schema import Filters, get_org_schema
from tasks.data_ops.filterable_objects import (
    check_dictobject_filter,
    filter_objects_by_pattern,
)
import inspect 

other_filters = ["custom", "customSetting", "deprecatedAndHidden", "feedEnabled", "hasSubtypes", "isInterface", "isSubtype", "mruEnabled"]


def get_boolean_attribute_names(cls):
    """
    Returns a list of attribute names of a class that are of type boolean.
    """
    return sorted([name for name, value in inspect.getmembers(cls) if not name.startswith('_') and name.endswith('able')] + other_filters)


def get_valid_filters_str(filterlist=get_boolean_attribute_names(SObject)):
    return "\n - " + "\n - ".join(filterlist)


class GetSObjects(BaseSalesforceApiTask):
    api_class = ApiListMetadata

    valid_filters = get_boolean_attribute_names(SObject)

    task_options = {
        "include_tooling": {
            "description": "Include objects from the Tooling API",
            "required": False,
        },
        "filters": {
            "description": f"""A list of filters to apply to the list of objects. 
            {get_valid_filters_str(valid_filters)}

            """,
            "required": False,
        },
        "print": {
            "description": "Print out the results",
            "required": False,
        },
        "show_attributes": {
            "description": "Show the attributes of the SObject model",
            "required": False,
        },
        "check_schema": {
            "description": "Check the schema for the objects",
            "required": False,
        },
    }

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.print_results = process_bool_arg(self.options.get("print", False))
        self.check_schema = process_list_arg(self.options.get("check_schema"))
        self.show_attributes = process_bool_arg(
            self.options.get("show_attributes", False)
        )
        self.includeTooling = process_bool_arg(
            self.options.get("include_tooling", False)
        )
        self.filters = process_list_arg(self.options.get("filters", []))
        for f in self.filters:
            if f not in self.valid_filters:
                raise ValueError(
                    f"\nFilter '{f}' is invalid. \nValid filters include: {get_valid_filters_str(self.valid_filters)}."
                )

    def _run_task(self):
        objects = [obj for obj in self.sf.describe()["sobjects"] if obj['associateEntityType'] not in ("ChangeEvent", "Share", "History", "Feed")]
        if self.includeTooling:
            objects += self.tooling.describe()["sobjects"]

        if self.filters:
            objects = [obj for obj in objects if check_dictobject_filter(obj, self.filters)]

        assert any(objects), "No objects found"
        objects = sorted(objects, key=lambda x: x["name"])
        self.return_values = [f for f in filter_objects_by_pattern(objects)]

        if self.check_schema:
            filters = (
                [getattr(Filters, f) for f in self.filters if f in self.filters]
                if self.filters is not None
                else [Filters.queryable]
            )
            with get_org_schema(self.sf, org_config=self.org_config, filters=filters) as org_schema:
                for obj in self.check_schema:
                    sobj = org_schema[obj]
                    if sobj is None:
                        self.logger.warning(f"Schema not found for {obj}")
                        continue
                    fields = sobj.fields.values()
                    for field in fields:
                        self.logger.info(f"{obj}.{field.name}")
                        if self.show_attributes:
                            for name, value in sorted(field.__dict__.items()):
                                self.logger.info(f"   - {name}: {value}")
                            return list(self.return_values)

            return list(self.return_values)

        if self.show_attributes:
            self.logger.info(f"\nFound {len(self.return_values)} objects")
            firstobj = self.return_values[0]
            for key, value in firstobj.items():
                self.logger.info(f"{key}: {value}")
            # for field in firstobj["fields"].values():
            #     self.logger.info(f" - {field} ({field.type})")
            #     for name, value in field.__dict__.items():
            #         if name.startswith("_") or callable(value):
            #             continue
            #         self.logger.info(f"   {name}: {value}")
            return list(self.return_values)

        if self.print_results:
            for obj in self.return_values:
                self.logger.info(obj["name"])
            self.logger.info(f"\nFound {len(self.return_values)} objects")
            return list(self.return_values)

        return list(self.return_values)

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
