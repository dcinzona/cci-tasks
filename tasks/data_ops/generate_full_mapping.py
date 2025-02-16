from collections import defaultdict
import yaml
import copy

from tasks.data_ops.overrides import init_overrides
from tasks.data_ops.filterable_objects import NOT_EXTRACTABLE, sobject_is_valid
from cumulusci.salesforce_api.org_schema import Filters, get_org_schema
from cumulusci.tasks.bulkdata.generate_mapping import GenerateMapping
from cumulusci.core.utils import process_bool_arg, process_list_arg
from cumulusci.core.exceptions import TaskOptionsError

generate_options = copy.deepcopy(GenerateMapping.task_options)
generate_options["exclude_setup_objects"] = {
    "description": "Include setup objects in the mapping",
    "required": False,
}


class GenerateFullMapping(GenerateMapping):

    task_options = generate_options
    exclude_setup_objects = True

    def _init_options(self, kwargs):
        init_overrides()
        super(GenerateFullMapping, self)._init_options(kwargs)

        if "namespace_prefix" not in self.options:
            self.options["namespace_prefix"] = ""

        if self.options["namespace_prefix"] and not self.options[
            "namespace_prefix"
        ].endswith("__"):
            self.options["namespace_prefix"] += "__"

        self.options["ignore"] = process_list_arg(self.options.get("ignore", []))
        break_cycles = self.options.setdefault("break_cycles", "ask")
        if break_cycles not in ["ask", "auto"]:
            raise TaskOptionsError(
                f"`break_cycles` should be `ask` or `auto`, not {break_cycles}"
            )
        self.options["include"] = process_list_arg(self.options.get("include", []))
        strip_namespace = self.options.get("strip_namespace")

        self.options["strip_namespace"] = process_bool_arg(
            True if strip_namespace is None else strip_namespace
        )
        self.exclude_setup_objects = process_bool_arg(
            self.options.get("exclude_setup_objects", True)
        )

    def _run_task(self):
        self.logger.info("Running GenerateFullMapping\n")
        self.logger.info("...Collecting SObject information")
        self.sobjects = [f["name"] for f in self.sf.describe()["sobjects"]]
        self.logger.info("...Collecting Tooling Object information")
        self.toolingObjects = [f['name'] for f in self.tooling.describe()["sobjects"]]
        self.not_extractable = [f for f in NOT_EXTRACTABLE] + self.options["ignore"]

        if not self.exclude_setup_objects:
            self.sobjects += self.toolingObjects

        self.not_extractable = list(set(self.not_extractable))
        self.not_extractable.sort()

        self.logger.info("...Apply extractable filter checks")
        self.valid_schema_objects = set(
            o
            for o in self.sobjects
            if sobject_is_valid(o, patterns=self.not_extractable)
        )

        if not any(self.options['include']):
            self.logger.info("No objects specified so including all valid objects")
            self.options['include'] = self.valid_schema_objects

        with get_org_schema(
            sf=self.sf,
            org_config=self.org_config,
            include_counts=False,
            included_objects=self.valid_schema_objects,
            filters=[Filters.queryable, Filters.createable],
            force_recache=False,
        ) as org_schema:
            self.valid_schema_objects = set(org_schema.keys())
            self.valid_included_objects = set(self.options["include"]).intersection(
                self.valid_schema_objects
            )
            assert "User" in self.valid_schema_objects, "User object not found in org"
            if not self.valid_included_objects:
                raise TaskOptionsError(
                    f"No valid objects to include in the mapping.  Valid objects are: {self.sobjects}"
                )
            self._collect_objects(org_schema)
            self._simplify_schema(org_schema)
        filename = self.options["path"]
        self.logger.info(f"Creating mapping schema {filename}")
        self._build_mapping()
        self.return_values = {"mapping": self.mapping}
        self.logger.info(f"Mapping schema has {len(self.mapping)} entries")
        with open(filename, "w") as f:
            yaml.dump(self.mapping, f, sort_keys=False)

    def _collect_objects(self, org_schema):
        """Walk the global describe and identify the sObjects we need to include in a minimal operation."""

        self.mapping_objects = self.options['include']
        unknown_objects = set(self.mapping_objects) - self.valid_schema_objects

        if unknown_objects:
            raise TaskOptionsError(f"{unknown_objects} cannot be found in the org.")

        # sorted_objects = sorted(self.valid_schema_objects)
        # self.logger.info(sorted_objects)
        # self.logger.info(f"Number of objects: {len(self.valid_schema_objects)}")
        # exit()
        # If we weren't given any objects to map, we'll start with all
        # First, we'll get a list of all objects that are either
        if not any(self.mapping_objects):
            for objname, obj in org_schema.items():
                if obj is not None and self._is_object_mappable(obj) and objname not in self.mapping_objects:
                    self.mapping_objects.append(objname)
            return
        # else:  # Let's find objects that we require
        #     for obj in self.mapping_objects:
        #         for field in org_schema[obj].fields.values():
        #             if field["type"] == "reference":
        #                 new_objects = [
        #                     obj
        #                     for obj in field["referenceTo"]
        #                     if obj not in self.mapping_objects and obj in self.valid_schema_objects
        #                 ]
        #                 if any(new_objects):
        #                     self.logger.info(f"Adding {new_objects} for {obj}.{field['name']}")
        #                     self.mapping_objects.extend(new_objects)

        # Add any objects that are required by our own,
        # meaning any object we are looking up to with a custom field,
        # or any master-detail parent of any included object.
        index = 0
        while index < len(self.mapping_objects):
            obj = self.mapping_objects[index]
            for field in org_schema[obj].fields.values():
                if field["type"] == "reference":
                    # if field["relationshipOrder"] == 1 or self._is_any_custom_api_name(
                    #     field["name"]
                    # ):
                    new_objects = [
                        obj
                        for obj in field["referenceTo"]
                        if obj not in self.mapping_objects and obj in self.valid_schema_objects
                    ]
                    if any(new_objects):                                
                        self.logger.info(f"Adding {new_objects} for {obj}.{field['name']}")
                        self.mapping_objects.extend(new_objects)

            index += 1

    def _simplify_schema(self, org_schema):
        self.logger.info("...Simplifying schema")
        """Override to exclude compound fields and include Ids

        Simplify and filter schema, including field details and interobject
        references, into self.simple_schema and self.refs"""
        self.simple_schema = {}
        self.refs = defaultdict(lambda: defaultdict(dict))

        # ignorelist = [f["name"] for f in self.tooling.describe()["sobjects"] if f["name"] not in ["User", "Group"]]
        for obj in self.mapping_objects:
            # self.logger.info(f"Processing {obj}")
            self.simple_schema[obj] = {}

            for field in org_schema[obj]["fields"].values():
                if self._is_field_mappable(obj, field):
                    self.simple_schema[obj][field["name"]] = field

                    if field["type"] == "reference":
                        for target in field["referenceTo"]:
                            # We've already vetted that this field is referencing
                            # included objects, via `_is_field_mappable()`
                            if target != obj and target not in ("User", "Group"):
                                self.refs[obj][target][field["name"]] = field

                if (
                    field["name"] == "RecordTypeId"
                    and org_schema[obj].recordTypeInfos
                    and len(org_schema[obj].recordTypeInfos) > 1
                ):
                    # "Master" is included even if no RTs.c
                    self.simple_schema[obj][field["name"]] = field

    def _build_mapping(self):
        """Output self.simple_schema in mapping file format by constructing a dict and serializing to YAML"""
        objs = list(self.simple_schema.keys())

        stack = self._split_dependencies(objs, self.refs)
        ns = self.project_config.project__package__namespace

        def strip_namespace(element):
            if self.options["strip_namespace"] and ns and element.startswith(f"{ns}__"):
                return element[len(ns) + 2:]
            else:
                return element

        self.mapping = {}
        self.logger.info("...Building mapping stacks")
        for orig_obj in stack:
            # Check if it's safe for us to strip the namespace from this object
            stripped_obj = strip_namespace(orig_obj)
            obj = stripped_obj if stripped_obj not in stack else orig_obj
            key = f"Extract {obj}"
            self.mapping[key] = {}
            self.mapping[key]["sf_object"] = obj
            self.mapping[key]["table"] = obj
            fields = ["Id"]  # need Id first for ExtractData maps to work
            lookups = []
            for field in self.simple_schema[orig_obj].values():
                """Enables lookup references to be populated to non-extactable objects"""
                if not sobject_is_valid(obj) and field["name"] not in ("Id") and obj != "RecordType":
                    continue
                if field["type"] == "reference" and field["name"] != "RecordTypeId":
                    # For lookups, namespace stripping takes place below.
                    lookups.append(field["name"]) if len(field["referenceTo"]) > 0 else None
                else:
                    fields.append(field["name"]) if field["name"] not in fields else None
            if fields:
                fields_stripped = [
                    strip_namespace(f) if strip_namespace(f) not in fields else f
                    for f in fields
                ]
                # fields_stripped.sort()
                self.mapping[key]["fields"] = fields_stripped
            if lookups:
                lookups.sort()
                self.mapping[key]["lookups"] = {}
                for orig_field in lookups:
                    # First, determine what manner of lookup we have here.
                    stripped_field = (
                        strip_namespace(orig_field)
                        if strip_namespace(orig_field) not in lookups
                        else orig_field
                    )
                    referenceTo = self.simple_schema[orig_obj][orig_field][
                        "referenceTo"
                    ]

                    # Can we safely namespace-strip this reference?
                    stripped_references = [
                        strip_namespace(orig_reference)
                        if strip_namespace(orig_reference) not in stack
                        else orig_reference
                        for orig_reference in referenceTo
                    ]

                    # The maximum reference index to set the after to the last
                    # sobject mentioned in the reference (polymorphic support)
                    try:

                        max_reference_index = max(
                            stack.index(orig_reference) for orig_reference in referenceTo
                        )
                        if max_reference_index >= stack.index(orig_obj):  # Dependent lookup
                            self.mapping[key]["lookups"][stripped_field] = {
                                "table": stripped_references,
                                "after": f"Insert {stripped_references[referenceTo.index(stack[max_reference_index])]}",
                            }
                        else:  # Regular lookup
                            self.mapping[key]["lookups"][stripped_field] = {
                                "table": stripped_references
                            }
                    except ValueError:
                        self.logger.info(
                            f"Reference {orig_field} in {orig_obj} to {referenceTo} not in stack"
                        )

    def _is_object_mappable(self, obj):
        """True if this object is one we can map, meaning it's an sObject and not
        some other kind of entity, it's not ignored, it's Bulk API compatible,
        and it's not in a hard-coded list of entities we can't currently handle."""

        return not any(
            [
                not sobject_is_valid(obj=obj, patterns=self.not_extractable),
                # obj["name"] in self.options["ignore"],  # User-specified exclusions
                # obj["name"].endswith(
                #     "ChangeEvent"
                # ),  # Change Data Capture entities (which get custom fields)
                # obj["name"].endswith("__mdt"),  # Custom Metadata Types (MDAPI only)
                # obj["name"].endswith("__e"),  # Platform Events
                # obj["customSetting"],  # Not Bulk API compatible
                # obj["name"]  # Objects we can't or shouldn't load/save
                # in [
                #     # "User",  # we want to include User Ids
                #     # "Group", # we want to include Group Ids
                #     "LookedUpFromActivity",
                #     "OpenActivity",
                #     "Task",
                #     "Event",
                #     "ActivityHistory",
                # ],
            ]
        )

    def _is_field_mappable(self, obj, field, compoundFieldNames: set = ()):
        """True if this field is one we can map, meaning it's not ignored,
        it's createable by the Bulk API, it's not a deprecated field,
        and it's not a type of reference we can't handle without special
        configuration (self-lookup or reference to objects not included
        in this operation)."""
        return not any(
            [
                field["compoundFieldName"] and field["compoundFieldName"] != "Name",
                # field["name"] == "Id",  # Omit Id fields for auto-pks # we need record ids for extracts
                f"{obj}.{field['name']}" in self.options["ignore"],  # User-ignored list
                "(Deprecated)" in field["label"],  # Deprecated managed fields
                field["type"] == "base64",  # No Bulk API support for base64 blob fields
                # not field["createable"],  # Non-writeable fields # comment out for formula and system fields
                field["type"] == "reference"  # Outside lookups
                and not self._are_lookup_targets_in_operation(field),
            ]
        )
