from collections import defaultdict
import yaml
import copy

from cumulusci.salesforce_api.filterable_objects import NOT_EXTRACTABLE
from cumulusci.salesforce_api.org_schema import get_org_schema
from cumulusci.tasks.bulkdata.generate_mapping import GenerateMapping
generate_options = copy.deepcopy(GenerateMapping.task_options)


class GenerateFullMapping(GenerateMapping):

    task_options = generate_options

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.options["ignore"] = self.options.get("ignore", [])
        self.options["strip_namespace"] = self.options.get("strip_namespace", False)
        self.options["break_cycles"] = self.options.get("break_cycles", 'auto')

    def _run_task(self):
        self.logger.info("Collecting sObject information")
        with get_org_schema(self.sf, self.org_config) as org_schema:
            self._collect_objects(org_schema)
            self._simplify_schema(org_schema)
        filename = self.options["path"]
        self.logger.info(f"Creating mapping schema {filename}")
        self._build_mapping()
        self.return_values = {"mapping": self.mapping}
        with open(filename, "w") as f:
            yaml.dump(self.mapping, f, sort_keys=False)

    def _simplify_schema(self, org_schema):
        """Override to exclude compound fields and include Ids

        Simplify and filter schema, including field details and interobject
        references, into self.simple_schema and self.refs"""
        self.simple_schema = {}
        self.refs = defaultdict(lambda: defaultdict(dict))
        for obj in self.mapping_objects:
            self.simple_schema[obj] = {}
            compoundFields = set([f"{c}" for c in 
                                 [field["compoundFieldName"] for field in org_schema[obj]["fields"].values() 
                                  if field["compoundFieldName"] 
                                  and field["compoundFieldName"] != "Name"
                                  ]])
            if len(list(compoundFields)) > 0:
                self.logger.info(f"Compound fields ignored in {obj}: {[f for f in compoundFields]}")

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
            fields = []
            lookups = []
            for field in self.simple_schema[orig_obj].values():
                if obj in NOT_EXTRACTABLE and field["name"] not in ("Id"):  # Enables lookup references to be populated to non-extactable objects
                    continue
                if field["type"] == "reference" and field["name"] != "RecordTypeId":
                    # For lookups, namespace stripping takes place below.
                    lookups.append(field["name"])
                else:
                    fields.append(field["name"])
            if fields:
                fields_stripped = [
                    strip_namespace(f) if strip_namespace(f) not in fields else f
                    for f in fields
                ]
                fields_stripped.sort()
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

    def _is_field_mappable(self, obj, field, compoundFieldNames: set = ()):
        """Override to exclude compound fields and include Id."""
        return not any(
            [
                field["name"] in compoundFieldNames 
                and field["name"] != "Name",  # Compound fields
                f"{obj}.{field['name']}" in self.options["ignore"],  # User-ignored list
                "(Deprecated)" in field["label"],  # Deprecated managed fields
                field["type"] == "base64",  # No Bulk API support for base64 blob fields
                field["type"] == "reference"  # Outside lookups
                and not self._are_lookup_targets_in_operation(field),
            ]
        )
