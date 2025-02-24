import collections
import typing as T

from cumulusci.tasks.bulkdata.extract_dataset_utils.synthesize_extract_declarations import (
    SimplifiedExtractDeclaration,
)

from cumulusci.salesforce_api.org_schema import (
    Field,
    Schema
)

from cumulusci.utils.iterators import partition

from cumulusci.tasks.bulkdata.extract_dataset_utils.extract_yml import (
    ExtractDeclaration,
    SFFieldGroupTypes,
    SFObjectGroupTypes,
)
from cumulusci.tasks.bulkdata.extract_dataset_utils.hardcoded_default_declarations import (
    DEFAULT_DECLARATIONS,
)


def flatten_declarations(
    declarations: T.Iterable[ExtractDeclaration],
    schema: Schema,
    opt_in_only: T.Sequence[str] = (),
) -> T.List[SimplifiedExtractDeclaration]:

    # pretend all fields are required on create

    try:
        for obj in schema.keys():
            for field in schema[obj]["fields"].values():
                field.defaultValue = None
                field.nillable = False
                field.defaultedOnCreate = False
                field.createable = True
        # assert schema.includes_counts, "Schema object was not set up with `includes_counts`"
        simplified_declarations = _simplify_sfobject_declarations(
            declarations, schema, opt_in_only
        )

        from .calculate_dependencies import extend_declarations_to_include_referenced_tables

        simplified_declarations = extend_declarations_to_include_referenced_tables(
            simplified_declarations, schema
        )
    except Exception as e:
        print(e)
        print(declarations)
        return declarations

    return simplified_declarations


def _simplify_sfobject_declarations(
    declarations: T.Iterable[ExtractDeclaration],
    schema: Schema,
    opt_in_only: T.Sequence[str],
) -> T.List[SimplifiedExtractDeclaration]:
    """Generate a new list of declarations such that all sf_object patterns
    (like OBJECTS(CUSTOM)) have been expanded into many declarations
    with specific names and defaults have been merged in."""
    atomic_declarations, group_declarations = partition(
        lambda d: d.is_group, declarations
    )
    atomic_declarations = list(atomic_declarations)
    normalized_atomic_declarations = _normalize_user_supplied_simple_declarations(
        atomic_declarations, DEFAULT_DECLARATIONS
    )
    atomized_declarations = _merge_group_declarations_with_simple_declarations(
        normalized_atomic_declarations, group_declarations, schema, opt_in_only
    )
    simplifed_declarations = [
        _expand_field_definitions(decl, schema[decl.sf_object].fields)
        for decl in atomized_declarations
        if decl.sf_object in schema.keys()
    ]
    return simplifed_declarations


def _merge_group_declarations_with_simple_declarations(
    simple_declarations: T.Iterable[ExtractDeclaration],
    group_declarations: T.Iterable[ExtractDeclaration],
    schema: Schema,
    opt_in_only: T.Sequence[str],
) -> T.List[ExtractDeclaration]:
    """Expand group declarations to simple declarations and merge
    with existing simple declarations"""
    simple_declarations = list(simple_declarations)
    group_declarations = list(group_declarations)

    specific_sobject_decl_names = [obj.sf_object for obj in simple_declarations]

    simplified_declarations = [
        _expand_group_sobject_declaration(decl, schema) for decl in group_declarations
    ]
    for decl_set in simplified_declarations:
        for decl in decl_set:
            already_specified = decl.sf_object in specific_sobject_decl_names
            if not already_specified:
                simple_declarations.append(decl)
            opted_out = decl.sf_object in opt_in_only
            if not (already_specified or opted_out):
                simple_declarations.append(decl)

    return simple_declarations


def _expand_group_sobject_declaration(decl: ExtractDeclaration, schema: Schema):
    """Expand a group sobject declaration to a list of simple declarations"""
    if decl.group_type == SFObjectGroupTypes.standard:

        def matches_obj(obj):
            return not obj.custom

    elif decl.group_type == SFObjectGroupTypes.custom:

        def matches_obj(obj):
            return obj.custom

    elif decl.group_type == SFObjectGroupTypes.all:

        def matches_obj(obj):
            return True

    else:  # pragma: no cover
        assert 0, decl.group_type

    matching_objects = []
    for obj in schema.sobjects:
        if obj.count is None:
            print(f"Count is None for {obj['name']}")
            continue
        if matches_obj(obj) and obj.count >= 1:
            matching_objects.append(obj["name"])
    
    decls = [
        synthesize_declaration_for_sobject(obj, decl.fields, schema[obj].fields)
        for obj in matching_objects
    ]
    return decls


def _expand_field_definitions(
    sobject_decl: ExtractDeclaration, schema_fields: T.Dict[str, Field]
) -> SimplifiedExtractDeclaration:
    """Expand group declarations to concrete ones. e.g. FIELDS(STANDARD) -> "LastName",

    Also include all required fields whether asked for or not.
    """
    simple_declarations, group_declarations = partition(
        lambda d: "(" in d, sobject_decl.fields
    )
    declarations = list(simple_declarations)

    # expand group declarations to concrete ones.
    # e.g. FIELDS(STANDARD) -> "LastName",
    for c in group_declarations:
        declarations.extend(_find_matching_field_declarations(c, schema_fields))

    def required(field):
        defaulted = (
            field.defaultValue is not None or field.nillable or field.defaultedOnCreate
        )
        already_specified = field.name in declarations
        return field.createable and not defaulted and not already_specified

    # add in all of the required fields
    declarations.extend(
        field.name
        for field in schema_fields.values()
        if field.name not in declarations
        # and field.requiredOnCreate
    )

    return SimplifiedExtractDeclaration.from_template_and_fields(
        sobject_decl, fields=declarations
    )


def _find_matching_field_declarations(
    field_group_type: str, schema_fields: T.Dict[str, Field]
) -> T.Iterable[str]:
    """Look in schema for field declarations matching a pattern like "Custom", "Standard", etc."""
    ctype = ExtractDeclaration.parse_field_complex_type(field_group_type)
    assert ctype, f"Could not parse {field_group_type}"  # Should be impossible

    if ctype == SFFieldGroupTypes.standard:
        # find updateable standard fields
        return (field.name for field in schema_fields.values() if not field.custom)
    elif ctype == SFFieldGroupTypes.custom:
        return (field.name for field in schema_fields.values() if field.custom)
    elif ctype == SFFieldGroupTypes.required:
        # required fields are always exported
        return ()
    elif ctype == SFFieldGroupTypes.all:
        return (field.name for field in schema_fields.values())
    else:  # pragma: no cover
        raise NotImplementedError(type)


def synthesize_declaration_for_sobject(
    sf_object: str, fields: list, schema_fields: T.Mapping[str, Field]
) -> SimplifiedExtractDeclaration:
    """Fake a declaration for an sobject that was mentioned
    indirectly"""
    default = DEFAULT_DECLARATIONS.get(sf_object)

    if default:
        expanded_default = _expand_field_definitions(default, schema_fields)
        ret = SimplifiedExtractDeclaration.from_template_and_fields(
            expanded_default, fields
        )
        return ret
    else:
        # if sf_object in OPT_IN_ONLY:
        #     fields = [f["name"] for f in schema_fields.values() if not f["nillable"]] or ["Id"]
        # fields = ["Id"]
        # raise ValueError(
        #     f"Cannot extract {sf_object} because it is not extractable.\n Required fields: {fields}"
        # )
        return SimplifiedExtractDeclaration(sf_object=sf_object, fields=fields)


def _normalize_user_supplied_simple_declarations(
    simple_declarations: T.List[ExtractDeclaration],
    default_declarations: T.Mapping[str, ExtractDeclaration],
) -> T.List[ExtractDeclaration]:
    """Merge info provided by the user with things we already know about each SObject

    For example, if we extract WorkBadgeDefinition, don't extract the
    built-in ones.
    """
    duplicates = _find_duplicates(simple_declarations, lambda x: x.sf_object)

    assert not duplicates, f"Duplicate declarations not allowed: {duplicates}"
    simple_declarations = {
        decl.sf_object: _merge_declarations_with_defaults(
            decl, default_declarations.get(decl.sf_object, _DEFAULT_DEFAULTS)
        )
        for decl in simple_declarations
    }
    return list(simple_declarations.values())


def _find_duplicates(input: T.Iterable[T.Tuple], key: T.Callable[[str], str]):
    """Find duplicates in an iterable"""
    counts = collections.Counter((key(v), v) for v in input)
    duplicates = [name for name, count in counts.items() if count > 1]
    return duplicates


def _merge_declarations_with_defaults(
    user_decl: ExtractDeclaration, default_decl: ExtractDeclaration
):
    """Merge two declarations with one taking priority over the other"""
    default_decl = default_decl or _DEFAULT_DEFAULTS
    return ExtractDeclaration(
        sf_object=user_decl.sf_object,
        where=user_decl.where or default_decl.where,
        fields=user_decl.fields or default_decl.fields,
        api=user_decl.api,
    )


_DEFAULT_DEFAULTS = ExtractDeclaration(fields="FIELDS(REQUIRED)")
