from collections import defaultdict
import yaml
import re
import copy

from tasks.data_ops.overrides import init_overrides
from cumulusci.salesforce_api.filterable_objects import NOT_EXTRACTABLE, NOT_COUNTABLE
from cumulusci.salesforce_api.org_schema import get_org_schema, Filters
from cumulusci.tasks.bulkdata.generate_mapping import GenerateMapping
from cumulusci.core.utils import process_bool_arg

generate_options = copy.deepcopy(GenerateMapping.task_options)
generate_options["exclude_setup_objects"] = {
    "description": "Include setup objects in the mapping",
    "required": False,
}


class GenerateFullMapping(GenerateMapping):

    task_options = generate_options
    exclude_setup_objects = True

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.options["ignore"] = self.options.get("ignore", [])
        self.ignore = self.options["ignore"]
        self.options["strip_namespace"] = self.options.get("strip_namespace", False)
        self.options["break_cycles"] = self.options.get("break_cycles", 'auto')
        self.exclude_setup_objects = process_bool_arg(
            self.options.get("exclude_setup_objects", True)
        )

    def _run_task(self):
        always_include = ["User", "Group"]
        self.logger.info("Collecting sObject information")
        self.get_all_objects = len(self.options["include"]) == 0
        self.toolingObjects = [f['name'] for f in self.tooling.describe()["sobjects"] if f['name'] not in always_include]
        self.apisobjects = [f["name"] for f in self.sf.describe()["sobjects"]] + always_include
        self.not_extractable = [f for f in NOT_EXTRACTABLE if f not in always_include] + self.ignore

        self.not_extractable += self.toolingObjects if self.exclude_setup_objects else []
        
        self.not_extractable = list(set(self.not_extractable))
        self.not_extractable.sort()

        objects_to_include = self.options["include"] if not self.get_all_objects else self.apisobjects + self.toolingObjects

        # self.logger.info(f"not_extractable objects: {self.not_extractable}")

        with get_org_schema(sf=self.sf, 
                            org_config=self.org_config,
                            include_counts=False,
                            included_objects=objects_to_include,
                            force_recache=False,
                            ) as org_schema:
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
        self.mapping_objects = []  # self.options["include"]

        # First, we'll get a list of all objects that are either
        # (a) custom, no namespace
        # (b) custom, with our namespace
        # (c) not ours (standard or other package), but have fields with our namespace or no namespace
        for objname, obj in org_schema.items():
            if obj is not None and objname not in self.not_extractable and self._is_object_mappable(obj) and objname not in self.mapping_objects:
                self.mapping_objects.append(objname)

        if self.get_all_objects:
            # no need to find references if we're getting everything
            self.logger.info("Including all objects")
            return
        # Add any objects that are required by our own,
        # meaning any object we are looking up to with a custom field,
        # or any master-detail parent of any included object.
        index = 0
        while index < len(self.mapping_objects):
            obj = self.mapping_objects[index]
            for field in org_schema[obj].fields.values():
                if field["type"] == "reference":
                    if field["relationshipOrder"] == 1 or self._is_any_custom_api_name(
                        field["name"]
                    ):
                        self.mapping_objects.extend(
                            [
                                obj
                                for obj in field["referenceTo"]
                                if obj not in self.mapping_objects
                                and obj not in self.not_extractable
                                and self._is_object_mappable(org_schema[obj])
                            ]
                        )

            index += 1

    def _simplify_schema(self, org_schema):
        """Override to exclude compound fields and include Ids

        Simplify and filter schema, including field details and interobject
        references, into self.simple_schema and self.refs"""
        self.simple_schema = {}
        self.refs = defaultdict(lambda: defaultdict(dict))

        # ignorelist = [f["name"] for f in self.tooling.describe()["sobjects"] if f["name"] not in ["User", "Group"]]
        for obj in self.mapping_objects:
            # self.logger.info(f"Processing {obj}")
            self.simple_schema[obj] = {}
            compoundFields = set([f"{c}" for c in 
                                 [field["compoundFieldName"] for field in org_schema[obj]["fields"].values() 
                                  if field["compoundFieldName"] 
                                  and field["compoundFieldName"] != "Name"
                                  ]])
            # if len(list(compoundFields)) > 0:
            #     self.logger.info(f"Compound fields ignored in {obj}: {[f for f in compoundFields]}")

            for field in org_schema[obj]["fields"].values():
                if self._is_field_mappable(obj, field, compoundFields):
                    self.simple_schema[obj][field["name"]] = field

                    if field["type"] == "reference":
                        for target in field["referenceTo"]:
                            # We've already vetted that this field is referencing
                            # included objects, via `_is_field_mappable()`
                            if target != obj:
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
                if obj in NOT_EXTRACTABLE and field["name"] not in ("Id") and obj != "RecordType":
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
                any(
                    re.match(pat.replace("%", ".*"), obj["name"], re.IGNORECASE) for pat in self.not_extractable
                ),
                obj["name"] in self.options["ignore"],  # User-specified exclusions
                obj["name"].endswith(
                    "ChangeEvent"
                ),  # Change Data Capture entities (which get custom fields)
                obj["name"].endswith("__mdt"),  # Custom Metadata Types (MDAPI only)
                obj["name"].endswith("__e"),  # Platform Events
                obj["customSetting"],  # Not Bulk API compatible
                obj["name"]  # Objects we can't or shouldn't load/save
                in [
                    # "User",  # we want to include User Ids
                    # "Group", # we want to include Group Ids
                    "LookedUpFromActivity",
                    "OpenActivity",
                    "Task",
                    "Event",
                    "ActivityHistory",
                ],
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
                field["name"] in compoundFieldNames 
                and field["name"] != "Name",
                # field["name"] == "Id",  # Omit Id fields for auto-pks # we need record ids for extracts
                f"{obj}.{field['name']}" in self.options["ignore"],  # User-ignored list
                "(Deprecated)" in field["label"],  # Deprecated managed fields
                field["type"] == "base64",  # No Bulk API support for base64 blob fields
                # not field["createable"],  # Non-writeable fields # comment out for formula and system fields
                field["type"] == "reference"  # Outside lookups
                and not self._are_lookup_targets_in_operation(field),
            ]
        )
