from cumulusci.salesforce_api.metadata import ApiListMetadata
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.salesforce_api.org_schema_models import SObject, Field
from cumulusci.core.utils import process_bool_arg, process_list_arg
from cumulusci.salesforce_api.org_schema import Filters, get_org_schema
from tasks.data_ops.filterable_objects import (
    check_dictobject_filter,
    filter_objects_by_pattern,
    OPT_IN_ONLY,
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


primitives = (bool, str, int, float, type(None))


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
        "describe": {
            "description": "Show the attributes of the SObject model for the provided list of objects or objects.fields",
            "required": False,
        },
        "check_schema": {
            "description": "Check the schema for differences between the return values and the schema",
            "required": False,
        },
    }

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.print_results = process_bool_arg(self.options.get("print", False))
        self.check_schema = process_bool_arg(self.options.get("check_schema"))
        self.show_attributes = process_list_arg(self.options.get("describe"))

        self.includeTooling = process_bool_arg(
            self.options.get("include_tooling", False)
        )
        self.filters = process_list_arg(
            self.options.get("filters", ["retrieveable", "updateable"])
        )
        for f in self.filters:
            if f not in self.valid_filters:
                raise ValueError(
                    f"\nFilter '{f}' is invalid. \nValid filters include: {get_valid_filters_str(self.valid_filters)}."
                )

    def _run_task(self):
        objects = [obj for obj in self.sf.describe()["sobjects"] if obj['associateEntityType'] not in ("ChangeEvent", "Share", "History", "Feed") and obj['name'] not in OPT_IN_ONLY]
        if self.includeTooling:
            objects += self.tooling.describe()["sobjects"]

        if self.filters:
            objects = [obj for obj in objects if check_dictobject_filter(obj, self.filters)]

        assert any(objects), "No objects found"
        objects = sorted(objects, key=lambda x: x["name"])
        self.return_values = [f for f in filter_objects_by_pattern(objects)]

        if self.show_attributes or self.check_schema:
            self.logger.info("\nChecking schema...")
            filters = (
                [getattr(Filters, f) for f in self.filters if f in self.filters]
                if self.filters is not None
                else [Filters.queryable]
            )

            object_attribute_names = set(k.lower() for k in self.parse_attributes().keys())
            with get_org_schema(self.sf, org_config=self.org_config, filters=filters) as org_schema:
                for objattrname in self.parse_attributes().keys():
                    if objattrname.lower() not in [f['name'].lower() for f in self.return_values]:
                        self.logger.warning(f"Object {objattrname} not found in return values")
                    if objattrname.lower() not in [sobj['name'].lower() for sobj in org_schema.values()]:
                        self.logger.warning(f"Object {objattrname} not found in schema")
                    else:
                        sobj = org_schema[objattrname]
                        print(sobj["name"])
                        self._show_attributes(sobj)

                for sobj in org_schema.values():
                    if sobj['name'] not in [f['name'] for f in self.return_values]:
                        if self.show_attributes and sobj["name"].lower() in object_attribute_names:
                            self.logger.warning(f"Object {sobj['name']} not found in return values")

                if self.check_schema:
                    objects_in_schema = set([sobj for sobj in org_schema.keys()])
                    diff = set(f['name'] for f in self.return_values) ^ objects_in_schema
                    if diff:
                        not_in_schema = sorted(
                            f["name"] for f in self.return_values if f["name"] in diff
                        )
                        not_in_return_values = sorted(f for f in sorted(objects_in_schema) if f in diff)
                        self.logger.warning(
                            f"\nObjects from return values not in schema: {not_in_schema}\n...\nNot in Schema Count: {len(not_in_schema)}"
                        ) if any(not_in_schema) else None
                        self.logger.warning(
                            f"\nObjects from schema not in return values: {not_in_return_values}\n...\nNot in Return Values Count: {len(not_in_return_values)}"
                        ) if any(not_in_return_values) else None
                        self.logger.warning(f"\nTotal delta between schema and return values: {len(diff)}")
                    else:
                        self.logger.info("\nSchema matches return value sets")

            return self.exit_task()

        if self.print_results:
            for obj in self.return_values:
                self.logger.info(obj["name"])
            return self.exit_task()

        return self.exit_task()

    def exit_task(self):
        self.logger.info(f"\nFound {len(self.return_values)} objects")
        return list(self.return_values)

    def parse_attributes(self):
        return_dict = {}
        if self.show_attributes:
            for attrstr in sorted(self.show_attributes):
                objname, fieldname = attrstr.split(".") if "." in attrstr else (attrstr, None)
                if not objname:
                    self.logger.warning("No object name provided")
                    continue
                if objname not in return_dict:
                    return_dict[objname] = set()
                if fieldname:
                    return_dict[objname].add(fieldname)       

        # sort
        for objname in return_dict.keys():
            return_dict[objname] = sorted(return_dict[objname])
        return return_dict

    def _show_attributes(self, sobj: SObject):
        if self.show_attributes:
            # self.logger.info(f"\nShowing attributes for {self.show_attributes}")
            attributes = self.parse_attributes()
            for objname in attributes.keys():
                if sobj['name'].lower() == objname.lower():
                    self.logger.info(f"...Getting attributes for {sobj['name']}\n")
                    fields_to_check = attributes[objname]
                    (
                        self._print_attributes(
                            sobj, f"{objname} (No fields selected)", ""
                        )
                        if not fields_to_check
                        else None
                    )

                    for fieldname in fields_to_check:
                        if '(' in fieldname:
                            fieldtype = fieldname.split('(')[1].replace(')', '').lower()
                            for field in sobj.fields.values():
                                if fieldtype == 'all':
                                    self._print_attributes(field, field.name, "  ")
                                if fieldtype == 'custom':
                                    if field.custom:
                                        self._print_attributes(field, field.name, "  ")
                                if fieldtype == 'standard':
                                    if not field.custom:
                                        self._print_attributes(field, field.name, "  ")
                        else:
                            field = sobj.fields[fieldname]
                            if field:
                                self._print_attributes(field, f"{sobj['name']}.{fieldname}", "")
                            else:
                                self.logger.warning(f"Field {fieldname} not found in {objname}")

    def _print_attributes(self, obj: SObject | Field, header_str: str, indentstr: str = ""):
        self.logger.info(f"{indentstr}{header_str}") if header_str else None
        if obj:
            indentstr = f"{indentstr}   - " if '-' not in indentstr else f"   {indentstr}"

            for key, value in sorted(obj.__dict__.items()):
                if key.startswith("_"):
                    continue
                if isinstance(value, primitives):
                    self.logger.info(f"{indentstr}{key}: {value}")
                else:
                    if key == "fields":
                        indentstr = "   " + indentstr + "(Field) "
                        for field in value.keys():
                            self._print_attributes(None, field, indentstr=indentstr)
                    elif isinstance(value, list):
                        self.logger.info(
                            f"{indentstr}{key}: List<{value.__class__.__name__}>"
                        )
                    elif isinstance(value, set):
                        self.logger.info(f"{indentstr}{key}: Set<{value.__class__.__name__}>")
                    elif isinstance(value, dict):
                        self.logger.info(f"{indentstr}{key}: Dict<{value.__class__.__name__}>")
                    else:
                        self.logger.info(f"{indentstr}{key}: {value.__class__.__name__}")

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
