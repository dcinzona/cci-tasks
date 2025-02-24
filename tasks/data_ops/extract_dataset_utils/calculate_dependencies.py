import typing as T

from cumulusci.salesforce_api.filterable_objects import NOT_EXTRACTABLE, NOT_COUNTABLE
from cumulusci.salesforce_api.org_schema import Schema

from .synthesize_extract_declarations import (
    SimplifiedExtractDeclaration,
    synthesize_declaration_for_sobject,
)


class SObjDependency(T.NamedTuple):
    table_name_from: str
    table_names_to: T.Union[str, T.Tuple[str, ...]]
    field_name: str
    priority: bool = False


def _calculate_dependencies_for_declarations(
    decls: T.Sequence[SimplifiedExtractDeclaration], schema: Schema
) -> T.Dict[str, T.List[SObjDependency]]:
    """Ensure that required lookups are fulfilled for list of SimplifiedExtractDeclarations

    Do this by adding their referent tables (in full) to the extract.
    Module-internal helper function.
    """
    dependencies = {}
    for decl in decls:
        assert isinstance(decl.sf_object, str)
        only_required_fields = decl.sf_object in NOT_EXTRACTABLE
        new_dependencies = _collect_dependencies_for_sobject(
            decl.sf_object, decl.fields, schema, only_required_fields=only_required_fields
        )
        dependencies.update(new_dependencies)
    return dependencies


def _collect_dependencies_for_sobject(
    source_sfobject: str,
    fields: T.List[str],
    schema: Schema,
    only_required_fields: bool,
) -> T.Dict[str, T.List[SObjDependency]]:
    """Ensure that required lookups are fulfilled for a single SObject

    Do this by adding its referent tables (in full) to the extract.
    Module-internal helper function.
    """
    dependencies = {}
    for field_name in fields:
        field_info = schema[source_sfobject].fields[field_name]
        # if not field_info.createable:  # pragma: no cover
        #     continue
        references = field_info.referenceTo
        if references:
            # Remove RecordType from references
            if "RecordType" in references:
                references.remove("RecordType")
                if not references:
                    continue

            targets = tuple(
                target for target in references if target not in NOT_COUNTABLE
            )
            field_disallowed = not targets  # or (source_sfobject == "User" and field_name != "Id")
            field_allowed = not (only_required_fields or field_disallowed)
            if field_info.requiredOnCreate or field_allowed:
                dependencies.setdefault(source_sfobject, []).append(
                    SObjDependency(
                        source_sfobject,
                        targets,
                        field_name,
                        field_info.requiredOnCreate,
                    )
                )

    return dependencies


def extend_declarations_to_include_referenced_tables(
    decl_list: T.Sequence[SimplifiedExtractDeclaration], schema: Schema
) -> T.Sequence[SimplifiedExtractDeclaration]:
    """Extend the declarations to complete required or requested lookups recursively"""
    decls = {decl.sf_object: decl for decl in decl_list}
    dependencies = _calculate_dependencies_for_declarations(decl_list, schema)
    to_process = list(decls.keys())

    while to_process:
        sf_object = to_process.pop()
        assert isinstance(sf_object, str)
        my_dependencies = dependencies.get(sf_object, ())
        for dep in my_dependencies:
            target_tables = dep.table_names_to
            for target_table in target_tables:
                sobj = schema.get(target_table)
                target_extractable = (
                    sobj and sobj.queryable
                )
                if target_table not in decls and target_extractable:                        
                    required_fields = [
                        field.name
                        for field in schema[target_table].fields.values()
                    ]

                    decls[target_table] = synthesize_declaration_for_sobject(
                        target_table, required_fields, schema[target_table].fields
                    )

                    new_dependencies = _collect_dependencies_for_sobject(
                        target_table,
                        decls[target_table].fields,
                        schema,
                        only_required_fields=False,
                    )
                    dependencies.update(new_dependencies)
                    to_process.append(target_table)

    return list(decls.values())
